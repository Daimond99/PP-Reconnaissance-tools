# TheRecon

**Network Reconnaissance Console** — a PySide6 desktop GUI that orchestrates a
chain of authorized security-testing tools (Nmap, Masscan, Hydra, Ncrack, Ncat,
Evil-WinRM) behind a guided wizard and a gated manual-command mode.

> **Authorized testing only.** Every path that runs a real command requires an
> explicit human confirmation first. Point it only at systems you own or have
> **written** permission to test.

---

## What it is

TheRecon is a **front-end and safety layer** over six command-line tools. It
doesn't reimplement them — it helps you build the right command, shows you
exactly what will run and its impact, makes you confirm, then runs it inside a
real terminal and collects the results. The actual tools run inside **WSL2
(Ubuntu)** on Windows, or **natively** on Linux.

**Supported tools:** Nmap · Masscan · Hydra · Ncrack · Ncat · Evil-WinRM

## What it can do today

- **Wizard Console** — the guided path. A form on the left (target / mode /
  wordlists) drives an embedded chain CLI in a real terminal beside it:
  `scan → impact-ranked attack plan → brute-force → credential harvest →
  in-scope post-exploit`. Each step asks for confirmation before it runs.
- **Direct Tool Mode** (top bar) — pick a tool + a pre-built "warhead" profile,
  or type a command yourself. It's validated, previewed with a per-flag impact
  summary, and only runs after you type the exact word `yes`. Secrets
  (passwords) are masked in the preview and the audit log.
- **Results Display** — parses completed Nmap/Masscan scans into a host/port
  table and Hydra/Ncrack output into a credentials table.
- **Raw Output** — display-only view of what Direct Tool Mode ran.
- **LLM Mode** — two AI-assisted terminals (an `llm` CLI with nmap tools, and a
  scoped OpenCode agent). Optional, ungated by design — see the safety note.

**What it is *not*:** a web-application scanner. The six tools cover the
network / service / credential / post-exploit layers well, but there is no
directory brute-forcer, web-vuln scanner, or SQLi/XSS tooling. Scanning a
website with it reaches the service and TLS layer only.

---

## Install

Tools run **inside WSL2 (Ubuntu)** on Windows, or **natively** on Linux. The
GUI itself always runs on the host Python.

### Quick install (one command)

**Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/Daimond99/TheRecon/main/install.sh | bash
```

**Windows** (first run from an **elevated** PowerShell if WSL isn't installed
yet — installing WSL needs admin + a reboot, so the script stops and asks you
to reboot then re-run once):
```powershell
irm https://raw.githubusercontent.com/Daimond99/TheRecon/main/install.ps1 | iex
```

Both install the 6 tools, clone the repo (default `~/TheRecon`, override with
`$THERECON_DIR`/`THERECON_DIR`), create a venv, and install Python deps.
Re-running is safe (idempotent).

### Manual install

**1. Windows only — WSL2 + Ubuntu:**
```powershell
wsl --install -d Ubuntu
```
Reboot if prompted, then open Ubuntu once to finish user setup.

**2. Install the 6 tools** — inside WSL Ubuntu (Windows) or your native shell
(Linux), same command either way:
```bash
sudo apt-get update
sudo apt-get install -y nmap masscan hydra ncrack ncat ruby ruby-dev
sudo gem install evil-winrm
```

**3. Clone + Python deps:**

> **WSL users:** clone into your Linux home (`cd ~` first), **not** `/mnt/c/...`.
> Cloning onto the Windows filesystem from inside WSL fails with
> `chmod on .git/config.lock failed: Operation not permitted` (DrvFs doesn't
> support the permissions git needs). The app still runs fine on Windows either
> way — this is only about where the repo folder lives.

```bash
cd ~
git clone https://github.com/Daimond99/TheRecon.git
cd TheRecon

# Windows:         python -m venv .venv  &&  .venv\Scripts\activate
# Linux/WSL/macOS: python3 -m venv .venv  &&  source .venv/bin/activate

pip install -r requirements.txt
```

> **Debian/Kali/Ubuntu:** if `pip install` errors with
> `externally-managed-environment` (PEP 668), you skipped the venv step above —
> that's the fix, not `--break-system-packages`.

**4. Run:**
```bash
python -m src.main
```

At startup a **preflight doctor** checks WSL, the 6 tools, and both Python
runtimes; if anything's missing it shows a non-blocking warning with the exact
fix. Run it standalone any time:
```bash
python -m src.preflight
```

---

## Optional: LLM Mode setup

Not covered by the installers — only needed for the LLM Mode page. Run inside
WSL Ubuntu (Windows) or your native shell (Linux):

**"LLM" tab** — `llm` CLI + nmap function-calling tools:
```bash
pipx install llm
git clone https://gitlab.com/kalilinux/packages/llm-tools-nmap.git tools/llm-tools-nmap
llm keys set openai          # or: llm install llm-gemini && llm keys set gemini
```

**"OpenCode" tab** — scoped coding agent:
```bash
curl -fsSL https://opencode.ai/install | bash
```
The tab sets up its own scoped workspace on first open.

---

## Tests

```bash
python -m pytest tests/ -q
```
Covers the safety-critical validators and the confirmation gate: the 6-tool
whitelist, the quote-aware shell-injection guard, the exact-`yes` rule,
Windows→WSL path rewriting, scope enforcement, single-use replay protection,
and secret masking.

---

## Safety note

- The **Wizard Console** and **Direct Tool Mode** are gated — nothing runs
  without a per-step / exact-`yes` confirmation.
- **Raw Output** is display-only (no keystroke reaches a shell).
- **LLM Mode** is two *ungated* real shells, by design. Review your threat model
  before using it against real targets.

---

## More detail

- **[CLAUDE.md](CLAUDE.md)** — architecture rules and hard constraints.
- **[docs/CURRENT_STATE.md](docs/CURRENT_STATE.md)** — a file-by-file map of
  what's implemented and what each module does.
- **[docs/PROGRESS.md](docs/PROGRESS.md)** — the running change log.

---

## Disclaimer

The authors and contributors of TheRecon are not responsible for any misuse or
damage caused by this program. Use responsibly and only on systems you are
authorized to test.
