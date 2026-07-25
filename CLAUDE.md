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
```

There is no configured lint/test/build tooling in this repo (no pytest config, no linter config found) — do not invent commands for these.

## Required reading before structural changes

`docs/ARCHITECTURE.md` and `docs/Resource System.md` are the authoritative, mandatory specs for this project — read them before adding modules, tools, or layers. `docs/AI_DEVELOPMENT.md` and `docs/Coding Standards.md` carry AI-specific refactoring rules. `docs/CURRENT_STATE.md` is a snapshot of what's actually implemented vs. placeholder in the code right now (read this first in a fresh session — cheaper than re-deriving it). `docs/PROGRESS.md` is the running log of what's been done recently. `docs/GUI_MISSION_CONTROL.md` is the file/page map for the GUI specifically. Key points that aren't obvious from skimming the code:

- **Windows Demo is an execution profile, not an architecture limitation.** If a tool can't currently execute on this platform, still create the full module structure (`builder.py`, `validator.py`, `parser.py`, `analyzer.py`) with placeholder implementations and TODO docstrings — never skip or omit modules because execution is unavailable.
- **Resource-driven architecture**: menus, help text, warnings, impact descriptions, prompt templates, dialog text — all of it lives in `src/resources/*.json`, never hardcoded as Python string literals.

## Architecture

Fixed layer pipeline, no layer may skip another:

```
GUI (src/ui/) → Wizard/AI (src/wizard/, src/ui/llm_mode.py) → Validation (src/validation/)
  → Command Builder (src/tools/<tool>/builder.py) → Confirmation Gate (src/core/confirmation_gate.py)
  → Execution (QProcess) → Parser (src/tools/<tool>/parser.py) → Analysis (src/tools/<tool>/analyzer.py)
  → Report (src/report/)
```

Hard rules that hold across the codebase:
- Builders only build command objects; they never execute, parse, or touch the GUI.
- The GUI never builds commands or contains security/business logic.
- Validation always runs before a command is built; execution always runs behind the confirmation gate.
- Every supported tool (`src/tools/<tool>/`) has the same four-file layout: `builder.py`, `validator.py`, `parser.py`, `analyzer.py`, `__init__.py`.

### Key modules

- `src/main.py` — entry point, applies `src/config.py`'s `STYLESHEET`, launches `ReconMainWindow`.
- `src/config.py` — theme/color palette, window constants, `AUTHORIZED_SCOPE`.
- `src/core/confirmation_gate.py` — the single "human in the loop" safety gate every execution path (Wizard Console, LLM Mode Plain, LLM Mode AI) must go through. `request()` validates + builds a preview only; `execute()` is a separate step requiring an exact literal `"yes"` reply. Supports masking secrets (e.g. passwords) from the preview/audit log via `argv_override` while still executing the real argv.
- `src/core/auto_chain.py`, `src/core/tool_manager.py`, `src/core/api_key_manager.py` — attack-chain automation, installed-tool detection, and LLM API key storage (via `keyring`) respectively.
- `src/wizard/engine.py` — wizard state machine / workflow orchestration; must never execute subprocesses, parse output, or read resource files directly.
- `src/utils/resource_loader.py` — the *only* component allowed to `open()` a resource JSON file. Always go through `load_json()`; it caches results and degrades to `{}` on missing/malformed files rather than crashing.
- `src/validation/common.py` — shared validation: command-line parsing, exact-confirmation check, etc.
- `src/report/audit_log.py` — audit logging for every LLM-mode command (channel, command, target, response, executed, provider).
- `src/resources/` — JSON resource files (`wizard/menu.json`, `wizard/messages.json`, `nmap/scan_profiles.json`, `nmap/flag_impacts.json`, `common/warnings.json`).
- `src/tools/<nmap|masscan|ncat|hydra|ncrack|evil_winrm>/` — one package per supported tool, each with `builder.py` / `validator.py` / `parser.py` / `analyzer.py`. Each also has a `resources/` subfolder that currently only holds a `.gitkeep` placeholder — reserved for future per-tool resources; it is not yet wired up, so `src/resources/` + `src/utils/resource_loader.py` remain the only active resource path.
- `src/ui/` — `main_window.py` (layout), `widgets.py` (Sidebar/TopBar/Console), `wizard_console.py`, `tool_selection.py`, `llm_mode.py` (LLM-assisted command suggestion flow, gated by `confirmation_gate.py`).
- `src/scripts/llm-tools-nmap.py` — standalone tool functions (e.g. local network/interface discovery) exposed to the `llm` CLI plugin for LLM-assisted scan-range suggestions; not part of the GUI pipeline.

### AI/LLM integration rules (from docs/ARCHITECTURE.md §17)

AI may explain tools, recommend profiles/flags, summarize results. AI must never execute scans automatically, skip confirmation, bypass validation, or fabricate output. Every AI-suggested command passes through the same validation and `ConfirmationGate` as manually entered commands — no shortcut path exists or should be added.

## Notes on repo state

README.md's "Project Structure" and "Development" sections describe an older layout (`src/core/wizard_engine.py`, `src/core/tool_manager.py` as the wizard) that has since been restructured into `src/wizard/engine.py` + the per-tool `src/tools/<tool>/` packages described above — trust the architecture above and the actual source tree over the README when they conflict.
- `tools/` at repo root holds cloned external tool source (nmap, thc-hydra, evil-winrm-py, ncrack, ncat-w32) for Windows-demo reference/install — gitignored, not vendored into this repo, not part of the app's own architecture. See `docs/CURRENT_STATE.md` for what's actually installed/usable on the current machine.

## Known architecture/safety gaps (2026-07-25 audit)

An audit against docs/ARCHITECTURE.md, docs/Resource System.md, docs/AI_DEVELOPMENT.md, and docs/Coding Standards.md found the current refactor is structurally complete (all 6 tool packages have the full builder/validator/parser/analyzer layout; no circular imports; deleted wizard_engine.py/wizard_safety.py fully unreferenced) but has real safety and layering gaps — not yet fixed, flagged here so future work accounts for them:

- **`src/ui/widgets.py`'s `RawOutputTab`** spawns a raw powershell/bash shell and pipes text to it with zero validation, builder, or `ConfirmationGate` involvement — a full pipeline bypass. It's live and wired into `MainContentArea`.
- **`src/ui/main_window.py`** re-pipes already-executed commands from the wizard/LLM/tool-selection tabs into `RawOutputTab.write_command()`, causing double execution — once gated, once not.
- **`src/scripts/llm-tools-nmap.py`** registers `nmap_scan` etc. as `llm` CLI function-call tools that `src/ui/llm_mode.py` loads via `--functions` — the LLM can invoke `nmap` directly, bypassing `ConfirmationGate` and `is_target_in_scope` entirely.
- **`src/ui/widgets.py`** still contains and uses a duplicate legacy `WizardConsoleTab` (ungated); the properly-gated rewrite `src/ui/wizard_console.py` is dead code, never imported.
- **`src/wizard/engine.py`**'s main nmap confirm flow reimplements `ConfirmationGate`'s logic instead of calling it, and skips the `is_target_in_scope` check as a result.
- **`src/ui/tool_selection.py`** builds ncat/evil-winrm/ncrack commands inline instead of via their (currently-placeholder) `src/tools/<tool>/builder.py` modules.
- **`src/wizard/engine.py`** is nmap/hydra/evil-winrm-aware (imports nmap's builder/validator/analyzer directly, hand-builds hydra/evil-winrm command strings) rather than tool-agnostic.
- **Resource-driven migration is partial**: `src/utils/resource_loader.py` + `src/resources/*.json` work correctly, but most prompts, confirmation-box templates, validation-error text, tool descriptions, and the LLM system prompt (`src/config.py`) remain hardcoded Python strings rather than resources.

None of the above are Windows-Demo/platform limitations — they're logic/wiring gaps. Treat `RawOutputTab` and `llm-tools-nmap.py`'s direct-execution capability as the highest-priority items before this app is used against real targets.
