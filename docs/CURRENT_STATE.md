# TheRecon — Current Code State (Snapshot for AI)

This file is a **snapshot of what actually exists in the code right now**,
not a spec. For the normative rules the code is supposed to follow, read
`ARCHITECTURE.md`, `AI_DEVELOPMENT.md`, `Coding Standards.md`,
`Resource System.md`. For the GUI file/page map, read `GUI_MISSION_CONTROL.md`.
Update this file whenever the state below goes stale.

Last verified: 2026-07-26, branch `restyle-mission-control-gui` (rebuilt after
the "Wizard Console rebuilt as gated nmap→hydra wizard, hydra implemented"
pass — see `PROGRESS.md`, same date). **This supersedes the plain-bash-only
description of Wizard Console below where the two disagree — read the
`### Wizard / orchestration` and per-tool table sections carefully, they've
changed.**

## Entry point

`src/main.py` → applies `src/config.py` `STYLESHEET` → launches
`ReconMainWindow` (`src/ui/main_window.py`).

## Layer-by-layer, what's real vs stub

### GUI (`src/ui/`)

- `main_window.py` — main window assembly, title bar, Settings popup menu,
  wires `Sidebar.navigate` → `MainContentArea.stack`. Top-bar Execute
  (`_on_execute_clicked`/`_run_gated_command`) and the Wizard Console page
  (see below) are now the two GUI paths going through `ConfirmationGate` —
  top-bar feedback is `QMessageBox` dialogs, Wizard Console feedback is
  printed inline in its own scrollback (see "Known live safety gaps" below).
- `widgets.py` — `Sidebar`, `TopBar` (mission bar), all pages in
  `MainContentArea`, `wrap_in_terminal()` helper. **Raw Output and LLM Mode
  pages are plain `InteractiveTerminal` instances (real shell, ungated).
  Wizard Console (`wizard_tab`) is now `WizardTerminal`
  (`src/ui/wizard_terminal.py`) — a scripted, gated nmap/hydra wizard, not a
  shell.**
- `terminal.py` — `InteractiveTerminal`: single-view real shell via
  `QProcess` (WSL Ubuntu bash preferred on Windows, falls back to Git Bash,
  then PATH bash). User types directly into the scrollback (no separate
  input line), default text color throughout, no app-injected text of any
  kind. Used for Raw Output and LLM Mode pages only now.
- `wizard_terminal.py` (`WizardTerminal`) — **new**, the current Wizard
  Console page. Same scrollback-as-input UI pattern as `InteractiveTerminal`
  (single editable `QTextEdit`, `_input_start` guards past output) but it is
  a state machine, not a shell: target → scan profile → `ConfirmationGate`
  preview + exact `"yes"` → real `nmap` run via `QProcess` → parse open
  ports → `nmap.analyzer.recommend_next_tools()` maps ports to next-stage
  tools (resource-driven, `src/resources/nmap/service_tools.json`) → if
  hydra applies, a login/password/extra sub-wizard → `ConfirmationGate`
  again (masked) → real `hydra` run (routed through `wsl.exe -e hydra ...`
  on Windows, since no Windows-native hydra binary exists) → parse found
  credentials → if any, notes Evil-WinRM as the next stage (not yet
  executable — see per-tool table below). Full narrative in
  `PROGRESS.md`, "Wizard Console rebuilt as gated nmap→hydra wizard" entry.
- `wizard_console.py` (`WizardConsoleTab`) — an *older* gated Wizard Console
  attempt, predates `wizard_terminal.py`. **Not imported/used anywhere** —
  dead code, same status as `llm_mode.py`/`tool_selection.py`. Not deleted;
  kept per "don't delete without asking." Don't confuse this with the
  current `wizard_terminal.py`, which is a different, newer file.
- `llm_mode.py` (`LLMModeTab`) — dead code, not imported.
- `tool_selection.py` (`ToolSelectionTab`) — dead code, not imported; still
  contains inline ncat/evil-winrm/ncrack command-building logic that was
  never moved into the per-tool `builder.py` files.

Sidebar has 6 pages (index 0–5): Wizard Console, Input Management, Command
Editor, Raw Output, Results Display, LLM Mode. Tool Selection was removed
from navigation. Raw Output and LLM Mode (indices 3, 5) are plain bash
terminals; Wizard Console (index 0) is the gated `WizardTerminal`. Details of
every page/attr are in `GUI_MISSION_CONTROL.md` — that file predates the
`WizardTerminal` change and still describes Wizard Console as plain bash; it
needs updating too, treat this file as authoritative for Wizard Console until
that's done.

### Wizard / orchestration

Two separate things exist under this heading, don't conflate them:

- **`src/ui/wizard_terminal.py` (`WizardTerminal`, ~400 lines) — the live
  Wizard Console page, actually wired in.** Tool-aware by design (nmap then
  hydra), calls the real `ConfirmationGate`, calls nmap's and hydra's real
  builder/validator/parser/analyzer modules directly rather than going
  through `src/wizard/engine.py`. This is the code path described in the
  "Wizard / orchestration" bullet further up this file and in
  `PROGRESS.md`.
- **`src/wizard/engine.py` (1006 lines) — NOT wired into the GUI at all.**
  Single large state-machine file, predates `wizard_terminal.py`. Directly
  imports nmap's builder/validator/analyzer (tool-aware, not tool-agnostic
  as the architecture spec wants). Hand-builds hydra/evil-winrm command
  strings inline instead of calling their builders. Its main nmap confirm
  flow **reimplements** `ConfirmationGate`'s logic rather than calling it,
  and as a result skips `is_target_in_scope`. Nothing in the current GUI
  calls into this file — it's dead code in practice, same status as
  `wizard_console.py`, just not formally deprecated. Don't extend it; extend
  `wizard_terminal.py` instead.

### Validation (`src/validation/common.py`, 204 lines)

Shared validation: command-line parsing, exact-confirmation check
(`"yes"` literal match), etc. Used correctly by `ConfirmationGate`.

### Command builders (`src/tools/<tool>/`)

All 6 tools have the full 4-file layout (`builder.py`, `validator.py`,
`parser.py`, `analyzer.py`, `__init__.py`) per the Windows-Demo architecture
rule — none are skipped. Depth of real implementation varies sharply:

| Tool | builder | validator | parser | analyzer | Status |
|---|---|---|---|---|---|
| **nmap** | real (`build_nmap_command`, `shlex`-quoted) | real | real (`parse_open_ports`) | real (+ `recommend_next_tools`) | Fully implemented, wired into `WizardTerminal` |
| **hydra** | real (`HydraSpec`, `build_hydra_argv`/`build_hydra_command` w/ password masking) | real (service whitelist, login/password file-vs-value detection, `-e` letters) | real (credential-line regex, `count_valid_credentials`) | real (brute-force impact text) | Fully implemented, wired into `WizardTerminal`; executes via `wsl.exe -e hydra ...` on Windows (no native Windows binary — installed in WSL, `apt-get install hydra`, v9.6) |
| masscan | 20 | 18 | 19 | 18 | Placeholder/TODO stubs |
| ncat | 21 | 17 | 17 | 18 | Placeholder/TODO stubs |
| ncrack | 22 | 17 | 17 | 18 | Placeholder/TODO stubs; mapped as a chain target in `service_tools.json` (RDP) but nothing executes it yet |
| evil_winrm | 27 | 17 | 20 | 18 | Placeholder/TODO stubs — **next chain stage to build**; `WizardTerminal` currently only prints what the evil-winrm command *would* be after hydra finds a credential, doesn't run it |

`TOOL_ENABLEMENT` in `src/config.py`: `nmap`/`hydra` now `True`, `ncat`/
`evil-winrm`/`ncrack` `True` (execution-availability flag, separate from the
"is the builder real" question above), `masscan` `False`.

nmap and hydra are the two tools with a real, wired end-to-end path — nmap's
open ports feed `recommend_next_tools()`, which drives the wizard's
hydra sub-flow. Evil-WinRM is the next piece: `src/resources/nmap/
service_tools.json` already maps `wsman`/`microsoft-ds` ports to it, and
`WizardTerminal._maybe_offer_winrm()` already fires when hydra finds a
credential — it just prints the command instead of building/running it. The
remaining 2 tools (masscan, ncrack) have the correct module skeleton (per
`Resource System.md`'s Windows-Demo rule — intentional, not a bug) but no
real logic yet.

`src/tools/<tool>/resources/` subfolders exist but only hold `.gitkeep` —
not wired to anything; `src/utils/resource_loader.py` + `src/resources/*.json`
is the only active resource path.

### Confirmation gate (`src/core/confirmation_gate.py`, 149 lines)

The single human-in-the-loop safety gate. `request()` validates + builds a
preview only; `execute()` requires an exact literal `"yes"` reply. Supports
masking secrets via `argv_override`. Correctly used by `wizard_console.py`
and (partially — see gap above) bypassed by `wizard/engine.py`'s nmap path.

### Other core (`src/core/`)

- `tool_manager.py` (252 lines) — installed-tool detection.
- `auto_chain.py` (168 lines) — attack-chain automation.
- `api_key_manager.py` (171 lines) — LLM API key storage via `keyring`.

### Resources (`src/resources/*.json` + `src/utils/resource_loader.py`)

`resource_loader.py` (48 lines) is the only component allowed to `open()` a
resource JSON; `load_json()` caches and degrades to `{}` on missing/malformed
files. Covers wizard menu/messages, nmap scan profiles/flag impacts, common
warnings, and (new) `nmap/service_tools.json` — maps an open port's service
name (or port number as fallback) to the next-stage tool/module/reason used
by `WizardTerminal`'s chain menu (`nmap.analyzer.recommend_next_tools()`
reads it). Most prompt/dialog/validation-error text elsewhere (e.g.
`src/config.py`, 905 lines) is still hardcoded Python strings, not yet
migrated to resources — partial migration, not started-from-zero.

### Reporting (`src/report/audit_log.py`, 101 lines)

Audit logging for every LLM-mode command (channel, command, target,
response, executed, provider).

### Known live safety gaps (not yet fixed)

Carried over from the 2026-07-25 audit, updated as of this snapshot —
**gap #1 is now partially fixed**, the rest still stand:

1. ~~`RawOutputTab`, Wizard Console, and LLM Mode are all plain
   `InteractiveTerminal`s~~ **Partially fixed**: Wizard Console
   (`wizard_tab`) is now `WizardTerminal` — every command it runs (nmap,
   hydra) goes through validation + `build_*_command`/`build_*_argv` +
   `ConfirmationGate` (exact `"yes"`, password masking, audit log). Raw
   Output and LLM Mode (2 of the 6 sidebar pages) are still plain
   `InteractiveTerminal` real shells with zero gate involvement, by explicit
   user request. So the GUI paths behind `ConfirmationGate` are now: the
   top-bar mission-bar Execute button (`main_window._on_execute_clicked`)
   and the Wizard Console page.
2. ~~`main_window.py` re-pipes already-executed commands from wizard into
   `RawOutputTab` — risk of double execution.~~ **Fixed**: `RawOutputTab`
   no longer has `append_log()`/`set_running()`, nothing mirrors into any
   terminal anymore. Top-bar Execute's preview/result go to `QMessageBox`
   dialogs instead.
3. `src/scripts/llm-tools-nmap.py` (300 lines) registers `nmap_scan` etc. as
   `llm` CLI function-call tools — if `llm_mode.py`'s old `--functions` load
   path is ever re-enabled, the LLM could invoke `nmap` directly, bypassing
   `ConfirmationGate` and scope checks. Currently inert since `llm_mode.py`
   isn't imported, but the script itself still exists and works standalone.
4. `WizardConsoleTab` (`wizard_console.py`) — was previously "the real gated
   Wizard Console logic, actually wired in." **No longer wired in at all**
   as of the plain-bash pass — `wizard_tab` is now `InteractiveTerminal`.
   The file/class still exists (dead code, not deleted) but nothing in the
   GUI reaches it, so its gated behavior is moot until/unless it's re-wired.
5. `wizard/engine.py` reimplements confirmation logic instead of calling
   `ConfirmationGate`, skipping `is_target_in_scope` — moot for the same
   reason as #4 (nothing in the GUI currently calls into `wizard/engine.py`
   either), but the gap is still real in the code if it's re-wired later.
6. `tool_selection.py` builds ncat/evil-winrm/ncrack commands inline instead
   of via their builders — moot right now since the tab isn't in the
   sidebar, but the logic exists and works if someone re-adds it.

None of these are Windows-Demo/platform limitations — they are logic/wiring
gaps, and #1 is now an intentional, user-requested trade-off rather than an
oversight. Treat the Wizard Console/Raw Output/LLM Mode terminals and
`llm-tools-nmap.py` as highest priority to reconsider before pointing this
app at a real target outside the demo.

## External tools (Windows demo, `tools/` — gitignored, not vendored)

Cloned source (read/reference only, not built from):

- `tools/nmap` — github.com/nmap/nmap
- `tools/thc-hydra` — github.com/vanhauser-thc/thc-hydra
- `tools/evil-winrm-py` — github.com/adityatelange/evil-winrm-py
- `tools/ncrack` — github.com/nmap/ncrack
- `tools/ncat-w32` — gitlab.com/kalilinux/packages/ncat-w32

What's actually usable on this Windows machine right now:

| Tool | Install method | Status |
|---|---|---|
| nmap | pre-existing / winget `Insecure.Nmap` | ✅ v7.98 on PATH |
| ncat | bundled with nmap | ✅ on PATH (`ncat.exe`) |
| evil-winrm-py | `pip install evil-winrm-py` | ✅ v1.6.0 installed; console scripts (`evil-winrm-py.exe`, `ewp.exe`) not yet on PATH |
| ncrack | official installer `tools/ncrack-0.7-setup.exe` (nmap.org, v0.7, 2019 — last release, project effectively unmaintained) | downloaded, **not installed** — silent `/S` install didn't take (needs interactive/UAC run) |
| ncat-w32 | n/a | not needed — ncat already available via nmap bundle |
| thc-hydra | n/a | no official Windows binary; would need MSYS2/MinGW build or WSL — deferred, not attempted |

This table is about *runtime availability for the Windows demo*, separate
from the `src/tools/hydra/` etc. code-module status above — a tool can be
absent from the machine while its builder/validator/parser/analyzer module
skeleton still exists in the codebase (that's the whole point of the
Windows-Demo architecture rule).
