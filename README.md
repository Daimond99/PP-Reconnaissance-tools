# TheRecon

**Network Reconnaissance Console** — A desktop GUI for orchestrating security reconnaissance tool chains, with a guided Wizard Console and gated direct command execution.

Built with **Python** and **PySide6**, TheRecon provides a unified console for network scanning, credential testing, and Windows post-exploitation tooling. Every execution path — the Wizard Console and the top-bar Execute button — requires explicit human confirmation before a command runs.

> ⚠️ **Legal Notice:** This tool is intended for **authorized security testing and educational purposes only**. Always obtain explicit permission before scanning or testing any system you do not own. Unauthorized use may violate applicable laws.

---

## Features

| Feature | Description |
|---------|-------------|
| **Wizard Console** | Guided chain CLI (`chain_wizard/`): scan → impact-ranked plan (AUTO/SEMI) → hydra brute-force → credential harvest → in-scope post-exploit — embedded in the GUI as a real terminal |
| **Confirmation Gate** | Every gated execution path requires an exact literal `"yes"` before a command runs; secrets (passwords) are masked in previews/audit logs |
| **Top-bar Execute** | Manual command entry, validated and confirmed through the same gate as the wizard |
| **Tool Manager** | Automatic detection of installed tools |
| **Cross-Platform routing** | Windows runs the wizard CLI inside WSL Ubuntu (tools native there); Linux runs it natively — routing happens at the "where the CLI runs" level, not per-tool |
| **Modern UI** | Frameless dark-theme console with sidebar navigation and an embedded terminal (ConPTY + pyte on Windows) |

---

## Supported Tools

| Category | Tools |
|----------|-------|
| Network Scanner | [Nmap](https://nmap.org/), [Masscan](https://github.com/robertdavidgraham/masscan) |
| Connection | [Ncat](https://nmap.org/ncat/) |
| Password Attack | [Hydra](https://github.com/vanhauser-thc/thc-hydra), [Ncrack](https://nmap.org/ncrack/) |
| Windows Attack | [Evil-WinRM](https://github.com/Hackplayers/evil-winrm) |

The application detects which tools are installed on your system at startup and provides installation guidance for missing dependencies.

---

## Requirements

- **Python** 3.8 or later
- **PySide6**, **keyring**, **pyte** (see `requirements.txt`); **pywinpty** on Windows for the embedded ConPTY terminal
- **WSL2 (Ubuntu)** on Windows — `chain_wizard/` and its tools run inside WSL, not natively on Windows
- External security tools (Nmap, Masscan, Hydra, Ncrack, Ncat, Evil-WinRM) — installed separately, inside WSL on Windows or natively on Linux

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Daimond99/TheRecon.git
cd TheRecon
```

### 2. Create a virtual environment (recommended)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install external tools

Install the 6 supported tools inside **WSL Ubuntu** (Windows) or natively (Linux) — `chain_wizard/` invokes them directly via subprocess, not through Windows-native binaries:

```bash
sudo apt-get install -y nmap masscan hydra ncrack ncat ruby ruby-dev
sudo gem install evil-winrm
```

---

## Usage

Launch the application from the project root:

```bash
python -m src.main
```

### Sidebar pages

1. **Wizard Console** — embeds the `chain_wizard/` chain CLI as a real terminal: target → scan → impact-ranked plan (`(recommended)`/`(optional)`/`(info)`) → per-step confirm → hydra brute-force → credential harvest/loot → in-scope post-exploit (ncat/nmap-NSE/evil-winrm).
2. **Input Management** / **Command Editor** — supporting panels for the mission bar workflow.
3. **Raw Output** — a plain real shell (WSL bash on Windows). Ungated by design — type anything.
4. **Results Display** — Zenmap-style host/port results view.
5. **LLM Mode** — a plain real shell for wiring up your own AI CLI (`claude`, `llm chat`, etc.). Also ungated.

**Top-bar Execute** — type a command in the mission bar and run it through the `ConfirmationGate`: preview → exact `"yes"` confirmation → execution. This and the Wizard Console are the only two paths that go through validation + confirmation; Raw Output and LLM Mode are intentionally plain, ungated shells.

---

## Project Structure

```
TheRecon/
├── src/
│   ├── main.py                    # Application entry point
│   ├── config.py                  # Theme/palette, AUTHORIZED_SCOPE, TOOL_ENABLEMENT
│   ├── ui/
│   │   ├── main_window.py         # Main window, top-bar Execute → ConfirmationGate
│   │   ├── widgets.py             # Sidebar, TopBar, all MainContentArea pages
│   │   ├── pty_terminal.py        # ConPTY (pywinpty) + pyte — Wizard Console terminal
│   │   └── terminal.py            # Plain-pipe InteractiveTerminal — Raw Output / LLM Mode
│   ├── core/
│   │   ├── confirmation_gate.py   # Human-in-the-loop safety gate ("yes" to execute)
│   │   ├── tool_manager.py        # Installed-tool detection
│   │   ├── auto_chain.py          # Attack-chain automation
│   │   └── api_key_manager.py     # LLM API key storage (keyring)
│   ├── tools/nmap/                # builder/validator/parser/analyzer (top-bar Execute path)
│   ├── validation/common.py       # Shared validation primitives
│   ├── report/audit_log.py        # Audit log for LLM-mode commands
│   └── resources/*.json           # Menus, warnings, scan profiles — resource-driven text
├── chain_wizard/                  # The live chain wizard (standalone CLI, embedded in the GUI)
│   ├── wizard/                    # main.py, chain.py (orchestration), pipeline.py (plan)
│   ├── library/                   # scanner.py, attack_map.py/.json, post_exploit.py/.json
│   └── core/                      # executor.py, display.py, color.py, models.py
├── requirements.txt
└── README.md
```

---

## Architecture Overview

Fixed layer pipeline, no layer may skip another:

```
GUI (src/ui/) → Validation (src/validation/) → Command Builder (src/tools/nmap/builder.py)
  → Confirmation Gate (src/core/confirmation_gate.py) → Execution (QProcess)
  → Parser (src/tools/nmap/parser.py) → Analysis (src/tools/nmap/analyzer.py)
```

The Wizard Console is a separate embedded process (`chain_wizard/`, launched via `src/ui/pty_terminal.py`) that scans, builds its own plan, and confirms per-step inside the CLI itself — it does not route through `src/tools/`.

---

## Development

```bash
# Run from project root
python -m src.main
```

Key modules:
- `src/core/confirmation_gate.py` — the one human-in-the-loop safety gate every gated execution path goes through
- `src/core/tool_manager.py` — installed-tool detection
- `src/config.py` — stylesheet, color palette, `AUTHORIZED_SCOPE`, `TOOL_ENABLEMENT`
- `chain_wizard/wizard/chain.py` — the wizard's own orchestration (scan → plan → confirm → run → loot → post-exploit)

See [`CLAUDE.md`](CLAUDE.md) for the full architecture rules and [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) for what's implemented vs. placeholder right now, including known safety gaps.

---

## Contributing

Contributions are welcome. Please open an issue to discuss significant changes before submitting a pull request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## License



---

## Author

**Daimond99** — [GitHub](https://github.com/Daimond99)
**Phon** — 
---

## Disclaimer

The authors and contributors of TheRecon are not responsible for any misuse or damage caused by this program. Use responsibly and only on systems you are authorized to test.
