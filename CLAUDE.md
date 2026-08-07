# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TheRecon is a PySide6 desktop GUI for orchestrating network reconnaissance / security-testing tool chains (Nmap, Masscan, Ncat, Hydra, Ncrack, Evil-WinRM). It offers a guided Wizard Mode, a Direct Tool Mode, an LLM-assisted mode, and pre-built "Warhead Profile" scans. Authorized security testing only — every execution path requires explicit human confirmation before a command runs.

## Commands

```bash
# Run the app (from project root)
python -m src.main

# Install deps
pip install -r requirements.txt

# Startup dependency doctor (WSL + 6 tools + Python runtimes), runnable standalone
python -m src.preflight

# Tests — validators + confirmation gate (no external target needed)
python -m pytest tests/ -q
```

Tests live in `tests/` (pytest, added 2026-08-07) and cover the safety-critical paths: the 6-tool whitelist, quote-aware injection guard, exact-`yes` rule, Windows→WSL path rewrite, scope enforcement, single-use gate, secret masking. There is no linter/build tooling configured (no linter config) — do not invent commands for those.

## Required reading before structural changes

`docs/ARCHITECTURE.md`, `docs/Resource System.md`, `docs/AI_DEVELOPMENT.md`, and `docs/Coding Standards.md` (the original normative specs) have been removed — their load-bearing rules are folded into this file's `## Architecture` section below and into the docs that remain. **Start with `docs/CURRENT_STATE.md`** — a snapshot of what's actually implemented vs. placeholder, including live safety gaps and cross-platform terminal design (read this first in a fresh session — cheaper than re-deriving it). `docs/PROGRESS.md` is the running log of what's been done recently. Key points that aren't obvious from skimming the code:

- **Windows Demo is an execution profile, not an architecture limitation.** If a tool can't currently execute on this platform, that's fine — but don't scaffold `builder.py`/`validator.py`/`parser.py`/`analyzer.py` placeholders that nothing ever calls "to preserve the layout." `src/tools/nmap/builder.py` and `validator.py` were exactly that (never imported by anything, dead since day one) and were deleted 2026-08-01. Only add a module in `src/tools/<tool>/` once something real is going to call it.
- **Resource-driven architecture**: menus, help text, warnings, impact descriptions, prompt templates, dialog text — all of it lives in `src/resources/*.json`, never hardcoded as Python string literals.

## Architecture

Fixed layer pipeline, no layer may skip another:

```
GUI (src/ui/) → Wizard panel / Direct Tool Mode → Validation (src/validation/)
  → Confirmation Gate (src/core/confirmation_gate.py)
  → Execution (terminal PTY / subprocess) → Parser (src/tools/<tool>/parser.py) → Analysis (src/tools/<tool>/analyzer.py)
  → Results Display (src/ui/widgets.py)
```

Hard rules that hold across the codebase:
- The GUI never builds commands or contains security/business logic.
- Validation always runs before a command is built; execution always runs behind the confirmation gate.
- `src/tools/` packages only exist where something real calls them — never scaffolded "to preserve a layout". Currently: `nmap/` (`parser.py`, `analyzer.py`), and, added 2026-08-01 once Direct Tool Mode Execute needed to feed Results Display's Credentials Found view, `hydra/` and `ncrack/` (`parser.py` only — no `builder`/`validator`/`analyzer`, because nothing calls those yet). `masscan/ncat/evil_winrm` still have no `src/tools/` package. The live wizard `chain_wizard/` runs all 6 tools directly regardless, not through these packages.

### Key modules

- `src/main.py` — entry point, applies `src/config.py`'s `STYLESHEET`, shows a splash screen (kept up until the Wizard Console's first terminal reports real PTY output via `firstTabReady`/`firstOutput`, not just widget construction — WSL's own boot can lag behind that), then launches `ReconMainWindow`.
- `src/config.py` — theme/color palette, window constants, `AUTHORIZED_SCOPE`.
- `src/core/confirmation_gate.py` — the single "human in the loop" safety gate. The top-bar **Direct Tool Mode** Execute path goes through it: `request()` validates + builds a preview only; `confirm("yes")` requires an exact literal `"yes"` reply. Supports masking secrets (e.g. passwords) from the preview/audit log via `argv_override` while still executing the real argv. Direct Tool Mode passes `skip_scope=True` (target is the user's own lab IP, typed into the TARGET field). On Windows, `request()` also rewrites any `C:\...` path in the command to its WSL form (`/mnt/c/...`, via `validation.common.convert_windows_paths_to_wsl`) before validation ever runs — the command actually executes inside WSL bash, which has no drive letters. Detects a bare `sudo` prefix (masscan/nmap raw-socket flags need root in WSL) and appends an explicit root-privilege warning to the impact preview. Impact text is generated per-tool (`generate_impact_description(flags, target, tool)`), not nmap-only.
- `src/core/tool_manager.py` — installed-tool detection (`get_tool_manager()`), used by the TopBar tool combo.
- `src/utils/resource_loader.py` — the *only* component allowed to `open()` a resource JSON file. Always go through `load_json()`; it caches results and degrades to `{}` on missing/malformed files rather than crashing.
- `src/validation/common.py` — shared validation: command-line parsing, exact-confirmation check, `convert_windows_paths_to_wsl()`. The dangerous-shell-metacharacter check is quote-aware (`_has_unquoted_shell_metachar`) — `;`/`&`/`|`/`` ` ``/`$`/`()`/`<>`/`\` are only rejected when they appear *outside* a `'...'`/`"..."` region, so e.g. hydra's `http-post-form "...&pass=..."` payload passes while an unquoted `foo; rm -rf /` still doesn't. `parse_command_line()` allows a bare `sudo` prefix (no sudo flags) ahead of one of the 6 allowed programs.
- `src/report/audit_log.py` — `audit_log_llm()`: append-only JSONL safety trail (`logs/audit_log.jsonl`) for every gated Direct Tool Mode Execute (channel, command, target, response, executed, provider). Nothing reads it back; it is the compliance record. Size-based rotation (5 MB/file, 3 backups kept as `.1`/`.2`/`.3`) added 2026-08-01 so it doesn't grow unbounded — oldest backup is dropped, never the live file mid-write. (Kept deliberately; the old `audit_log_confirmation/cancel/fallback` variants + the `auto_chain.py`/`api_key_manager.py` modules that used them were removed as dead code.)
- `src/resources/` — `tool_commands.json` (one base command template per tool, GUI TOOLS combo) and `warheads/<tool>.json` (6 files, 6 profiles each — 2 stealth / 2 critical / 2 quality — WARHEAD PROFILE combo, repopulated per-tool by `TopBar.set_warhead_profiles()`) both loaded via `config.py`'s `TOOL_COMMANDS`/`WARHEAD_BY_TOOL`/`WARHEAD_COMMANDS`. `flag_impacts.json` now exists for all 6 tools (`nmap/`, `masscan/`, `ncat/`, `hydra/`, `ncrack/`, `evil-winrm/`), read by `nmap.analyzer.generate_impact_description(flags, target, tool)` — every tool gets real per-flag confirmation-box warnings, not just nmap. The old wizard/tool-selection resources (`wizard/menu.json`, `wizard/messages.json`, `nmap/scan_profiles.json`, `nmap/service_tools.json`, `common/warnings.json`) stay deleted — the live wizard carries its own JSON.
- `src/tools/nmap/` — `parser.py` / `analyzer.py` / `__init__.py`. `analyzer` is imported by `src/core/confirmation_gate.py` (`format_confirmation_box` / `generate_impact_description` / `is_target_in_scope`) for the Direct Tool Mode Execute path; `parser.py::parse_nmap_xml()` is called by `main_window._ingest_nmap_xml()` to populate Results Display from a completed nmap **or masscan** scan's `-oX` file (masscan's -oX schema is a compatible subset of nmap's — `parse_nmap_xml` never checks `scanner=`, so one parser covers both; `main_window._scan_xml_capture_paths()` auto-appends `-oX` to a bare nmap/masscan invocation). `builder.py`/`validator.py` — never wired into anything — were deleted 2026-08-01.
- `src/tools/hydra/parser.py` / `src/tools/ncrack/parser.py` — added 2026-08-01, regex-parse each tool's own found-credentials output (`hydra -o <file>`, `ncrack -oN <file>`, both auto-appended by `main_window._cred_capture_paths()` the same way `-oX` is for nmap/masscan) into Results Display's separate "Credentials Found" view (`widgets.ResultsDisplayTab.add_credential_results()` / `_render_credentials_detail()` — a differently-shaped entry, not a host/port table). `masscan`/`ncat`/`evil_winrm` still have no `src/tools/` package; ncat/evil-winrm are interactive sessions with no structured result to parse.
- `src/ui/` — `main_window.py` (layout, title-bar Settings dropdown + sidebar toggle, Direct Tool Mode Execute → Raw Output, Open/Save scan XML, `closeEvent` asks Yes/No then on Windows runs `wsl --shutdown`), `widgets.py` (Sidebar/TopBar/`InputManagementTab` scan queue/`RawOutputTab`/`ResultsDisplayTab`), `terminal.py` (plain-pipe `InteractiveTerminal`), `terminal_tabs.py` (`TerminalTabsWidget` — PyCharm-style tab bar for the Wizard Console; capped at `_MAX_TABS = 4` open at once; `_wsl_available()` shows a plain "install WSL" placeholder instead of a blank terminal when no distro is registered, never hardcoded to a distro name — launches via `wsl.exe` with no `-d` flag so whatever the user's default distro is gets used), `webterm/` (`XtermTerminal` — xterm.js in QWebEngineView + real PTY, the primary terminal backend), `pty_terminal.py` (`PtyTerminal` — pyte + ConPTY, legacy fallback). Sidebar pages are now 5 (Command Editor removed): Wizard Console / Input Management / Raw Output / Results Display / LLM Mode. See `docs/CURRENT_STATE.md`.
- **`chain_wizard/`** (repo root, NOT under `src/`) — the live chain wizard: scan → impact-ranked plan (AUTO/SEMI) → hydra brute → credential harvest/loot → in-scope post-exploit (ncat/nmap-NSE/evil-winrm). Self-contained Python, 6-tool-restricted, arsenal/post-exploit in JSON. This is the current Wizard Console.

### AI/LLM integration rules

AI may explain tools, recommend profiles/flags, summarize results. AI must never execute scans automatically, skip confirmation, bypass validation, or fabricate output. Every AI-suggested command passes through the same validation and `ConfirmationGate` as manually entered commands — no shortcut path exists or should be added.

## Notes on repo state

When any doc (README, older notes) conflicts with the architecture above or the actual source tree, trust the source tree.
- `tools/` at repo root holds cloned external tool source (nmap, thc-hydra, evil-winrm-py, ncrack, ncat-w32) for Windows-demo reference/install — gitignored, not vendored into this repo, not part of the app's own architecture. See `docs/CURRENT_STATE.md` for what's actually installed/usable on the current machine.

## Known live safety gaps

The old 2026-07-25 audit list is gone — nearly every file it named has been deleted. `docs/CURRENT_STATE.md`'s "Known live safety gaps" section is the single source of truth. In short, as of the 2026-07-31 cleanup: `RawOutputTab` and the LLM Mode page are plain, ungated terminals *by design* (the only gated GUI path is the top-bar Direct Tool Mode Execute → `ConfirmationGate`); the `llm-tools-nmap.py` direct-execution script was **removed**, closing that bypass. Read `docs/CURRENT_STATE.md` before pointing this app at a real target.
