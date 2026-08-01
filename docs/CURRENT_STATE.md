# TheRecon — Current Code State (Snapshot for AI)

This file is a **snapshot of what actually exists in the code right now**,
not a spec. For normative rules, read `CLAUDE.md`. For the current
Wizard Console embedding plan and remaining TODOs, read
`CROSS_PLATFORM_TERMINAL_PLAN.md`. Update this file whenever the state below
goes stale.

Last verified: 2026-08-01, branch `main`, after the sudo/cred-capture/
Results-Display-for-all-tools pass (see `PROGRESS.md`, "Sudo support,
per-tool warheads, Results Display for masscan/hydra/ncrack, splash screen").

## Entry point

`src/main.py` → applies `src/config.py` `STYLESHEET` → shows a splash
screen → launches `ReconMainWindow` (`src/ui/main_window.py`) → splash stays
up until the Wizard Console's first terminal reports real PTY output
(`TerminalTabsWidget.firstTabReady`), capped at 20s so a stuck WSL boot
can't hang it forever.

## Layer-by-layer, what's real vs stub

### GUI (`src/ui/`)

Sidebar has 5 pages (`Sidebar.NAV_ITEMS`, index 0–4), 1:1 with
`MainContentArea._build_pages()`:

| Index | Attr | Class | Notes |
|---|---|---|---|
| 0 | `wizard_tab` | `TerminalTabsWidget` — VS Code-style tabbed terminal; each tab is `XtermTerminal` (xterm.js in QWebEngineView + real PTY) → `PtyTerminal` (pyte/ConPTY) → `InteractiveTerminal`, first available wins | Wizard Console — first tab runs `chain_wizard/` CLI; `+`/`⌄` open more Wizard or plain Shell tabs, see below |
| 1 | `input_tab` | `InputManagementTab` | Zenmap-style scan queue (Status/Command). Direct Tool Mode Execute lands a row here; Append/Remove/Cancel Scan; double-click a row → command back to top-bar |
| 2 | `raw_output_tab` | `RawOutputTab` (wraps `make_terminal("shell")` — same xterm.js backend as Wizard) | real shell; also the live display surface for Direct Tool Mode Execute |
| 3 | `results_tab` | `ResultsDisplayTab` | Zenmap-style split view, starts empty. Two entry shapes now: nmap/masscan scan results (host/port table, unchanged) **and** hydra/ncrack found-credentials entries (`kind: "credentials"`, rendered as a Credentials Found table instead) |
| 4 | `llm_tab` | `InteractiveTerminal` | plain real shell for wiring up your own AI CLI, ungated |

The **Command Editor** page (old index 2, `CommandEditorTab`) was removed
2026-07-31.

**Title bar** carries a left-corner sidebar collapse toggle (fully hides the
sidebar + divider, Claude Code desktop-style) and a **Settings** dropdown
(New Scan / Stop Scan / Open Scan… / Save Scan… / Save All Scans… / Quit).
Open/Save round-trip a scan as minimal nmap XML (`<nmaprun args="…">`): Save
writes the selected Input Management row; Open parses the command back into
the top-bar command box + TARGET field and adds an Input Management row.
Closing the window (`closeEvent`) asks a Yes/No confirm, then on Windows
runs `wsl.exe --shutdown` — added 2026-08-01 because the old code left the
WSL2 VM running in the background after the app closed (killing the PTY's
`wsl.exe` client process doesn't stop the VM itself).

**TOOLS / WARHEAD PROFILE combos (top bar)** — warhead profiles are now
per-tool, not one shared nmap-flavored list: picking a tool in TOOLS calls
`TopBar.set_warhead_profiles(tool)`, which repopulates WARHEAD PROFILE from
`WARHEAD_BY_TOOL[tool]` (6 profiles per tool: 2 stealth / 2 critical / 2
quality). `TOOL_LIST` (a dead fallback — `ToolManager.tools` is never
empty, so the `else TOOL_LIST` branch could never run) was deleted
2026-08-01 along with the fallback branch that used it.

- `main_window.py` — main window assembly, title bar, Settings popup menu,
  wires `Sidebar.navigate` → `MainContentArea.stack`. Top-bar Execute
  (`_on_execute_clicked`/`_run_gated_command`) is the **only** GUI path that
  goes through `ConfirmationGate` directly — result is shown via
  `QMessageBox` dialogs, not mirrored into any terminal.
- `webterm/` (`XtermTerminal`) — **primary Wizard Console terminal.** xterm.js
  (the emulator VS Code ships) hosted in a `QWebEngineView`, bridged over
  `QWebChannel` to a real PTY: ConPTY (`pywinpty`) running `wsl.exe bash` on
  Windows (no `-d <distro>` — launches whatever the user's WSL *default*
  distro is, not hardcoded to "Ubuntu", since 2026-08-01), stdlib `pty` fork
  of `bash` on Linux. IDE-grade behavior — reflow-on-resize, mouse select,
  copy/paste, and full curses apps (vim/nano/htop/python). Vendored JS
  (xterm.js/addon-fit/xterm.css/qwebchannel.js) under `webterm/vendor/`, no
  CDN. `XTERM_AVAILABLE` guards the QtWebEngine + PTY imports; if either is
  missing it degrades to `PtyTerminal` then `InteractiveTerminal`. Two
  readiness signals: `backendReady` (PTY process spawned — fires fast,
  before WSL has actually finished booting) and `firstOutput` (first real
  bytes read back — this is the one that means "usable"; the startup
  splash in `src/main.py` waits on it via `TerminalTabsWidget.firstTabReady`).
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

`terminal_tabs.py` (`TerminalTabsWidget`) added 2026-08-01: `_MAX_TABS = 4`
caps how many terminal tabs (Wizard + Shell combined) can be open at once —
each is its own `QWebEngineView`/Chromium renderer process plus a real PTY,
so this is a real per-tab RAM/CPU cost, not a cosmetic limit. `+`/`⌄` disable
once at cap. `_wsl_available()` (Windows only, cached after first check) —
`wsl.exe` on PATH + at least one real distro registered (excludes the
`docker-desktop`/`docker-desktop-data` pseudo-entries Docker Desktop
registers) — shows a plain "install WSL" placeholder widget instead of a
silently-blank terminal if neither holds.

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
literal match), `convert_windows_paths_to_wsl()`. Used by `ConfirmationGate`.

Changed 2026-08-01:
- **Quote-aware dangerous-metacharacter check** — the old
  `DANGEROUS_SHELL_CHARS.search(command)` blocked `;|&`$()<>\` anywhere in
  the raw string, which rejected legitimate quoted data (e.g. hydra's
  `http-post-form "/login:user=^USER^&pass=^PASS^:F=X"` — the `&` there is
  literal, inside `"..."`). Replaced with `_has_unquoted_shell_metachar()`,
  a small char-by-char scanner that tracks `'...'`/`"..."` regions and only
  flags one of those characters when it's **outside** a quoted region.
  Security posture unchanged for the actual attack shapes (`foo; rm -rf /`,
  `foo | bar`, `foo & bg`, `` `cmd` ``, `$(cmd)` are still rejected) — this
  only stopped over-blocking safely-quoted data.
- **Bare `sudo` prefix allowed** — `parse_command_line()` now accepts
  `sudo <one of the 6 tools> ...` (masscan always needs raw sockets in WSL;
  nmap's `-sS`/`-O`/privileged ping probes do too, and `setcap` isn't
  always set up). Only the bare form is accepted — `sudo -u root nmap ...`
  or any other sudo flag is still rejected — so the elevated program is
  still exactly one of the 6 authorized tools, never sudo doing something
  else. `ConfirmationGate` appends an explicit "[!] running as root" line
  to the impact preview whenever this fires, so it's never silent.
- **`convert_windows_paths_to_wsl(command)`** — rewrites any `C:\...`-style
  path (quoted or bare) to its WSL mount-point form (`/mnt/c/...`). Called
  from `ConfirmationGate.request()` on Windows, before validation, so a
  wordlist/script path pasted from Windows Explorer doesn't trip the
  backslash-is-dangerous check and doesn't need manual translation.

### Command builders (`src/tools/`)

**`src/tools/nmap/`** (`parser.py`/`analyzer.py`/`__init__.py`). `analyzer`
(`format_confirmation_box`, `generate_impact_description(flags, target,
tool)`, `is_target_in_scope`) is imported directly by
`src/core/confirmation_gate.py` — `generate_impact_description` is no
longer nmap-only, it takes a `tool` argument and reads
`src/resources/<tool>/flag_impacts.json` (all 6 tools now have one).
`parser.py::parse_nmap_xml()` is called by `main_window._ingest_nmap_xml()`
to feed Results Display from a Direct Tool Mode **nmap or masscan** scan's
`-oX` output — `parse_nmap_xml` never actually checks `scanner=`, it just
walks `<host>`/`<address>`/`<ports>`/`<port>`, and masscan's `-oX` schema is
a compatible subset of nmap's, so the same parser reads both.
`builder.py`/`validator.py` — never wired into anything, dead weight —
were **deleted 2026-08-01**.

**`src/tools/hydra/parser.py`** and **`src/tools/ncrack/parser.py`** —
added 2026-08-01 (only `parser.py` + `__init__.py`, no
`builder`/`validator`/`analyzer` — nothing calls those). Regex-parse each
tool's own found-credentials output file
(`hydra -o <file>` / `ncrack -oN <file>`) into
`[{host, port, service, login, password}, ...]`, fed into
`ResultsDisplayTab.add_credential_results()`. Auto-capture wiring lives in
`main_window._cred_capture_paths()` (mirrors `_scan_xml_capture_paths` for
nmap/masscan) — a bare hydra/ncrack invocation (optionally `sudo`-prefixed)
with no output flag of its own gets `-o`/`-oN <scratch file>` appended
before the confirmation preview is built.

`masscan`, `ncat`, `evil_winrm` still have no `src/tools/` package — nothing
calls one yet. `chain_wizard/` calls all 6 tools directly via
`core/executor.py` (`subprocess`, `shell=True`), not through these
packages, regardless.

### Confirmation gate (`src/core/confirmation_gate.py`)

The single human-in-the-loop safety gate. `request()` validates + builds a
preview only; `confirm("yes")` requires an exact literal `"yes"` reply.
Supports masking secrets via `argv_override`. Reached only by the top-bar
Direct Tool Mode Execute button (`main_window._on_execute_clicked` →
`_run_direct_command`), which passes `skip_scope=True` (the user types their
own lab IP into TARGET) and then streams the command into the Raw Output
terminal, marking the Input Management row Done/Error on completion. The
Wizard Console does its own per-step confirmation inside the CLI itself and
does not call into this class.

Added 2026-08-01: on Windows, `request()` runs
`convert_windows_paths_to_wsl()` on the command before validation; detects
a `sudo`-prefixed command and both derives the correct tool name for
`generate_impact_description` (skipping past `sudo`) and appends a root-
privilege warning line to the impact text.

### Other core (`src/core/`)

- `tool_manager.py` — installed-tool detection (`get_tool_manager()`), used
  by the TopBar tool combo.
- `auto_chain.py` and `api_key_manager.py` were **deleted 2026-07-31** — dead
  code, nothing imported them (LLM Mode is a plain terminal now, no API-key
  UI; no auto-chain caller).

### Resources (`src/resources/*.json` + `src/utils/resource_loader.py`)

`resource_loader.py` is the only component allowed to `open()` a resource
JSON; `load_json()` caches and degrades to `{}` on missing/malformed files.
The old wizard/tool-selection resources (`wizard/menu.json`,
`wizard/messages.json`, `nmap/scan_profiles.json`, `nmap/service_tools.json`,
`common/warnings.json`) were deleted 2026-07-31 — nothing loaded them after
the `chain_wizard/` rewrite.

Live resources as of 2026-08-01 (moved out of hardcoded `config.py` dicts,
one commit at a time):
- **`<tool>/flag_impacts.json`** — 6 files now (`nmap/`, `masscan/`, `ncat/`,
  `hydra/`, `ncrack/`, `evil-winrm/`), read by
  `nmap.analyzer.generate_impact_description(flags, target, tool)`. Every
  tool gets real per-flag confirmation-box warnings now, not just nmap.
- **`tool_commands.json`** — `{"commands": {tool: base_command_template}}`,
  one entry per tool (`config.TOOL_COMMANDS`), fills the command box when a
  TOOLS combo entry is picked.
- **`warheads/<tool>.json`** — 6 files, one per tool, `{profile_name:
  command}`, 6 profiles each (2 stealth / 2 critical / 2 quality-normal).
  `config.py` loads all 6 into `WARHEAD_BY_TOOL` (keyed by tool) and
  flattens into `WARHEAD_COMMANDS` (safe — every profile name is already
  tool-prefixed, so it's unique across tools) for `_on_warhead_change`'s
  lookup. `TopBar.set_warhead_profiles(tool)` repopulates the WARHEAD
  PROFILE combo from `WARHEAD_BY_TOOL[tool]` whenever TOOLS changes.

`chain_wizard/library/attack_map.json` and `post_exploit.json` are a
separate, resource-driven data source specific to the wizard CLI — not
routed through `src/utils/resource_loader.py`.

### Reporting (`src/report/audit_log.py`)

`audit_log_llm()` appends every gated Direct Tool Mode Execute to
`logs/audit_log.jsonl` (channel, command, target, response, executed,
provider — never a secret). Only fed by the `ConfirmationGate` path; nothing
reads it back (it is the compliance record). The old
`audit_log_confirmation/cancel/fallback` variants were removed as dead code.

## Known live safety gaps (not yet fixed)

1. **`RawOutputTab` and LLM Mode are plain terminals, zero gate involvement**
   — by explicit user request, not an oversight. The only GUI path behind
   `ConfirmationGate` is the top-bar Direct Tool Mode Execute button (which
   then displays its output in Raw Output). The Wizard Console
   (`chain_wizard/`) has its own per-step "yes" confirmation built into the
   CLI, a separate, self-contained safety check.
2. **Resource-driven migration is narrower now, not closed** — `tool_commands.json`,
   `warheads/*.json`, and `flag_impacts.json` (all 6 tools) moved out of
   `config.py` 2026-08-01. Still hardcoded there: `STYLESHEET`,
   `WINDOW_TITLE`, color palette, and the `QMessageBox` prompt/confirmation
   text in `main_window.py` (e.g. the Execute confirmation dialog body, the
   close-confirmation prompt) — none of that is resource-driven yet.

The old `llm-tools-nmap.py` direct-execution gap was **closed 2026-07-31** by
deleting the script (it was orphaned and never GUI-loaded). Neither remaining
gap is a Windows-Demo/platform limitation — #1 is an intentional trade-off,
#2 is a migration gap, now smaller than before. Reconsider #1 before pointing
this app at a real target outside the demo.

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
