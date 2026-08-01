# TheRecon

**Network Reconnaissance Console** — desktop GUI (PySide6) for orchestrating security reconnaissance tool chains, with a guided Wizard Console and gated direct command execution. Every execution path requires explicit human confirmation before a command runs.

---

## What it does

- **Wizard Console** — tabbed terminal (PyCharm-style tabs, drag to reorder): the first tab runs the embedded chain CLI (`chain_wizard/`): target → scan → impact-ranked attack plan → hydra brute-force → credential harvest → in-scope post-exploit (ncat / nmap-NSE / evil-winrm). `+`/`▾` open more Wizard or plain Shell tabs. Terminal itself is a real xterm.js emulator (the one VS Code uses) over a real PTY — full color, resize reflow, mouse selection, copy/paste, curses apps (vim/htop).
- **Top-bar Execute** — manual command entry, validated and confirmed through the same `ConfirmationGate` (exact `"yes"` to run, secrets masked in previews/logs) as the wizard.
- **Raw Output** — display-only surface for Top-bar Execute's output; nothing typed into it is ever sent to a shell.
- **LLM Mode** — two ungated real shells for free-form AI-tool use: an `llm` CLI tab pre-wired with nmap function-calling tools, and a PATH-scoped OpenCode coding-agent tab. See "Optional: LLM Mode setup" below — not installed by `install.sh`/`install.ps1`.

Supported tools: **Nmap, Masscan, Hydra, Ncrack, Ncat, Evil-WinRM**.

---

## Cross-platform install

Routing happens at the "where the tools run" level:

- **Windows** → tools run **inside WSL2 (Ubuntu)**. Install WSL first, then the tools inside it.
- **Linux** → tools run **natively**. Just install the tools directly.

### Quick install (one command)

**Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/Daimond99/TheRecon/main/install.sh | bash
```

**Windows** (from an elevated PowerShell the *first* run only, if WSL isn't installed yet — installing WSL needs admin + a reboot, so the script will stop and ask you to reboot then re-run it once):

```powershell
irm https://raw.githubusercontent.com/Daimond99/TheRecon/main/install.ps1 | iex
```

Both scripts install the 6 tools, clone the repo (default `~/TheRecon`, override with `$THERECON_DIR`/`THERECON_DIR` env var), create a venv, and install Python deps — see [`install.sh`](install.sh)/[`install.ps1`](install.ps1). Re-running either is safe (idempotent). The manual steps below are the same thing spelled out, useful if you want to see/control each step yourself.

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

## Optional: LLM Mode setup

Not covered by `install.sh`/`install.ps1` — only needed if you want the **LLM Mode** page's two tabs. Run these **inside WSL Ubuntu** (Windows) or your **native shell** (Linux) — same commands either way, same as the 6-tool install above.

**"LLM" tab — `llm` CLI + nmap function-calling tools:**

```bash
pipx install llm
git clone https://gitlab.com/kalilinux/packages/llm-tools-nmap.git tools/llm-tools-nmap
llm keys set openai          # or: llm install llm-gemini && llm keys set gemini
```

(the tab itself offers to run `llm keys set openai` on first open if no key is stored yet)

**"OpenCode" tab — scoped coding agent:**

```bash
curl -fsSL https://opencode.ai/install | bash
```

The tab handles the rest itself on first open — creates `tools/opencode-workspace/`, drops a scope-note `AGENTS.md` there, and restricts `$PATH` to the 6 authorized tools before launching OpenCode.

---

## More detail

See [`CLAUDE.md`](CLAUDE.md) for architecture rules and [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) for what's implemented vs. placeholder, including known safety gaps.

---

## Disclaimer

The authors and contributors of TheRecon are not responsible for any misuse or damage caused by this program. Use responsibly and only on systems you are authorized to test.
