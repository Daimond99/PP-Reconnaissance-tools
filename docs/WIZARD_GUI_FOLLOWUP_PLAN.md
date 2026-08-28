# Wizard Console — remove the black console-styled panel (follow-up)

## Context

2026-08-27: Wizard Console was rewritten so every menu/confirmation is a
real Qt dialog instead of typed terminal text — see `docs/PROGRESS.md`'s
"2026-08-27 — Wizard Console: full Qt-dialog rewrite, no terminal/CLI"
entry and `docs/CURRENT_STATE.md` §4/§8 for the full architecture
(`chain_wizard/core/ui_driver.py`, `src/core/wizard_driver.py`,
`src/ui/wizard_dialogs.py`, `src/ui/wizard_runner.py`).

**That part is done and correct — do not redo it.** The subprocess/JSON
protocol/dialog machinery works (unit-tested, real subprocess round-trip
verified). What's left is purely visual: the user (a professor's
requirement, relayed by the person running this session) wants **zero
terminal-styled surface anywhere on the Wizard Console page** — right now
`src/ui/wizard_runner.py`'s `WizardProgressView` is a `QTextEdit` styled to
look exactly like a black monospace console (`CONSOLE_BG`/`CONSOLE_TEXT`,
`font-family: Consolas, monospace` — see screenshot in the conversation
this plan came from: a black box sits where the terminal used to be, and
that's the objection even though nothing is actually typed into it).

## What to build instead

Replace `WizardProgressView` (`src/ui/wizard_runner.py`) with a real
structured Qt widget — not a text log. Something like:

- A `QListWidget` (or a small custom widget per row) where each entry is
  one event: a scan-result line (`22/tcp → ssh`), a step outcome
  (`[hydra] SSH brute force — done` / `— skipped`), a credential found
  (`admin:hunter2 on 22/ssh`, maybe visually flagged/highlighted), the
  final summary (`Executed: 3 · Skipped: 1`). Icons or colored left-border/
  badge per row type instead of `[label]` text prefixes.
- Normal app styling (`PANEL`/`BG_INPUT`/`TEXT` from `src/config.py`, same
  palette `WizardControlPanel` already uses) — no `CONSOLE_BG`/
  `CONSOLE_TEXT`/monospace font anywhere on this page.
- Empty state before the first scan: a normal centered label (not inside a
  black box) — same message as today ("Fill in the panel on the left and
  press Start scan...") is fine, just not console-styled.

`WizardDriver.statusUpdate` already emits structured dicts
(`{"type": "status", "kind": "scan_result"|"step_done"|"cred_found", "text":
..., "data": {...}}` — see `chain_wizard/core/ui_driver.py`'s `IpcUI.status`
and every `get_ui().status(...)` call site... actually check: as of the
2026-08-27 rewrite, no call site emits `status` yet — `chain.py`/
`scanner.py` still only call `ui.menu`/`ui.text`/`ui.multiselect`/
`ui.confirm`. Wiring real scan-result/step-done/cred-found status events
into `chain_wizard/wizard/chain.py` (open ports after Phase 1, each step's
outcome, each harvested credential) is *part of this follow-up* — right
now `WizardRunner._on_finished`/`statusUpdate` has almost nothing to
render because nothing sends it yet. Add `get_ui().status(...)` calls at:
  - `chain.py::run_chain`, after `scan_target()` returns — one status per
    open port (mirrors the deleted `print(f"  {port}/tcp → {service}")`
    loop).
  - `chain.py::_execute_step`, after `run_cmd` — step done/skipped, with
    `port`/`service`/`tool`/`name` in `data` for a structured row.
  - `chain.py::_execute_step`'s credential-found branch — one status per
    harvested `(user, password)`.
  - `chain.py::run_chain`'s summary block, at the end.

Keep `data` payloads structured (dict of primitives), not pre-formatted
strings, so the new widget can build a real row (icon + columns) instead of
just dumping `text` into a label.

## Also worth checking while in there

- `wizard_dialogs.py`'s `show_confirm_dialog` uses a `QTextEdit` for the
  impact preview box — that one's fine to keep monospace-ish (it's showing
  a real command + `ConfirmationGate`'s preview-box text, which *is*
  supposed to read like a terminal preview, same as Direct Tool Mode's own
  confirmation box). Don't over-apply this plan to that dialog; the
  objection is specifically the ambient "always-visible black panel",
  not a modal dialog that's explicitly showing a command.

## Verification

- `python -m pytest tests/` and `python -m pytest chain_wizard/tests/`
  (from `chain_wizard/`) — both suites should still fully pass; extend
  `chain_wizard/tests/test_ui_driver.py`-style coverage for the new
  `status()` call sites if reasonable (e.g. assert `chain.run_chain` calls
  `ui.status("scan_result", ...)` once per open port — can stub `get_ui()`
  with a fake recorder).
- Manual: `python -m src.main`, Wizard Console page — before Start scan,
  no black box anywhere; after Start scan and answering a couple of
  dialogs, the right-hand panel should look like a normal list/table in
  the app's own theme, not a console.
