# TheRecon — Function & Mode Reference (for LLM readers)

A companion to `CLAUDE.md` and `docs/CURRENT_STATE.md`, written specifically to
answer: **"what does each function/module do, and what are the modes?"**
Read `docs/CURRENT_STATE.md` first for the full picture — this file is a
denser, function-level index on top of it.

---

## 1. The three user-facing modes

| Mode | Where | Gated? | What it does |
|------|-------|--------|--------------|
| **Direct Tool Mode** | Top bar (TOOLS combo + TARGET + Execute) | Yes — `ConfirmationGate` | User picks a tool + warhead profile, edits the command box directly, clicks Execute. Single command, single run. |
| **Wizard Console** | Sidebar page 0 | Yes — `ConfirmationGate(channel="wizard")` | Guided multi-step flow: scan → build attack plan → confirm each step → execute → harvest creds → post-exploit. Runs `chain_wizard/` as a hidden subprocess talking JSON over stdio. |
| **LLM Mode** | Sidebar page 4, two tabs | Split: OpenCode tab is ungated (Docker sandbox is the backstop); "LLM Nmap" tab is gated | **OpenCode** — full agentic coding/shell session `docker exec`'d into the sandboxed container. **LLM Nmap** — a suggestion-only panel: LLM proposes an nmap command, human confirms via the same gate as Direct Tool Mode before it runs. |

All three ultimately funnel any actual tool execution through
`src/core/confirmation_gate.py` (Wizard Console and Direct Tool Mode always;
OpenCode is the one path that doesn't, and it's contained by the Docker
sandbox instead — see `docs/DOCKER_SANDBOX_DEFENSE.md`).

Note: the Wizard used to have an AUTO vs SEMI mode toggle (auto-run the whole
plan vs pick per-port). **SEMI was removed 2026-08-29** — there is no mode
selector in the Wizard UI anymore, it's AUTO only.

---

## 2. Startup sequence (`src/main.py`)

1. Linux only: set QtWebEngine software-render env vars (needed under WSLg/headless).
2. `faulthandler.enable()` → crashes go to `logs/crash.log`.
3. Apply `STYLESHEET` from `src/config.py`, show splash screen.
4. Construct `ReconMainWindow`; splash stays up until the Wizard Console's
   first terminal actually produces PTY output (`firstTabReady` signal),
   capped at 20s — because WSL boot can lag behind widget construction.
5. ~2.5s later, run `src/preflight.py`'s dependency doctor in a background
   `QThread`; pops a warning dialog only if something's missing/broken.

---

## 3. Pipeline every execution path follows

```
GUI  →  Validation  →  ConfirmationGate  →  Execution  →  Parser  →  Results Display
```

No step may be skipped, and the GUI layer is never allowed to build a command
string or contain logic like "is this flag dangerous" — that lives in
`src/validation/` and `src/tools/*/analyzer.py`.

---

## 4. Core safety functions (`src/validation/common.py`)

| Function | Purpose |
|----------|---------|
| `parse_command_line(cmd)` | Splits the typed command with shlex, checks the first token (or the token after a bare `sudo`) is one of the 6 allowed programs (`ALLOWED_PROGRAMS`). Rejects anything else. |
| `_has_unquoted_shell_metachar(s)` | Quote-aware scan for `; & \| \` $ ( ) < > \`. Only flags these characters when they sit **outside** a `'...'`/`"..."` span — so a hydra payload like `http-post-form "user=^USER^&pass=^PASS^"` passes, but `foo; rm -rf /` is rejected. |
| `convert_windows_paths_to_wsl(cmd)` | On Windows only: rewrites any `C:\...` path in the command to `/mnt/c/...` before validation, because the command actually runs inside WSL bash which has no drive letters. |
| `validate_exact_confirmation(reply)` | Returns True only if `reply == "yes"` exactly. No "y", "Yes", "YES". |

## 5. The confirmation gate (`src/core/confirmation_gate.py`)

One `ConfirmationGate` instance = one pending command, single-use.

- **`request(cmd, target, tool, skip_scope=False, argv_override=None)`**
  Validates the command, rewrites Windows paths, builds a human-readable
  impact preview via `nmap.analyzer.generate_impact_description()`. Does
  **not** execute anything. `argv_override` lets the real argv (with a real
  password) run while the preview/audit-log shows a masked string instead.
  `skip_scope=True` bypasses the `AUTHORIZED_SCOPE` (192.168.1.0/24) check —
  used when the human typed the target themselves (Direct Tool Mode, Wizard).
  Detects a bare `sudo` prefix and appends a root-privilege warning to the
  preview (masscan/nmap raw sockets need root inside WSL).
- **`confirm(reply)`**
  Only returns True for the literal string `"yes"`. Writes one line to
  `logs/audit_log.jsonl` either way (decision + whether it executed). Marks
  itself spent so calling `confirm("yes")` twice on the same gate does
  nothing the second time (replay protection).

Two callers today: `main_window._on_execute_clicked` (Direct Tool Mode) and
`src/core/wizard_driver.py` (`channel="wizard"`, one gate per wizard step).

## 6. Impact/analysis functions (`src/tools/nmap/analyzer.py`)

- `generate_impact_description(flags, target, tool)` — looks up
  `src/resources/<tool>/flag_impacts.json` and returns plain-English risk text
  per flag, for **any** of the 6 tools, not just nmap (name is legacy).
- `format_confirmation_box(...)` — renders the text block shown in the
  confirmation dialog.
- `is_target_in_scope(target)` — checks target against `AUTHORIZED_SCOPE`
  from `src/config.py`. Only actually enforced on the LLM Nmap panel's
  free-typed target (see gaps below).

## 7. Result parsers (`src/tools/<tool>/parser.py`)

Only exist where something real consumes the output — never scaffolded.

| Tool(s) | Parser | Feeds |
|---------|--------|-------|
| nmap, masscan | `nmap/parser.py::parse_nmap_xml()` | Results Display's host/port table (masscan's `-oX` is a compatible subset, same parser handles both) |
| hydra | `hydra/parser.py` | Results Display's separate "Credentials Found" table |
| ncrack | `ncrack/parser.py` | Same credentials table |
| ncat, evil-winrm | none | Interactive sessions, nothing structured to parse |

`main_window._scan_xml_capture_paths()` / `_cred_capture_paths()`
auto-append the right output flag (`-oX`, `-o`, `-oN`) to a bare command
before it's confirmed, so the user doesn't have to remember to add it.

## 8. Terminal backend (3-tier fallback, `terminal_tabs.make_terminal()`)

1. `XtermTerminal` (`src/ui/webterm/`) — primary. xterm.js in `QWebEngineView`
   over a real PTY. Full terminal features (reflow, mouse select, curses apps).
2. `PtyTerminal` (`src/ui/pty_terminal.py`) — fallback. ConPTY + pyte → HTML
   in a `QTextEdit`. No resize reflow.
3. `InteractiveTerminal` (`src/ui/terminal.py`) — last resort. Plain
   `QProcess` pipe, no TTY features at all.

## 9. The Docker sandbox (the real execution boundary)

`docker/run.sh` is the **only** place `docker run` is ever invoked. The
container (`therecon-tools`):
- non-root user, `--cap-drop=ALL` + minimal `--cap-add`
- `--read-only` rootfs
- no `docker.sock` or `/mnt/c` mount
- dedicated bridge network, never `--network=host`

The app talks to it via `docker exec` (`chain_wizard/core/executor.py`,
`src/ui/terminal_launch.py`), never a bare host-side `subprocess.run(shell=True)`.
This means even if an LLM gets tricked (e.g. by a scanned target's banner)
into suggesting a `sudo`-prefixed destructive command that a human then
approves, the blast radius is the disposable container, not the real host.
Full threat model in `docs/DOCKER_SANDBOX_DEFENSE.md`.

## 10. Wizard CLI internals (`chain_wizard/`, repo root — not under `src/`)

Launched as a subprocess (`python3 -m wizard.main --target ... --gui`) by
`WizardDriver`. Talks JSON-over-stdio instead of `input()`/`print()` when
`--gui` is passed.

| Module | Purpose |
|--------|---------|
| `wizard/main.py` | Entry point, arg parsing, loop control |
| `wizard/chain.py` | Orchestrates: scan → plan → confirm → run → parse creds → post-exploit |
| `wizard/pipeline.py` | `build_plan()` (AUTO only), `step_priority()` |
| `library/scanner.py` | nmap quick/full/stealth scans + masscan |
| `library/attack_map.py` + json | port number → which tool/command template to use |
| `library/post_exploit.py` + json | discovered service → post-exploit action |
| `library/parser.py` | gnmap output → `ScanResult` dataclass |
| `core/executor.py` | actually runs the shell command (`subprocess.run(shell=True)`), handles sudo priming |
| `core/ui_driver.py` | `UI` abstraction — `CliUI` (real terminal prompts) vs `IpcUI` (JSON protocol to the Qt GUI) |
| `core/models.py` | `Step`, `ScanResult`, `AttackPlan` dataclasses |

## 11. Resource-driven text (`src/resources/*.json`)

Nothing user-facing (menus, warnings, impact text, prompt templates) is a
Python string literal — all loaded via `src/utils/resource_loader.py::load_json()`,
the only function allowed to `open()` a resource file. Degrades to `{}` on
missing/broken files instead of crashing.

| File | Purpose |
|------|---------|
| `tool_commands.json` | base command template per tool |
| `warheads/<tool>.json` (×6) | 6 pre-built profiles per tool (2 stealth/2 critical/2 quality) |
| `<tool>/flag_impacts.json` (×6) | per-flag risk text for the confirmation dialog |

---

## 12. Known intentional gaps (not bugs)

- **OpenCode tab + plain Shell tab**: no `ConfirmationGate`, no exact-`"yes"`.
  Backstop is the Docker sandbox, not a dialog.
- **`AUTHORIZED_SCOPE` is not enforced** on Direct Tool Mode or Wizard Console
  (`skip_scope=True` on both — target is assumed to be the user's own lab).
  It **is** enforced on the LLM Nmap suggestion panel, the one path where the
  target isn't typed by a human directly.

See `docs/CURRENT_STATE.md` §12 for the full, currently-maintained list.
