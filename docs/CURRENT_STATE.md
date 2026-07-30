# TheRecon — Current Code State (Snapshot for AI)

This file is a **snapshot of what actually exists in the code right now**,
not a spec. For normative rules, read `CLAUDE.md`. For the current
Wizard Console embedding plan and remaining TODOs, read
`CROSS_PLATFORM_TERMINAL_PLAN.md`. Update this file whenever the state below
goes stale.

Last verified: 2026-07-31, branch `main`, after the dead-tool-package
removal + `chain_wizard/` rename (see `PROGRESS.md`, "Dead tool packages
removed, wizard folder renamed").

## Entry point

`src/main.py` → applies `src/config.py` `STYLESHEET` → launches
`ReconMainWindow` (`src/ui/main_window.py`).

## Layer-by-layer, what's real vs stub

### GUI (`src/ui/`)

Sidebar has 6 pages (`Sidebar.NAV_ITEMS`, index 0–5), 1:1 with
`MainContentArea._build_pages()`:

| Index | Attr | Class | Notes |
|---|---|---|---|
| 0 | `wizard_tab` | `TerminalTabsWidget` — VS Code-style tabbed terminal; each tab is `XtermTerminal` (xterm.js in QWebEngineView + real PTY) → `PtyTerminal` (pyte/ConPTY) → `InteractiveTerminal`, first available wins | Wizard Console — first tab runs `chain_wizard/` CLI; `+`/`⌄` open more Wizard or plain Shell tabs, see below |
| 1 | `input_tab` | `InputManagementTab` | supporting panel |
| 2 | `cmd_editor_tab` | `CommandEditorTab` | supporting panel |
| 3 | `raw_output_tab` | `RawOutputTab` (wraps `InteractiveTerminal`) | plain real shell, ungated by design |
| 4 | `results_tab` | `ResultsDisplayTab` | Zenmap-style host/port view, starts empty |
| 5 | `llm_tab` | `InteractiveTerminal` | plain real shell for wiring up your own AI CLI, ungated |

- `main_window.py` — main window assembly, title bar, Settings popup menu,
  wires `Sidebar.navigate` → `MainContentArea.stack`. Top-bar Execute
  (`_on_execute_clicked`/`_run_gated_command`) is the **only** GUI path that
  goes through `ConfirmationGate` directly — result is shown via
  `QMessageBox` dialogs, not mirrored into any terminal.
- `webterm/` (`XtermTerminal`) — **primary Wizard Console terminal.** xterm.js
  (the emulator VS Code ships) hosted in a `QWebEngineView`, bridged over
  `QWebChannel` to a real PTY: ConPTY (`pywinpty`) running `wsl.exe -d Ubuntu
  bash` on Windows, stdlib `pty` fork of `bash` on Linux. IDE-grade behavior —
  reflow-on-resize, mouse select, copy/paste, and full curses apps
  (vim/nano/htop/python). Vendored JS (xterm.js/addon-fit/xterm.css/
  qwebchannel.js) under `webterm/vendor/`, no CDN. `XTERM_AVAILABLE` guards the
  QtWebEngine + PTY imports; if either is missing it degrades to `PtyTerminal`
  then `InteractiveTerminal`.
- `pty_terminal.py` (`PtyTerminal`) — legacy fallback. Real ConPTY (`pywinpty`) + `pyte` VT
  emulator rendered to a `QTextEdit` as HTML. On Windows this is what powers
  the Wizard Console: it launches `wsl.exe -d Ubuntu bash -lc "cd
  '/mnt/d/TheRecon/chain_wizard' && python3 -m wizard.main; exec bash -l"` —
  full color, working `sudo`, TAB completion, identical to a standalone WSL
  terminal. Falls back to plain `InteractiveTerminal` if `pywinpty`/`pyte`
  aren't importable.
- `terminal.py` (`InteractiveTerminal`) — non-PTY real shell via `QProcess`
  (stdin/stdout pipe, no TTY). Used for Raw Output, LLM Mode, and as the
  Wizard Console fallback when ConPTY is unavailable. Single `QTextEdit` is
  both scrollback and input line (no separate input row); Up/Down history
  recall.

Dead UI files from earlier passes (`wizard_terminal.py`, `wizard_console.py`,
`src/wizard/engine.py`, `tool_selection.py`, `llm_mode.py`) have all been
**deleted**, not just unwired — don't look for them.

### Wizard / orchestration

The live wizard is the standalone chain CLI under **`chain_wizard/`** (repo
root, NOT under `src/`). It does not import anything from `src/` — it's a
self-contained Python package invoked as a subprocess (`python3 -m
wizard.main`) inside the terminal described above.

- `wizard/main.py` — entry, target/mode/wordlist prompts, loops (Ctrl-C
  restarts, Ctrl-D exits).
- `wizard/chain.py` — orchestration: scan → `_select_steps` (impact-ranked
  menu, `(recommended)`/`(optional)`/`(info)` tags) → per-step confirm → run
  → `_parse_creds`/`_save_loot` → `_offer_post_exploit`/`_offer_winrm`.
- `wizard/pipeline.py` — `build_plan()` (AUTO/SEMI), `step_priority()`.
- `library/scanner.py` — nmap quick/full/stealth (tunable `-T`)/masscan.
- `library/attack_map.py` + `.json` — port → attack arsenal.
- `library/post_exploit.py` + `.json` — service → post-exploit action
  (ncat for ftp/telnet, nmap NSE for smb/mysql; evil-winrm handled
  separately, only after a real harvested credential).
- `library/parser.py` — gnmap → `ScanResult`.
- `core/executor.py` — `subprocess.run(shell=True)`, no `wsl.exe` prefix:
  routing is handled by **where the CLI itself runs** (inside WSL on
  Windows, natively on Linux), not by prefixing each tool call.
- `core/color.py` / `core/display.py` — ANSI (auto-disabled off-TTY),
  banner/section width adapting to `shutil.get_terminal_size()`.
- `core/models.py` — `Step`/`ScanResult`/`AttackPlan` dataclasses.

Restricted to the 6 authorized tools: nmap, masscan, hydra, ncrack, ncat,
evil-winrm.

### Validation (`src/validation/common.py`)

Shared validation: command-line parsing, exact-confirmation check (`"yes"`
literal match). Used by `ConfirmationGate`.

### Command builders (`src/tools/`)

Only **`src/tools/nmap/`** survives (`builder.py`/`validator.py`/
`parser.py`/`analyzer.py`/`__init__.py`). Its `analyzer` (
`format_confirmation_box`, `generate_impact_description`,
`is_target_in_scope`) is imported directly by `src/core/confirmation_gate.py`
— it's the only tool package still wired into anything.

The other five packages that used to live here — `hydra`, `masscan`, `ncat`,
`ncrack`, `evil_winrm` — were **deleted 2026-07-31**. Nothing imported them:
`chain_wizard/` calls those tools directly via `core/executor.py`
(`subprocess`, `shell=True`), not through per-tool builder/validator/parser/
analyzer modules. If a future task needs a gated (non-wizard) path for one
of those tools, it would need a new package written from scratch — don't
assume the old placeholders still exist.

### Confirmation gate (`src/core/confirmation_gate.py`)

The single human-in-the-loop safety gate. `request()` validates + builds a
preview only; `execute()` requires an exact literal `"yes"` reply. Supports
masking secrets via `argv_override`. Reached only by the top-bar Execute
button (`main_window._on_execute_clicked`/`_run_gated_command`) — the Wizard
Console does its own per-step confirmation inside the CLI itself and does
not call into this class.

### Other core (`src/core/`)

- `tool_manager.py` — installed-tool detection.
- `auto_chain.py` — attack-chain automation.
- `api_key_manager.py` — LLM API key storage via `keyring`.

### Resources (`src/resources/*.json` + `src/utils/resource_loader.py`)

`resource_loader.py` is the only component allowed to `open()` a resource
JSON; `load_json()` caches and degrades to `{}` on missing/malformed files.
Covers wizard menu/messages, nmap scan profiles/flag impacts, common
warnings, `nmap/service_tools.json`. Most prompt/dialog/validation-error
text elsewhere (`src/config.py`) is still hardcoded Python strings, not
migrated to resources.

`chain_wizard/library/attack_map.json` and `post_exploit.json` are a
separate, resource-driven data source specific to the wizard CLI — not
routed through `src/utils/resource_loader.py`.

### Reporting (`src/report/audit_log.py`)

Audit logging for every LLM-mode command (channel, command, target,
response, executed, provider). Only fed by the top-bar Execute /
`ConfirmationGate` path.

## Known live safety gaps (not yet fixed)

1. **`RawOutputTab` and LLM Mode are plain `InteractiveTerminal`s, zero gate
   involvement** — by explicit user request, not an oversight. So the only
   GUI path behind `ConfirmationGate` is the top-bar Execute button. The
   Wizard Console (`chain_wizard/`) has its own per-step "yes" confirmation
   built into the CLI, but that's a separate, self-contained safety check,
   not `ConfirmationGate`.
2. **`src/scripts/llm-tools-nmap.py`** registers `nmap_scan` etc. as `llm`
   CLI function-call tools — if ever loaded via `llm --functions` from
   inside the LLM Mode shell, the LLM could invoke `nmap` directly, bypassing
   all validation/scope checks. The script works standalone; nothing in the
   GUI auto-loads it, but a user typing the `llm --functions ...` command
   into the (ungated) LLM Mode shell themselves would activate it.
3. **Resource-driven migration is partial** — `src/utils/resource_loader.py`
   + `src/resources/*.json` work correctly, but most prompts,
   confirmation-box templates, validation-error text, and the LLM system
   prompt (`src/config.py`) remain hardcoded Python strings.

None of the above are Windows-Demo/platform limitations — they're
intentional trade-offs (#1) or wiring gaps (#2, #3). Treat `RawOutputTab`/
LLM Mode and `llm-tools-nmap.py`'s direct-execution capability as the
highest-priority items to reconsider before pointing this app at a real
target outside the demo.

## External tools

Cloned source under `tools/` (repo root, gitignored, reference-only — nmap,
thc-hydra, evil-winrm-py, ncrack, ncat-w32) is unrelated to what actually
runs; see `CROSS_PLATFORM_TERMINAL_PLAN.md`'s platform-routing table for the
real execution path.

### WSL2 Ubuntu (Windows) — current tool-runner

All six tools installed via `apt-get`/`gem` inside WSL Ubuntu:

| Tool | Install | Verified version |
|---|---|---|
| nmap | `sudo apt-get install -y nmap` | v7.98 |
| masscan | `sudo apt-get install -y masscan` | v1.3.2 |
| hydra | `sudo apt-get install -y hydra` | v9.6 |
| ncrack | `sudo apt-get install -y ncrack` | v0.7 |
| ncat | `sudo apt-get install -y ncat` (separate package — not bundled with Ubuntu's `nmap` apt package) | v7.98 |
| evil-winrm | `sudo apt-get install -y ruby ruby-dev && sudo gem install evil-winrm` | v3.9 |

`chain_wizard/` targets this tool set directly via `core/executor.py` — see
"Wizard / orchestration" above for how routing works without per-tool `wsl`
prefixing.

### Linux — native install

Same package set, installed natively (no WSL layer needed) — see
`README.md`'s install section.
