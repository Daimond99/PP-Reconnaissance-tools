# TheRecon

**Network Reconnaissance Console** — desktop GUI (PySide6) for orchestrating security reconnaissance tool chains, with a guided Wizard Console and gated direct command execution. Every execution path requires explicit human confirmation before a command runs.

---

## What it does

- **Wizard Console** — tabbed terminal (PyCharm-style tabs, drag to reorder): the first tab runs the embedded chain CLI (`chain_wizard/`): target → scan → impact-ranked attack plan → hydra brute-force → credential harvest → in-scope post-exploit (ncat / nmap-NSE / evil-winrm). `+`/`▾` open more Wizard or plain Shell tabs. Terminal itself is a real xterm.js emulator (the one VS Code uses) over a real PTY — full color, resize reflow, mouse selection, copy/paste, curses apps (vim/htop).
- **Top-bar Execute** — manual command entry, validated and confirmed through the same `ConfirmationGate` (exact `"yes"` to run, secrets masked in previews/logs) as the wizard.
- **Raw Output / LLM Mode** — plain, ungated real shells for free-form use.

Supported tools: **Nmap, Masscan, Hydra, Ncrack, Ncat, Evil-WinRM**.

---

## Cross-platform install

Routing happens at the "where the tools run" level:

- **Windows** → tools run **inside WSL2 (Ubuntu)**. Install WSL first, then the tools inside it.
- **Linux** → tools run **natively**. Just install the tools directly.

### 1. Windows only — install WSL2 + Ubuntu

```powershell
wsl --install -d Ubuntu
```

Reboot if prompted, then open Ubuntu once to finish setup (creates your WSL user).

### 2. Install the 6 tools

Run this **inside WSL Ubuntu** (Windows) or your **native shell** (Linux) — same command either way:

```bash
sudo apt-get update
sudo apt-get install -y nmap masscan hydra ncrack ncat ruby ruby-dev
sudo gem install evil-winrm
```

### 3. Clone the repo and install Python deps

```bash
git clone https://github.com/Daimond99/TheRecon.git
cd TheRecon

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt
```

`PySide6-QtWebEngine` (the Wizard Console's terminal renderer) and `pywinpty` (Windows-only ConPTY fallback) install automatically via `requirements.txt`.

### 4. Run

```bash
python -m src.main
```

---

## More detail

See [`CLAUDE.md`](CLAUDE.md) for architecture rules and [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) for what's implemented vs. placeholder, including known safety gaps.

---

## Disclaimer

The authors and contributors of TheRecon are not responsible for any misuse or damage caused by this program. Use responsibly and only on systems you are authorized to test.
