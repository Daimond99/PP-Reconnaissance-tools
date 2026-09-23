# PP-Reconnaissance-tools

> **Safety-gated GUI orchestrator for authorized network reconnaissance.**
> Solves the "one wrong flag away from scanning the wrong subnet" problem by forcing every command through validation → preview → exact-`yes` confirmation → audited execution, all behind a single desktop app.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-41CD52?logo=qt)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)
![Tests](https://img.shields.io/badge/tests-82%20passing-brightgreen)

---

## Screenshots

| Wizard Console (guided chain) | Direct Tool Mode (manual + validated) |
|---|---|
| ![Wizard Mode](img-gui/wizardmode.png) | ![Direct Tool Mode](img-gui/direct-tool-mode.png) |

| Confirmation Gate (exact-`yes` required) | Parsed Results Display |
|---|---|
| ![Confirm Dialog](img-gui/warring-confirm.png) | ![Results](img-gui/results-display.png) |

| LLM-assisted Mode (ungated by design) | Wizard Step 2 |
|---|---|
| ![LLM Mode](img-gui/llm-ai-agent.png) | ![Wizard 2](img-gui/wizardmode2.png) |

> Additional screenshots in [`img-gui/`](img-gui/): `input-management.png`, `setting.png`, `llm-nmap-mode.png`, `llm-agent2.png`.
> <!-- TODO: record a short GIF demo of the full Wizard chain (scan → plan → brute → post-exploit) and replace this line. -->

---

## Key Features & Security Controls

Every item below maps to code that ships in this repo — see the file reference in each bullet.

- **Whitelist enforcement (6-tool allow-list)** — `ALLOWED_PROGRAMS = {nmap, masscan, hydra, ncrack, ncat, evil-winrm}` in `src/validation/common.py`. Any other program (including `bash`, `sh`, `curl`, `python`) is rejected before execution. Bare `sudo` prefix is permitted only when the elevated program is still one of the 6.
- **Quote-aware shell-injection guard** — `_has_unquoted_shell_metachar()` scans char-by-char honoring `'...'` / `"..."` regions; blocks `; | & \` \` $ ( ) < > \` when they appear **outside** a quoted region. Lets Hydra's `http-post-form "…&pass=…"` payloads through; still rejects `foo; rm -rf /`.
- **Exact-`yes` confirmation contract** — `validate_exact_confirmation()`: only the case-sensitive literal string `"yes"` counts. `y`, `Yes`, `YES`, whitespace, empty Enter all cancel. Enforced by `ConfirmationGate.confirm()` and the wizard-step gate.
- **Single-use replay protection** — `ConfirmationGate` sets `_pending = False` after every `confirm()` (success or failure), so a stale `"yes"` cannot re-fire the same argv (`src/core/confirmation_gate.py:145`).
- **Secret masking via `argv_override`** — the preview string / audit-log entry can be a masked version (`****`) of the command while the real argv still executes. Real credentials never touch `self.command`, the preview box, or the audit log (`confirmation_gate.py:82-86`).
- **Append-only JSONL audit log with size-based rotation** — `src/report/audit_log.py` writes every gated decision (channel, command, target, response, executed, provider, exit_code) to `logs/audit_log.jsonl`. Rotates at 5 MB × 3 backups so a long-lived install can't fill the disk; history is preserved, never overwritten mid-write.
- **Sandboxed execution (Docker)** — all 6 tools run inside a non-root, `--cap-drop=ALL`, `--read-only`-rootfs container (`docker/Dockerfile` + `docker/run.sh`), never directly on the WSL2/Linux host. Specifically defends against indirect prompt injection: a scanned target's banner tricking an LLM into suggesting a `sudo`-prefixed command that a human then approves still only damages the disposable container. See `docs/DOCKER_SANDBOX_DEFENSE.md` for the full threat model + live test evidence.
- **Scope enforcement (least-privilege target)** — `is_target_in_scope()` checks the target against `AUTHORIZED_SCOPE` (CIDR, defaults to `192.168.1.0/24`) before validation runs. Off-scope targets are rejected with `[!] Scope violation`. In practice `skip_scope=True` is used for Direct Tool Mode and the Wizard Console (both take a target the human typed in directly — the human typing it is treated as the scope decision); it's actively enforced on the one path where the target is AI-suggested rather than human-typed (the "LLM Nmap" panel).
- **Windows→WSL path rewrite** — `convert_windows_paths_to_wsl()` transparently rewrites `C:\wordlists\rockyou.txt` → `/mnt/c/wordlists/rockyou.txt` before validation, because commands actually execute inside WSL bash which has no drive-letter concept. Runs before the injection guard sees a bare backslash.
- **Per-flag impact preview** — `generate_impact_description(flags, target, tool)` reads `src/resources/flag_impacts.json` (all 6 tools) and produces a human-readable "this will…" block shown in the confirmation dialog. Detects bare `sudo` and appends an explicit root-privilege warning.
- **Non-repudiable channel tagging** — audit entries carry `channel` (`plain` / `ai` / `wizard`) and `provider` (`openai` / `gemini`) so an AI-suggested run is distinguishable from a human-typed one post-hoc.
- **Startup preflight doctor** — `python -m src.preflight` verifies WSL availability, all 6 tools installed, and both Python runtimes; runs at app launch with a non-blocking warning and the exact fix command.

---

## Tech Stack

| Layer | Choice | Where |
|---|---|---|
| Language | Python 3.10+ | — |
| GUI framework | PySide6 ≥ 6.6 (Qt6) | `src/ui/` |
| Terminal (primary) | xterm.js in `QWebEngineView` + real PTY | `src/ui/webterm/` |
| Terminal (fallback) | pyte VT emulator + ConPTY/pywinpty | `src/ui/pty_terminal.py` |
| Terminal (last resort) | `QProcess` pipe | `src/ui/terminal.py` |
| Execution env (Windows) | WSL2 / Ubuntu | via `wsl.exe` |
| Execution env (Linux) | native shell | — |
| Tool sandbox | Docker container (`therecon-tools`) | `docker/Dockerfile`, `docker/run.sh` — all 6 tools run here, not on the host |
| Wrapped tools | Nmap · Masscan · Hydra · Ncrack · Ncat · Evil-WinRM | 6-tool whitelist |
| Test framework | pytest | `tests/` |
| Audit format | JSONL, append-only, size-rotated | `logs/audit_log.jsonl` |
| Optional LLM | `llm` CLI (OpenAI / Gemini/ Claude), OpenCode agent | LLM Mode page |

---

## How to Run / Setup

**Prerequisites**: Python 3.10+; Windows users also need WSL2 + Ubuntu and Docker Engine inside it — not Docker Desktop (both auto-installed by `install.ps1`).

> **Linux branch note:** the fixes that make this run cleanly on native
> Linux (Kali/Debian/Ubuntu — QtWebEngine runtime libs, `evil-winrm`'s
> `libreadline-dev` build dep, the `/results` bind-mount permission fix)
> live on the [`for-linux-version`](https://github.com/Daimond99/PP-Reconnaissance-tools/tree/for-linux-version)
> branch, not yet on `main`. The commands below install from that branch;
> swap `for-linux-version` → `main` once it's merged.

### Quick install (one command)

**Linux** (Debian/Ubuntu/Kali, apt-based):
```bash
curl -fsSL https://raw.githubusercontent.com/Daimond99/PP-Reconnaissance-tools/for-linux-version/install.sh | bash
```

**Windows** (run from **elevated** PowerShell the first time — WSL install needs admin + reboot):
```powershell
irm https://raw.githubusercontent.com/Daimond99/PP-Reconnaissance-tools/main/install.ps1 | iex
```

Both installers are idempotent: install Docker Engine, build + start the sandboxed tool container (`docker/run.sh`), clone the repo (default `~/PP-Reconnaissance-tools`; override with `$THERECON_DIR`), create a venv, install Python deps (`requirements.txt` → `PySide6>=6.6.0`, `pyte>=0.8.2`, `pywinpty>=2.0` on Windows). The 6 authorized tools (nmap/masscan/hydra/ncrack/ncat/evil-winrm) run only inside that container, never installed on the host directly — see `docker/Dockerfile`. `install.sh` will prompt for your `sudo` password (Docker install, group membership) — run it in a real terminal, not piped into something non-interactive.

### Manual install (Linux)

```bash
# 1. Clone this branch
git clone --branch for-linux-version https://github.com/Daimond99/PP-Reconnaissance-tools.git
cd PP-Reconnaissance-tools

# 2. Install Docker Engine -- NOT Docker Desktop, the native apt package
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"   # log out/in (or open a fresh terminal) to pick this up

# 3. QtWebEngine runtime libs (Wizard Console's terminal needs these to open)
sudo apt-get install -y \
    libnss3 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libxkbcommon0 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
    libxshmfence1

# 4. Build + start the sandboxed tool container
chmod +x docker/run.sh
./docker/run.sh

# 5. Python venv + deps
python3 -m venv .venv
source .venv/bin/activate      # or call .venv/bin/pip / .venv/bin/python directly
pip install -r requirements.txt

# 6. Run
python -m src.main
```

### Manual install (Windows, from `main`)

```powershell
# 1. WSL2 + Ubuntu
wsl --install -d Ubuntu   # reboot if prompted, open Ubuntu once

# 2. Install Docker Engine inside WSL Ubuntu -- NOT Docker Desktop
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

# 3. Clone + Python deps
git clone https://github.com/Daimond99/PP-Reconnaissance-tools.git
cd PP-Reconnaissance-tools
python -m venv .venv
.venv\Scripts\Activate.ps1     # or .venv\Scripts\activate.bat / .venv\Scripts\pip
pip install -r requirements.txt

# 4. Build + start the sandboxed tool container (inside WSL Ubuntu)
chmod +x docker/run.sh
./docker/run.sh

# 5. Run
.\.venv\Scripts\python -m src.main
```

Standalone preflight check (either OS):
```bash
python -m src.preflight     # or: .venv/bin/python -m src.preflight
```

---

## Test Coverage

```bash
python -m pytest tests/ -q             # 82 passed — GUI + safety layer
python -m pytest chain_wizard/tests/ -q   # 14 passed — wizard CLI + IPC protocol
```

Two separate suites, both safety-critical, no external target required for either:

| Suite | File | Covers |
|---|---|---|
| `tests/` | `test_validation.py` | 6-tool whitelist, quote-aware injection guard, exact-`yes` rule, Windows→WSL path rewrite, `sudo` prefix handling, `shlex` parse errors |
| `tests/` | `test_confirmation_gate.py` | Scope enforcement, preview/argv separation, single-use replay protection, secret masking via `argv_override`, audit-log side effects, cancel path |
| `tests/` | `test_terminal_launch.py` | Cross-platform launcher script builders (WSL vs native, incl. the OpenCode→Docker `docker exec` launch) |
| `tests/` | `test_gui_smoke.py` | Headless PySide6 widget construction — imports don't break, main window builds |
| `chain_wizard/tests/` | `test_ui_driver.py`, `test_chain_status.py` | `IpcUI` JSON request/reply shapes, `CliUI`/`IpcUI` singleton, wizard status events |

---

## Repo Layout

```
src/
├── main.py                       # entry point, splash → ReconMainWindow
├── preflight.py                  # startup doctor: WSL + 6 tools + Python
├── config.py, theme.py           # constants, AUTHORIZED_SCOPE, palette
├── core/
│   ├── confirmation_gate.py      # THE gate — request/confirm/cancel + audit
│   ├── tool_manager.py           # installed-tool detection
│   └── llm_keys.py
├── validation/common.py          # whitelist + injection guard + WSL rewrite
├── tools/                        # parsers/analyzers per tool
│   ├── nmap/     (parser, analyzer)
│   ├── hydra/    (parser)
│   └── ncrack/   (parser)
├── report/audit_log.py           # append-only JSONL + rotation
├── ui/
│   ├── main_window.py, wizard_panel.py
│   ├── widgets/  (sidebar, topbar, results, raw_output, input_management)
│   ├── webterm/  (xterm.js + PTY — primary terminal)
│   ├── pty_terminal.py, terminal.py, terminal_tabs.py, terminal_launch.py
└── utils/resource_loader.py      # single JSON-loader chokepoint (cached)

chain_wizard/                     # standalone guided-chain CLI (subprocess)
docker/                           # Dockerfile + run.sh — the sandbox the 6 tools run in
tests/                            # 82 tests, safety-critical paths (chain_wizard/tests/ has its own 14)
docs/                             # architecture, sandbox defense, data flow, Thai overview, scope Q&A, change log
img-gui/                          # GUI screenshots
```

---

## Docs

**Core (read these to understand the system + project scope):**
- [`CLAUDE.md`](CLAUDE.md) — architecture rules, layer discipline, hard constraints (source of truth when anything else conflicts with the source tree)
- [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) — file-by-file map of what's implemented, known gaps
- [`docs/DOCKER_SANDBOX_DEFENSE.md`](docs/DOCKER_SANDBOX_DEFENSE.md) — the tool sandbox's threat model, design, and live test evidence
- [`docs/OVERVIEW_TH.md`](docs/OVERVIEW_TH.md) — Thai-language first-read overview
- [`docs/WIZARD_DATA_FLOW.md`](docs/WIZARD_DATA_FLOW.md) — `chain_wizard/`'s internal data flow + every JSON schema that crosses a process/storage boundary
- [`docs/PP-scope-checklist.md`](docs/PP-scope-checklist.md) / [`docs/PP-SCOPE-QA.md`](docs/PP-SCOPE-QA.md) — academic project-scope checklist + a defend-ready Q&A mapping each scope item to code evidence

**History (not needed to understand the system as it is today):**
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — append-only running log, session by session

---

## Disclaimer

**For educational use in isolated lab environments only.** TheRecon wraps offensive-security tooling (network scanners, credential brute-forcers, remote-shell clients). Running these against systems you do not own or do not have **written** authorization to test is illegal in most jurisdictions. The default `AUTHORIZED_SCOPE = 192.168.1.0/24` reflects a home-lab assumption — reconfigure or self-host in an isolated VLAN, and the authors accept no liability for misuse.
