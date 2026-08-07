# TheRecon — Current Code State

**A snapshot of what's actually implemented and what every file does.** Written
for a fresh reader (human or AI) to understand the program without re-deriving
it from the source. For the *rules* to follow when changing it → `CLAUDE.md`.
For the *history* of how it got here → `PROGRESS.md`.

**Last verified:** 2026-08-07
**Branch:** feat/wizard-control-panel

---

## 1. What this program is

A **PySide6 desktop GUI + safety layer** wrapping six command-line security
tools: **nmap, masscan, hydra, ncrack, ncat, evil-winrm**. It does not
reimplement the tools — it builds commands, shows their impact, forces a human
confirmation, runs them in a real terminal, and parses the results.

- On **Windows**, the tools run inside **WSL2 (Ubuntu)**; the GUI runs on the
  Windows Python. On **Linux** the tools run natively.
- The whole thing is **restricted to those 6 tools** end-to-end: the validator
  whitelist, the installed-tool detector, the warhead profiles, and the wizard's
  attack map all agree on the same 6. Adding a 7th means wiring all of them.

### The pipeline (no layer skips another)

```
GUI (src/ui/)
  → Wizard panel / Direct Tool Mode
  → Validation (src/validation/common.py)
  → Confirmation Gate (src/core/confirmation_gate.py)   ← the single "yes" gate
  → Execution (terminal PTY / subprocess)
  → Parser (src/tools/<tool>/parser.py)
  → Results Display (src/ui/widgets/)
```

**Hard rule:** the GUI never builds commands or holds security logic; validation
always runs before a command is built; execution always runs behind the gate.

---

## 2. Quick reference

| Aspect | Where | Notes |
|--------|-------|-------|
| Entry point | `src/main.py` | splash → `ReconMainWindow` → preflight doctor |
| The safety gate | `src/core/confirmation_gate.py` | Direct Tool Mode Execute only |
| Guided wizard | `chain_wizard/` (repo root) | subprocess CLI, 6-tool restricted, self-confirming |
| Primary terminal | `src/ui/webterm/xterm_widget.py` | xterm.js + real PTY |
| Terminal fallback | `pty_terminal.py` → `terminal.py` | ConPTY+pyte → plain pipe |
| Command validation | `src/validation/common.py` | whitelist + injection guard |
| Resources | `src/resources/*.json` | menus/warheads/impacts — never hardcoded |
| Audit trail | `logs/audit_log.jsonl` | append-only, size-rotated |
| Tests | `tests/` | validators + gate (`python -m pytest tests/`) |

---

## 3. Startup sequence (`src/main.py`)

1. On Linux, set QtWebEngine software-render env flags (WSLg/headless hygiene).
2. Enable `faulthandler` → `logs/crash.log` (catches native SIGSEGV/SIGABRT).
3. Apply the theme from `src/config.py`, show a splash screen.
4. Build `ReconMainWindow`; keep the splash up until the Wizard Console's first
   terminal reports real PTY output (`firstTabReady`), max 20s.
5. ~2.5s after show, run the **preflight doctor** in a `QThread`; if anything's
   missing, pop a non-blocking warning. Silent when everything's fine.

---

## 4. The GUI — Sidebar pages (5)

Assembled by `src/ui/main_window.py` + the `src/ui/widgets/` package (split
2026-08-07 from a single `widgets.py`, one class per module: `sidebar.py`,
`topbar.py`, `dropdown.py`, `raw_output.py`, `results_display.py`,
`input_management.py`, `main_content.py`, `helpers.py`; the package `__init__`
re-exports every public name so `from src.ui.widgets import …` is unchanged).

### Page 0 — Wizard Console
Split layout: **control panel (left, 280px)** + **terminal tabs (right)**.
- **`WizardControlPanel`** (`src/ui/wizard_panel.py`) — a form: Target / Mode
  (AUTO·SEMI) / User + Pass wordlist (with Browse…) / Start scan. It only
  *collects* choices and emits `scanRequested(dict)`; it never builds or runs a
  command.
- **`TerminalTabsWidget(form_driven=True)`** (`src/ui/terminal_tabs.py`) —
  VS Code-style tabs. Before the first scan, a placeholder hint fills the pane.
  Start scan → the panel dict becomes CLI flags (`_panel_to_wizard_args`) →
  opens a Wizard tab running `chain_wizard/` with `--target/--mode/--wordlist`
  (skips the CLI's own prompts). `+`/`⌄` open more Wizard or Shell tabs (cap 4).

### Page 1 — Input Management (`InputManagementTab`)
Zenmap-style scan queue (Status / Command). Every Direct Tool Mode Execute lands
a row (Running → Done/Error). Double-click a row → its command goes back to the
top bar. Append opens a saved `-oX` XML; Remove / Cancel Scan act on rows.

### Page 2 — Raw Output (`RawOutputTab`)
Display-only terminal (xterm.js backend, `read_only=True`). Shows Direct Tool
Mode output. Every user keystroke is dropped before the PTY; only programmatic
injection (`write_text`/`run_command`) writes to it. This is the audit surface.

### Page 3 — Results Display (`ResultsDisplayTab`)
Zenmap-style split pane. Two data shapes:
- **Nmap/Masscan** → host/port table (from `-oX` XML).
- **Hydra/Ncrack** → separate credentials table (`kind: "credentials"`).

### Page 4 — LLM Mode (`TerminalTabsWidget(fixed=True)`)
Two fixed, square-block tabs, **ungated by design** (same trade-off as Raw
Output):
- **"LLM"** — `llm` CLI + `llm-tools-nmap` plugin (nmap function-calling).
- **"OpenCode"** — a coding agent, PATH-scoped to the 6 tools + read-only utils
  (soft confinement, not a sandbox).

### Title bar
- **Sidebar toggle** (left) — hides the sidebar + divider.
- **Settings dropdown** (right) — New/Stop Scan · Open/Save/Save-All Scan (XML) ·
  Set/Remove LLM API Key · Quit.
- **Close** — asks Yes/No; on Windows also runs `wsl.exe --shutdown` so the WSL2
  VM doesn't linger.

### Top bar (Direct Tool Mode)
- **TOOLS combo** — installed tools from `tool_manager`; selecting one
  repopulates the warhead list and fills the command box from `tool_commands.json`.
- **WARHEAD PROFILE combo** — per-tool profiles (2 stealth / 2 critical /
  2 quality) from `warheads/<tool>.json`.
- **TARGET field** — the user's own lab IP (`skip_scope=True`).
- **Execute** — the only GUI path through `ConfirmationGate`.

---

## 5. The terminal backend (3-tier fallback)

`terminal_tabs.make_terminal(profile, ...)` picks the first available:

1. **`XtermTerminal`** (`src/ui/webterm/xterm_widget.py`) — **primary**. xterm.js
   (VS Code's emulator) in a `QWebEngineView` + `QWebChannel` bridge, over a real
   PTY (ConPTY/`pywinpty` on Windows, stdlib `pty.fork` on Linux). Full IDE-grade
   terminal: reflow-on-resize, mouse select, copy/paste, curses apps. Vendored
   JS under `webterm/vendor/` (no CDN). Signals: `backendReady` (PTY spawned),
   `firstOutput` (first bytes — the "usable" signal the splash waits on).
2. **`PtyTerminal`** (`src/ui/pty_terminal.py`) — fallback. ConPTY + pyte → HTML
   in a `QTextEdit`. Color/sudo/TAB, but no reflow on resize.
3. **`InteractiveTerminal`** (`src/ui/terminal.py`) — last resort. Plain
   `QProcess` pipe, no TTY features.

**Windows launch:** `wsl.exe -e bash …` with **no `-d`** flag → uses the user's
default distro. WSL-side paths are derived at runtime from the repo location
(`_wsl_root_dir`, `_win_to_wsl_path`), never hardcoded to a dev machine.
`_wsl_available()` shows an "install WSL" placeholder if no real distro exists.

---

## 6. The safety layer

### `src/validation/common.py`
Tool-agnostic validators — they validate, never build or run.
- `parse_command_line()` — splits a command, enforces the **6-tool whitelist**
  (`ALLOWED_PROGRAMS`), allows a **bare `sudo` prefix** (no sudo flags) since
  masscan/nmap raw-socket flags need root in WSL.
- `_has_unquoted_shell_metachar()` — quote-aware injection guard. `;|&`$()<>\`
  are rejected only **outside** `'...'`/`"..."`, so hydra's quoted
  `http-post-form "…&pass=…"` payload passes while `foo; rm -rf /` doesn't.
- `convert_windows_paths_to_wsl()` — rewrites `C:\...` → `/mnt/c/...` (Windows
  only) before validation, since the command runs in WSL bash.
- `validate_exact_confirmation()` — only the literal string `"yes"` confirms.

### `src/core/confirmation_gate.py`
The single human-in-the-loop gate. **One instance per pending command**
(single-use). Two phases:
1. `request()` — validates, rewrites Windows paths, builds an impact preview via
   `nmap.analyzer`. **Never executes.** Supports `argv_override` to run the real
   argv while previewing/logging a **masked** command string (passwords hidden),
   and `skip_scope=True` for local targets. Appends a root-privilege warning when
   it detects a `sudo` prefix.
2. `confirm(reply)` — returns True only for exact `"yes"`; audit-logs the
   decision; marks the gate spent so a repeat `confirm("yes")` can't re-fire.

Only the top-bar **Direct Tool Mode Execute** path uses this gate
(`main_window._on_execute_clicked` → `_run_gated_command`). The Wizard Console
has its **own** per-step confirmation inside the `chain_wizard` CLI.

### `src/tools/nmap/analyzer.py`
Impact/risk text for the gate — `generate_impact_description(flags, target,
tool)` reads `src/resources/<tool>/flag_impacts.json` (all 6 tools have one),
`format_confirmation_box()`, `is_target_in_scope()`.

### `src/report/audit_log.py`
`audit_log_llm()` appends one line per gated decision to `logs/audit_log.jsonl`
(channel, command, target, response, executed, provider — **never secrets**).
Size-rotated (5 MB × 3 backups). Append-only compliance record; nothing reads it
back.

### `src/preflight.py`
Pure-stdlib dependency doctor. Verifies Windows Python has
PySide6/QtWebEngine/pywinpty, WSL has a real distro (not just Docker Desktop
stubs), the 6 tools are installed, and WSL's python3 is ≥3.10. Runs at startup
in a thread; runnable standalone (`python -m src.preflight`, exit code = problem
count).

---

## 7. Result parsers (`src/tools/`)

A `src/tools/<tool>/` package exists **only where something parses that tool's
output** — never scaffolded to preserve a layout.

- **`nmap/`** — `parser.py` (`parse_nmap_xml()`, also handles masscan's
  compatible `-oX` subset) + `analyzer.py` (above). Wired from
  `main_window._ingest_nmap_xml()`.
- **`hydra/`, `ncrack/`** — `parser.py` only. Regex-parse found credentials from
  `hydra -o` / `ncrack -oN` output into the credentials table.
- **`masscan`, `ncat`, `evil-winrm`** — no package (nothing parses their output;
  ncat/evil-winrm are interactive sessions).

**Auto-capture:** `main_window._scan_xml_capture_paths()` /
`_cred_capture_paths()` append the right output flag (`-oX` / `-o` / `-oN`) to a
bare invocation before confirmation, so results flow to Results Display without
the user remembering the flag.

---

## 8. The wizard CLI (`chain_wizard/`, repo root)

Self-contained Python package, **not** under `src/`, launched as a subprocess by
the Wizard Console. No imports from GUI code. Runs all 6 tools directly via
`subprocess` — it does **not** go through `src/tools/` or `ConfirmationGate`; it
carries its own per-step confirmation.

**Flow:** target → mode (AUTO/SEMI) → scan (nmap/masscan) → impact-ranked plan →
per-step confirm → execute → harvest credentials → in-scope post-exploit.

| Module | Purpose |
|--------|---------|
| `wizard/main.py` | Entry; prompts, or the GUI's `--target/--mode/--*-wordlist` preset; loop control |
| `wizard/chain.py` | Orchestration: scan → plan → confirm → run → parse creds → post-exploit |
| `wizard/pipeline.py` | `build_plan()` (AUTO/SEMI), `step_priority()` (impact ranking) |
| `library/scanner.py` | nmap quick/full/stealth + masscan |
| `library/attack_map.py` + `.json` | port → attack (which tool + command template) |
| `library/post_exploit.py` + `.json` | service → post-exploit action |
| `library/parser.py` | gnmap → `ScanResult` |
| `core/executor.py` | `subprocess.run(shell=True)`, routed by launcher context |
| `core/color.py`, `core/display.py` | ANSI color (off-TTY safe), adaptive banners |
| `core/models.py` | `Step`, `ScanResult`, `AttackPlan` dataclasses |

---

## 9. Resources (`src/resources/` + `src/utils/resource_loader.py`)

**Rule:** menus, warnings, profiles, impact text → JSON, never hardcoded.
`resource_loader.load_json()` is the *only* thing allowed to `open()` a resource
file; it caches and degrades to `{}` on missing/malformed files.

| File | Purpose |
|------|---------|
| `tool_commands.json` | One base command per tool (fills the command box) |
| `warheads/<tool>.json` (6) | 6 profiles per tool (2 stealth / 2 critical / 2 quality) |
| `<tool>/flag_impacts.json` (6) | Per-flag impact text for the confirmation box |

The wizard CLI has its own separate resources (`chain_wizard/library/*.json`),
not routed through `resource_loader`.

---

## 10. Other modules

- `src/theme.py` — the visual layer: window constants, color palette,
  `STYLESHEET`, terminal-font constants (split from `config.py` 2026-08-07).
- `src/config.py` — re-exports everything from `theme.py` (so `from src.config
  import PURPLE, STYLESHEET, …` is unchanged), and itself holds the
  resource-driven `TOOL_COMMANDS`/`WARHEAD_*` accessors + `AUTHORIZED_SCOPE`
  (`192.168.1.0/24`). `__all__` documents the public surface.
- `src/core/tool_manager.py` — installed-tool detection for the TOOLS combo.
- `src/core/llm_keys.py` — `set_llm_key` / `remove_llm_key` for the LLM Mode
  page (shells to the `llm` CLI). Kept out of `src/ui/` per the no-logic-in-GUI
  rule.

---

## 11. Tests (`tests/`)

`python -m pytest tests/` — 52 tests, no external target needed.
- **`test_validation.py`** — whitelist, 6 injection shapes, sudo handling,
  quote-aware scanner, exact-`yes`, Windows→WSL path rewrite.
- **`test_confirmation_gate.py`** — request/reject, scope enforce/bypass, exact
  `"yes"`, **single-use replay protection**, secret masking, cancel logging.
- **`conftest.py`** — puts the repo root on `sys.path`; stubs the audit logger
  so tests never write to `logs/`.

---

## 12. Known gaps & status

**Gated (safe):**
- ✓ Direct Tool Mode Execute — `ConfirmationGate` + exact `"yes"`.
- ✓ Raw Output — read-only, no keystroke reaches a shell.
- ✓ Wizard Console — per-step CLI confirmation.

**Ungated (intentional trade-offs, documented, not oversights):**
1. **LLM Mode** — two real shells, no gate. Review the threat model before real
   targets. OpenCode has soft PATH/dir confinement only.
2. **Direct Tool Mode uses `skip_scope=True`** — `AUTHORIZED_SCOPE` is not
   enforced on the main GUI path (targets are assumed to be the user's own lab).
   The gate is still the enforcement.

**Polish / open work (not safety):**
- Hardcoded UI strings remain in `config.py` / `main_window.py` (STYLESHEET,
  QMessageBox text) — partial resource migration.
- The wizard control panel has **not been run end-to-end in the full GUI on a
  real scan** yet (verified headless/argparse only).
- No web-application scanning capability (no dir-brute / web-vuln / SQLi tools) —
  the 6-tool set reaches the network/service layer only.

**Harmless leftover:** hard-killing the process mid-run on Linux (SIGTERM/
`timeout`) trips `QThread: Destroyed while thread is still running` → SIGABRT
during teardown (the PTY reader thread). A normal window close (`closeEvent`) is
clean — this only fires on `kill`-style termination.

---

## 13. Deleted / never-scaffolded (so nobody re-adds them)

- Old UI: `wizard_terminal.py`, `wizard_console.py`, `tool_selection.py`,
  `llm_mode.py`, `CommandEditorTab`, `src/wizard/engine.py`.
- Dead core: `auto_chain.py`, `api_key_manager.py`, the
  `llm-tools-nmap.py` direct-exec script.
- `nmap/builder.py` + `validator.py` (never wired).
- Cleaned 2026-08-07: `llm_keys.has_llm_key` (uncalled), an unused `QComboBox`
  import, `ACCENT_YELLOW`/`ACCENT_CYAN` constants, and `gobuster`/`dirb` from
  the validator whitelist (never wired anywhere).
- **Do not** scaffold `builder.py`/`validator.py`/`parser.py`/`analyzer.py`
  placeholders "to preserve the layout" — add a module only when something real
  will call it.
