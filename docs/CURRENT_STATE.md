# TheRecon — Current Code State (2026-08-05)

**Snapshot of actual implementation** (not a design spec). For architecture rules → `CLAUDE.md`. For activity log → `PROGRESS.md`.

**Last verified:** 2026-08-05  
**Branch:** main  
**Recent changes:** preflight doctor startup check, mission-bar UI polish, WSL shutdown on close, terminal robustness

---

## Quick Reference (AI scanning)

| Aspect | Status | Details |
|--------|--------|---------|
| **Entry** | src/main.py | → splash → ReconMainWindow → preflight health check |
| **Gating** | ConfirmationGate | Direct Tool Mode Execute only (top bar) |
| **Wizard** | chain_wizard/ | Subprocess CLI (6-tool restricted) |
| **Terminals** | XtermTerminal (primary) | xterm.js + real PTY; fallback: PtyTerminal → InteractiveTerminal |
| **LLM Mode** | Ungated (intentional) | Two fixed tabs: llm-nmap + opencode |
| **Safety** | Passed/Gated | Raw Output read-only; LLM Mode is trade-off |

---

## Entry Point

**Startup sequence:**
1. `src/main.py` — applies theme from `src/config.py`
2. Show splash screen (stays visible until Wizard Console ready, max 20s)
3. Launch `ReconMainWindow` (`src/ui/main_window.py`)
4. Wizard Console first tab: wait for real PTY output (`TerminalTabsWidget.firstTabReady`)
5. Hide splash once terminal is live

**Startup health check** (`src/preflight.py`, added 2026-08-05)
- Runs in QThread ~2.5s after window shows
- **Verifies (cross-platform):** Windows Python (PySide6/QtWebEngine/pywinpty), WSL installed + real distro, 6 tools in distro, WSL python3 ≥3.10
- **Detects:** missing/old WSL, tools not installed, python3 < 3.10, Microsoft Store stub
- **Behavior:** Silent if OK; non-modal warning if issues found (lists exact fixes)
- **Exit code:** number of problems (used by installers)
- **Standalone:** `python -m src.preflight` (pure stdlib, no exceptions)

---

## Sidebar Pages (5 total)

### Page 0: Wizard Console
- **Layout:** split — control panel (left, 268px) + terminal tabs (right), assembled by `widgets._wizard_console_page()`
- **Control panel:** `WizardControlPanel` (`wizard_panel.py`) — Target / Mode (AUTO·SEMI) / User+Pass wordlist / Start scan; emits `scanRequested(dict)`
- **Terminal:** `TerminalTabsWidget(form_driven=True)` (VS Code-style tabs)
  - **Backend:** `XtermTerminal` (xterm.js + real PTY) → `PtyTerminal` (pyte/ConPTY) → `InteractiveTerminal` (fallback)
  - **Before first scan:** no tab — a placeholder hint ("Fill in the panel… press Start scan") fills the pane; `firstTabReady` fires immediately so the startup splash doesn't wait on a tab that isn't coming yet
  - **Start scan:** panel dict → CLI flags (`start_wizard_scan` / `_panel_to_wizard_args`) → opens the first Wizard tab, hides the placeholder, runs `chain_wizard/` with `--target/--mode/--wordlist` (skips CLI prompts)
  - **Tabs:** `+`/`⌄` open more Wizard (interactive) or Shell tabs (max 4)

### Page 1: Input Management
- **Class:** `InputManagementTab`
- **View:** Zenmap-style scan queue (Status / Command columns)
- **Wired from:** Direct Tool Mode Execute; double-click → command back to top bar
- **Actions:** Append/Remove/Cancel Scan

### Page 2: Raw Output
- **Class:** `RawOutputTab` (xterm.js backend, read-only since 2026-08-01)
- **Display:** Direct Tool Mode Execute output only
- **Keystroke handling:** ALL user input dropped before PTY (read_only=True); only programmatic injection (`write_text`/`run_command`) works
- **Purpose:** Audit trail for gated commands

### Page 3: Results Display
- **Class:** `ResultsDisplayTab`
- **View:** Zenmap-style split pane
- **Data:** Nmap/Masscan results (host/port table) + Hydra/Ncrack credentials (separate table, `kind: "credentials"`)

### Page 4: LLM Mode
- **Class:** `TerminalTabsWidget(fixed=True, ...)`
- **Tabs:** 2 fixed square-block tabs (no `+`/`⌄`, no close)
  - **"LLM" tab:** llm-tools-nmap (cd `tools/llm-tools-nmap`, sets API key if needed)
  - **"OpenCode" tab:** scoped coding agent (PATH restricted to 6 tools + read-only utils)
- **Gating:** NONE (intentional, see "Known safety gaps")

**Removed:** Command Editor page (deleted 2026-07-31)

### Title Bar Controls

**Sidebar toggle** (left corner)
- Hides sidebar + divider (Claude Code style)

**Settings dropdown** (right menu)
- New Scan / Stop Scan
- Open Scan… / Save Scan… / Save All Scans…
- Quit
- Set LLM API Key… / Remove LLM API Key…

**File I/O**
- Save: exports selected Input Management row as minimal nmap XML (`<nmaprun args="…">`)
- Open: parses XML back into command box + TARGET field + adds Input Management row

**Close behavior** (added 2026-08-05)
- Prompts Yes/No confirmation
- On Windows: runs `wsl.exe --shutdown` (prevents lingering WSL2 VM in background)

### Top Bar (Command Area)

**TOOLS combo**
- Lists installed tools (from `ToolManager.get_tool_manager()`)
- Selecting tool → repopulates WARHEAD PROFILE from `WARHEAD_BY_TOOL[tool]`
- One base command per tool (from `tool_commands.json`)

**WARHEAD PROFILE combo**
- Per-tool profiles (2 stealth / 2 critical / 2 quality per tool)
- Previously: one shared nmap-based list; now: per-tool
- Populated dynamically when TOOLS changes

**TARGET field** (text input)
- User's lab IP for Direct Tool Mode Execute
- `skip_scope=True` (no cross-check against AUTHORIZED_SCOPE)

**Execute button** (gated)
- Only GUI path through `ConfirmationGate`
- Output shown in Raw Output tab + Input Management row marked Done/Error

### Terminal Backend (Fallback Chain)

**Tier 1: XtermTerminal (primary)**
- **Tech:** xterm.js (VS Code's terminal emulator) in QWebEngineView + QWebChannel bridge
- **PTY:** ConPTY (`pywinpty`) on Windows | stdlib `pty` fork on Linux
- **Launch:** `wsl.exe bash` (Windows, no `-d` → uses WSL default distro) | native bash (Linux)
- **UX:** Full IDE-grade terminal (reflow-on-resize, mouse select, copy/paste, curses apps vim/htop)
- **Assets:** Vendored JS under `webterm/vendor/` (xterm.js, addon-fit, qwebchannel.js) — no CDN
- **Readiness signals:** `backendReady` (PTY spawned, fast) | `firstOutput` (first bytes, means usable)
- **Guard:** `XTERM_AVAILABLE` (degrades if QtWebEngine/PTY missing)

**Tier 2: PtyTerminal (fallback)**
- **Tech:** ConPTY (`pywinpty`) + pyte VT emulator → HTML in QTextEdit
- **Launch:** `wsl.exe -e bash -lc "cd <wsl-repo> && python3 -m wizard.main"` (Windows)
- **UX:** Color, sudo, TAB completion; BUT no reflow on resize (truncates, not wraps)
- **Path handling:** `<wsl-repo>` derived at runtime from `terminal_tabs._wsl_root_dir()` (not hardcoded to `D:\TheRecon`)
- **Guard:** Falls back to InteractiveTerminal if `pywinpty`/`pyte` missing

**Tier 3: InteractiveTerminal (fallback)**
- **Tech:** `QProcess` (pipe, no TTY/PTY)
- **UX:** Plain text, no color/sudo/TTY features; Up/Down history
- **Fallback for:** All pages (Wizard, Raw Output, LLM Mode) when PTY unavailable

### TerminalTabsWidget (`terminal_tabs.py`)

**Structure** (added 2026-08-01)
- Generalized to support Wizard Console AND LLM Mode
- `profiles` parameter: `[(menu_label, profile_key, tab_name), ...]`
- Profiles: `"wizard"` | `"shell"` | `"llm-nmap"` | `"opencode"`
- Tab limit: `_MAX_TABS = 4` (real cost: each tab = QWebEngineView + PTY process)

**Fixed mode** (LLM Mode only)
- `fixed=True` → exactly 2 tabs pre-opened, no `+`/`⌄`/close (prevents OpenCode tab hang)
- Square-corner styling (`border-radius: 0`)

**WSL check** (Windows only)
- `_wsl_available()`: cached after first check
- Requires: `wsl.exe` on PATH + ≥1 real distro (excludes Docker Desktop pseudo-entries)
- Shows "install WSL" placeholder if check fails (never blank terminal)

**Paths** (Windows)
- `_wsl_root_dir()` → derived at runtime from repo location
- `_win_to_wsl_path()` → converts `C:\...` → `/mnt/c/...`
- NOT hardcoded to dev machine paths (fixed 2026-08-01 for cross-machine portability)

### Main Window & Top-Bar Execute

**`main_window.py`**
- Assembles window, title bar, Settings menu
- Wires Sidebar.navigate → MainContentArea.stack
- Top-bar Execute (`_on_execute_clicked` / `_run_gated_command`): **only** GUI path through ConfirmationGate
- Result: shown via QMessageBox dialogs (not mirrored to terminal)

---

### Deleted UI Files
- `wizard_terminal.py`, `wizard_console.py` (old wizard embedding)
- `src/wizard/engine.py` (old wizard logic)
- `tool_selection.py`, `llm_mode.py` (old modes)
- `CommandEditorTab` (old page index 2)

---

## Wizard CLI (`chain_wizard/`)

Self-contained Python package, subprocess-launched from Wizard Console.
Not under `src/` — no imports from GUI code.

**Flow:** target prompt → mode (AUTO/SEMI) → scan (nmap/masscan) → impact-ranked plan → per-step confirm → execute → harvest creds → post-exploit options

**Modules:**
| Module | Purpose |
|--------|---------|
| `wizard/main.py` | Entry, prompts (target/mode/wordlist), loop control (Ctrl-C restart, Ctrl-D exit) |
| `wizard/chain.py` | Orchestration: scan → plan → confirm → run → parse creds → offer post-exploit |
| `wizard/pipeline.py` | `build_plan()` (AUTO/SEMI), `step_priority()` (impact ranking) |
| `library/scanner.py` | Nmap quick/full/stealth (tunable `-T`) + masscan |
| `library/attack_map.py` + `.json` | Port → attack (credentials/exploitation) mapping |
| `library/post_exploit.py` + `.json` | Service → post-exploit action (ncat/nmap-NSE/evil-winrm) |
| `library/parser.py` | gnmap parsing → `ScanResult` dataclass |
| `core/executor.py` | `subprocess.run(shell=True)` — routing by launcher context (WSL vs native), not per-tool prefix |
| `core/color.py` | ANSI color (auto-disabled off-TTY) |
| `core/display.py` | Banner/sections, width adaptive (`shutil.get_terminal_size()`) |
| `core/models.py` | Dataclasses: `Step`, `ScanResult`, `AttackPlan` |

**Tools:** Restricted to 6 authorized tools (nmap, masscan, hydra, ncrack, ncat, evil-winrm)

---

## LLM Mode (Added 2026-08-01)

Two ungated real shells in fixed square-block tabs. **Intentional trade-off:** no ConfirmationGate (same as Raw Output).

### "LLM" Tab (`llm-nmap` profile)

- **Tool:** Simon Willison's `llm` CLI + `llm-tools-nmap` plugin
- **Location:** Auto-cd into `tools/llm-tools-nmap/` (cloned from GitLab, gitignored)
- **Functions:** nmap_scan, nmap_quick_scan, nmap_service_detection, nmap_os_detection, nmap_ping_scan, nmap_script_scan, get_local_network_info
- **API key setup:** Offers to run `llm keys set openai` if none stored; prints usage banner
- **Current model:** gemini-2.5-flash (free tier quota gated by project/region)

### "OpenCode" Tab (`opencode` profile)

- **Tool:** OpenCode coding agent CLI (official installer → `~/.opencode/bin/opencode`)
- **Scope:** Path-restricted to 6 tools + read-only utils (ls, cat, grep, find, head, tail, wc, file, mkdir, touch)
- **Workspace:** `tools/opencode-workspace/` (gitignored), contains auto-generated `AGENTS.md` (user-editable)
- **Controls (soft, not sandboxed):**
  - PATH rebuilt → `~/.recon_agent_bin/` symlinks only (absolute paths still reach filesystem)
  - `opencode` blocked from Shell/Raw Output via bash `DEBUG` trap (avoids ad-hoc invocation)
  - Tab dirs confined via PROMPT_COMMAND hook (soft lock)

**Fixes (2026-08-01):**
- **Exit loop:** Respawns OpenCode instead of falling through to bash (avoids `bash: not found`)
- **Ctrl+Z handling:** Dropped at Qt terminal level (`block_ctrl_z` flag) before reaching PTY (OpenCode TUI doesn't handle it properly)
- **WSL `-e` flag:** Explicit `--exec` added to all `wsl.exe bash` invocations (prevents silent variable loss)
- **Safety:** Added `$HOME` guard in PATH-scope rebuild (prevents catastrophic `rm -f /*` if $HOME empty)

### LLM API Key Manager (`src/core/llm_keys.py`)

- **GUI:** Settings ▸ Set LLM API Key… / Remove LLM API Key…
- **Scope:** Free-text provider (openai, gemini, custom plugins)
- **Implementation:** Shells to `llm keys set/list`, edits `keys.json` for removal
- **Constraint:** Must use `wsl.exe -e` (--exec) on Windows to preserve variable assignments

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

---

## Validation & Parsing (`src/tools/`, `src/validation/`)

### Nmap Analyzer (`src/tools/nmap/`)

**Files:** parser.py, analyzer.py, __init__.py

**Exports (used by ConfirmationGate):**
- `format_confirmation_box()` — formats impact warning dialog
- `generate_impact_description(flags, target, tool)` — impact text per-tool (reads `src/resources/<tool>/flag_impacts.json` — ALL 6 tools have entries now)
- `is_target_in_scope()` — scope check for gated execute

**Parser:** `parse_nmap_xml()` for Results Display
- Parses `-oX` output from nmap **or masscan** (masscan's schema is nmap-compatible subset)
- Never checks `scanner=` attribute — works for both tools
- Wired from `main_window._ingest_nmap_xml()`

### Credential Parsers (`src/tools/hydra/`, `src/tools/ncrack/`)

**Files:** parser.py + __init__.py (no builder/validator/analyzer — nothing calls those yet)

**Function:**
- Regex-parse hydra `-o <file>` / ncrack `-oN <file>` output
- Output: `[{host, port, service, login, password}, ...]`
- Fed to `ResultsDisplayTab.add_credential_results()`

**Auto-capture:** `main_window._cred_capture_paths()`
- Bare invocation (with optional `sudo`) + no output flag → auto-append `-o` / `-oN <scratch file>` before confirmation
- Mirrors `_scan_xml_capture_paths` for nmap/masscan

### Unused Tool Packages

`masscan`, `ncat`, `evil-winrm` have no `src/tools/` package (nothing needs to parse their output yet).
All 6 tools run directly via `chain_wizard/core/executor.py` (`subprocess.run(shell=True)`) — tool-specific modules only exist where GUI needs them.

### Validation (`src/validation/common.py`)

**Shared checks:**
- Command-line parsing (6-tool whitelist)
- Bare `sudo` prefix allowed (no other flags)
- Quote-aware metacharacter detection (`;|&`$()<>\` only flagged outside `'...'`/`"..."`)
- `convert_windows_paths_to_wsl()` — `C:\...` → `/mnt/c/...` (Windows only)
- Exact-confirmation check (`"yes"` literal match)

### Confirmation Gate (`src/core/confirmation_gate.py`)

**The single human-in-the-loop safety checkpoint.**

**Entry point:** Top-bar Execute button only
- `main_window._on_execute_clicked()` → `_run_gated_command()`
- Passes `skip_scope=True` (user's own lab IP in TARGET field)

**Two-phase design:**
1. `request()` — validates + builds impact preview (no execution)
2. `confirm("yes")` — requires exact literal `"yes"` reply to proceed

**Features:**
- Secret masking (via `argv_override`) — passwords hidden in preview/audit-log
- Audit logging → `logs/audit_log.jsonl` (JSONL format, size-rotated)
- Windows path translation (before validation)
- Sudo detection → appends root-privilege warning to impact text
- Tool name derivation (skips past `sudo` prefix for impact lookup)

**Output routing:**
- Result streamed to Raw Output tab
- Input Management row marked Done/Error on completion
- Result shown via QMessageBox dialogs (not mirrored to terminal)

**Note:** Wizard Console has its own per-step confirmation built into chain_wizard CLI — does NOT call ConfirmationGate

### Other core (`src/core/`, `src/preflight.py`)

- `tool_manager.py` — installed-tool detection (`get_tool_manager()`), used
  by the TopBar tool combo.
- `llm_keys.py` — Settings ▸ **Set LLM API Key…** / **Remove LLM API Key…**.
- `auto_chain.py` and `api_key_manager.py` were **deleted 2026-07-31** — dead
  code, nothing imported them (LLM Mode is a plain terminal now, no API-key
  UI; no auto-chain caller).

**`src/preflight.py`** (added 2026-08-05) — pure-stdlib dependency doctor,
verifies the app's cross-platform prerequisites. Checks: Windows Python has
PySide6/QtWebEngine/pywinpty, WSL has a real distro (not just Docker Desktop
pseudo-entries), the 6 tools are installed in the distro, WSL's python3 is ≥3.10
(for chain_wizard's PEP 604 unions), not the Microsoft Store stub. Runs at GUI
startup in a QThread (~2.5s after show) — fully set-up machines see nothing;
any gap pops a non-modal warning with install commands. Exit code = problem
count. Runnable standalone: `python -m src.preflight`.

---

## Resources (`src/resources/`, `src/utils/resource_loader.py`)

**Design rule:** All menus, help text, warnings, profiles, impact descriptions → JSON, never hardcoded strings.

**`resource_loader.py`**
- Only component allowed to `open()` resource JSONs
- `load_json()` caches + degrades to `{}` on missing/malformed files
- Safe (no exceptions at startup)

**Live resources (2026-08-01 onward):**

| File | Purpose | Scope |
|------|---------|-------|
| `<tool>/flag_impacts.json` (6 files) | Per-flag impact descriptions for confirm dialog | nmap, masscan, ncat, hydra, ncrack, evil-winrm |
| `tool_commands.json` | Base command template per tool (fills command box) | All 6 tools |
| `warheads/<tool>.json` (6 files) | Profile sets: 2 stealth / 2 critical / 2 quality per tool | All 6 tools |

**Wizard CLI resources (separate from GUI):**
- `chain_wizard/library/attack_map.json` — port → attack mapping
- `chain_wizard/library/post_exploit.json` — service → post-exploit action
- Not routed through `src/utils/resource_loader.py` (separate CLI resource system)

**Deleted (2026-07-31):**
- `wizard/menu.json`, `wizard/messages.json` (old wizard mode)
- `nmap/scan_profiles.json`, `nmap/service_tools.json` (old nmap mode)
- `common/warnings.json`

---

## Audit Logging (`src/report/audit_log.py`)

**File:** `logs/audit_log.jsonl` (JSONL, size-rotated)

**Format (each line):** channel, command, target, response, executed, provider (no secrets)

**Trigger:** ConfirmationGate path only (Direct Tool Mode Execute)

**Rotation:** 5 MB per file, 3 backups kept (.1/.2/.3), oldest dropped

**Compliance:** Append-only compliance record; nothing reads it back

---

## Known Safety Status

**Gated paths:**
- ✓ Direct Tool Mode Execute (top bar) — through ConfirmationGate + "yes" confirmation
- ✓ Raw Output tab — read-only since 2026-08-01 (no user keystroke reaches PTY)
- ✓ Wizard Console — per-step CLI confirmation (self-contained)

**Ungated paths (intentional trade-offs):**
1. **LLM Mode** — 2 real shells, no gate involvement
   - By design, not oversight
   - User can run arbitrary commands in llm-nmap + opencode tabs
   - Opencode has soft PATH/dir confinement (not sandboxed)
   - **Decision point:** before using on real targets, review threat model

2. **Hardcoded UI strings** — still in `config.py` + `main_window.py`
   - STYLESHEET, WINDOW_TITLE, color palette
   - QMessageBox text (Execute confirm dialog, close prompt)
   - Partial resource migration: `tool_commands.json`, `warheads/*.json`, `flag_impacts.json` moved (2026-08-01)
   - Not a safety gap (UI-only), just incomplete resource-driven architecture

**Closed gaps:**
- ✓ `llm-tools-nmap.py` script (deleted 2026-07-31) — was an orphaned direct-execution path

**Platform notes:** Neither remaining gap is Windows-Demo specific

---

## Tool Execution Environment

### Source Clones vs. Actual Tools

**Under `tools/` (repo root, gitignored, reference-only):**
- nmap, thc-hydra, evil-winrm-py, ncrack, ncat-w32 source
- NOT what runs (these are for reference/historical context)

**Actually wired into GUI (`tools/` but functional):**
- `tools/llm-tools-nmap/` — llm CLI plugin (LLM Mode tab)
- `tools/opencode-workspace/` — OpenCode's workspace (OpenCode tab + `AGENTS.md`)

### Windows (WSL2 Ubuntu)

**Platform routing:** Tools run **inside WSL2 Ubuntu**, GUI runs **on Windows Python**

**Installation (inside WSL):**

| Tool | Command | Version |
|------|---------|---------|
| nmap | `sudo apt-get install -y nmap` | v7.98 |
| masscan | `sudo apt-get install -y masscan` | v1.3.2 |
| hydra | `sudo apt-get install -y hydra` | v9.6 |
| ncrack | `sudo apt-get install -y ncrack` | v0.7 |
| ncat | `sudo apt-get install -y ncat` (separate pkg) | v7.98 |
| evil-winrm | `sudo gem install evil-winrm` (needs ruby/ruby-dev) | v3.9 |

**Invocation:** `wsl.exe bash -lc "cd <repo> && command"` (tools native in WSL context)

**Routing:** No per-tool `wsl.exe` prefix — where the CLI runs determines everything

### Linux (Native)

**Platform routing:** Tools run **natively**, no WSL layer

**Installation:** Same apt/gem commands, run directly in shell

**Invocation:** Just call tool by name (on PATH)

**Routing:** Same as Windows, but no WSL wrapping

**See also:** `README.md` for install commands
