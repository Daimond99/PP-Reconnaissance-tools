# Progress Log

Running log of what's done, what's in flight, what's next. Newest entry on
top. For deep current-state detail see `CURRENT_STATE.md`; for the current
GUI/wizard embedding plan see `CROSS_PLATFORM_TERMINAL_PLAN.md`.
(`GUI_MISSION_CONTROL.md` was deleted 2026-07-31 — fully superseded, it
described UI files removed in earlier passes.)

---

## 2026-08-01 — OpenCode exit-loop, Ctrl+Z, opencode-block, path confinement, Raw Output read-only

Follow-up hardening pass on top of the LLM Mode entry below, driven by
issues found testing the new OpenCode tab.

**Bug: exiting OpenCode killed the tab.** `_opencode_launch`'s old
`"$OC"; exec bash -l` fallback failed with `exec: bash: not found` —
`$PATH` is scoped to `$SCOPE_BIN` (the 6 authorized tools + read-only
utilities) by the time that line runs, and `bash` was never in that
whitelist, so the bare-name lookup for it errored and killed the tab.
Fixed by looping straight back into a fresh OpenCode session instead
(`while :; do "$OC"; sleep 1; done`, `sleep 1` guarding against a tight
crash-loop if `$OC` starts failing every run) — the tab never runs
`exec bash` post-scope at all now, so that lookup never happens again.
Consequence: the tab never reaches an interactive bash prompt any more,
which made the original `set -m`/non-`exec`'d-job trick (kept a shell
alive underneath OpenCode so Ctrl+Z could `fg` back into it) moot; removed.

**Bug: Ctrl+Z blanked the pane.** Root cause turned out to be different
from the initial fix attempt (`trap '' TSTP` in the wrapper shell — didn't
work, and it's now understood why): OpenCode runs its own TUI in raw
terminal mode, so Ctrl+Z never becomes a real `SIGTSTP` at the kernel
level — it's delivered as a literal `0x1A` byte, and OpenCode's own
handling of that byte (a self-suspend routine, not real job-control
suspend) was what left the terminal blank with nothing to redraw it, made
worse once the exit-loop fix above meant a *new* OpenCode instance would
spawn on top of the still-running suspended one and hang on its own
workspace lock. Fixed upstream instead of in the shell script: `XtermTerminal`
(`src/ui/webterm/xterm_widget.py`) and `PtyTerminal`
(`src/ui/pty_terminal.py`) both gained a `block_ctrl_z` constructor flag
that drops `0x1A` before it ever reaches the PTY — set only for the
`opencode` profile in `terminal_tabs.make_terminal()`.

**`opencode` blocked from the plain Shell tab and Raw Output** (per user
request — the agent should only be reachable through its own scoped tab,
not launched ad hoc). A plain `trap ... DEBUG` can't actually cancel a
command, only observe it; `shopt -s extdebug` changes that (a DEBUG trap
returning non-zero skips the next command entirely — the same primitive
shell debuggers use for single-stepping). Installed via `~/.bashrc`
(guarded by `TR_BLOCK_OPENCODE`, only exported by the shell-profile launch
path) rather than inline, because the trap has to live in the *actual*
interactive shell the user types into — `exec bash -l` replaces the
process image and traps set beforehand don't survive that, only exported
env vars do. Matches "opencode" as a substring of the whole command line,
so it catches a full/relative path to the binary and `bash -c "..."`
wrapping too, not just a bare-name PATH lookup.

**Every interactive tab confined to its own scope dir** (per user request
— "don't let a tab `cd` its way out of its own path"). New
`_confine_snippet()` in `terminal_tabs.py`, same `~/.bashrc`-install
mechanism as the opencode-block trap: a `PROMPT_COMMAND` hook that snaps
`$PWD` back to `$TR_SCOPE_DIR` after any command that leaves it (`cd`,
`pushd`, a sourced script — checking after the fact catches all of these,
not just a literal `cd ..`). Wired into `wizard` (chain_wizard/, once the
CLI itself exits to its trailing bash), `shell` (repo root — wider than
the other tabs since it's meant to be usable project-wide), and `llm-nmap`
(tools/llm-tools-nmap/). Installed for consistency into `opencode` too,
but it's inert there: `PROMPT_COMMAND` only fires at an interactive
prompt, and that tab never reaches one after the exit-loop fix above —
PATH-scoping remains the only real control OpenCode's tab has. Soft lock
only either way: an absolute path still reaches the rest of the
filesystem, same ceiling as the existing PATH-scoping.

**Raw Output narrowed to display-only** (per user request, after
initially misdirecting the same ask at Results Display — that tab turned
out to have no typable surface at all already, just missing explicit
`NoEditTriggers` on its `QListWidget`/`QTreeWidget`, fixed defensively
anyway). `make_terminal()` gained `read_only: bool`; `XtermTerminal`/
`PtyTerminal` drop every keystroke/paste from the page before it reaches
the PTY when set, while `write_text`/`run_command` (Direct Tool Mode
Execute's programmatic command injection) are untouched since they write
to the backend directly rather than through the same path as page
keystrokes. `RawOutputTab` now calls `make_terminal("shell",
read_only=True)`. Known gap: the plain-pipe tier-3 fallback
(`InteractiveTerminal`) doesn't support `read_only` — not expected to be
hit on a machine with WebEngine/ConPTY available, which both dev and
target machines have so far.

Verified throughout: `py_compile` clean on every touched file; every
generated bash launch script (`_shell_launch`/`_llm_launch`/
`_opencode_launch`) round-tripped through `bash -n` for syntax validity
after each change, including a real bug caught this way (the confine
marker text originally contained an apostrophe, breaking out of the
single-quoted `grep -qF '...'` around it — fixed by rewording the marker).
Not yet done: manual GUI click-through of Ctrl+Z / exit-loop / opencode-block
/ confinement in the running app (`python -m src.main`) — verified via
`bash -n` + code-path reasoning, not by driving the live UI.

Next: the tier-3 `read_only` gap above; extending real path confinement to
`opencode` itself would need a different mechanism than `PROMPT_COMMAND`
(it never reaches an interactive prompt) — e.g. wrapping how OpenCode's
own shell tool invokes commands, out of scope for this pass.

---

## 2026-08-01 — LLM Mode: llm-tools-nmap + OpenCode agent, square-corner tab style

Turned LLM Mode from a single plain shell into two fixed, square-cornered
block tabs — **"LLM"** and **"OpenCode"** — both real AI-tool integrations,
neither gated (same intentional trade-off as Raw Output). Full detail in
`CURRENT_STATE.md`'s new "LLM Mode" section; summary here.

**"LLM" tab — llm-tools-nmap:**
- Cloned `gitlab.com/kalilinux/packages/llm-tools-nmap` into
  `tools/llm-tools-nmap/` (gitignored); installed the `llm` CLI via `pipx`
  in WSL. `llm-nmap` profile (`terminal_tabs._llm_launch`) auto-cd's there,
  offers to `llm keys set openai` if no key stored yet, prints a
  copy-pasteable usage banner.
- New `src/core/llm_keys.py` + Settings ▸ **Set LLM API Key…** / **Remove
  LLM API Key…** — free-text provider name, not hardcoded to openai/gemini.
  Kept out of `src/ui/` per the GUI-never-builds-commands rule.
- Installed `llm-gemini`, set default model to `gemini-2.5-flash` after
  `gemini-1.5-flash-latest` turned out unsupported by this key's API
  version and the account's free-tier quota turned out to be 0 for
  `gemini-2.0-flash` (region/project-gated — separate quota pool from the
  gemini.google.com web chat's own free usage, a mixup worth remembering).

**"OpenCode" tab — scoped coding agent:**
- Installed [OpenCode](https://opencode.ai) (official installer, inspected
  the script first — GitHub-release download only, no `sudo`/`rm -rf`
  before running it blind). `opencode` profile
  (`terminal_tabs._opencode_launch`) cd's into `tools/opencode-workspace/`
  (gitignored), drops an `AGENTS.md` scope note there once (user-editable
  after), then rebuilds `~/.recon_agent_bin/` — symlinks to *only* the 6
  authorized tools + a few read-only utilities — and restricts `$PATH` to
  it before launching. Soft scope, not a sandbox: blocks bare-name lookups
  (git/python/curl/apt/ssh unavailable by name), not absolute-path calls.
- Bug found + fixed: first cut used `exec "$OC"`, which replaced the shell
  entirely — Ctrl+Z suspended OpenCode with no shell left underneath to
  `fg` back into (looked like the terminal just died). Fixed with `set -m;
  "$OC"; exec bash -l` (explicit job control + no `exec`-replace).
- Bug found + fixed: opening a second OpenCode tab hung (OpenCode locks its
  workspace dir). Rather than chase that lock, `TerminalTabsWidget` gained
  a `fixed=True` mode — opens exactly one tab per profile up front and
  permanently hides `+`/`⌄`/close, so a second instance of any profile on
  that page is structurally impossible, not just discouraged.
- **Safety incident found + fixed**: the PATH-scope rebuild originally used
  `rm -f "$SCOPE_BIN"/*`. `$HOME` was reproduced empty in one
  non-interactive WSL invocation shape, which would silently collapse
  `$SCOPE_BIN` to `""` and turn that glob into `rm -f /*` against the WSL
  root filesystem — only survived by luck (permission errors, not safe
  code). Fixed with an explicit `if [ -z "$HOME" ]` abort-first guard and
  per-name `rm -f "$SCOPE_BIN/$tool"` deletes instead of any `dir/*` glob.

**Root-cause bug, fixed once, mattered twice:** `wsl.exe bash -lc
"<multi-statement script>"` **without `-e`** gets re-parsed through an
extra shell layer that silently drops variable assignments across
`;`-separated statements (reproduced: `OC=x; [ -z "$OC" ] && echo BUG`
prints `BUG` without `-e`, correctly doesn't with it). This had already
been fixed in `llm_keys.py`'s own `wsl.exe` calls; the same missing `-e`
in `terminal_tabs.make_terminal()`'s `XtermTerminal`/`PtyTerminal` argv
(tier-3 fallback had it, tiers 1–2 didn't) is why the OpenCode tab
couldn't find its own installed binary in the real GUI until fixed.

**Square-corner tab style (user request, applied everywhere):**
`TerminalTabsWidget` generalized to accept `profiles=[(menu_label,
profile_key, tab_name), ...]` instead of hardcoding Wizard/Shell naming,
plus the new `fixed` mode above. QSS unified into one square-cornered
style (`border-radius: 0`) for every terminal page's tabs, replacing the
old rounded-pill look — Wizard Console kept its content-sized/
closable/reorderable behavior, LLM Mode's two tabs additionally
`setExpanding(True)` to fill the header 50/50 as big blocks.

Verified throughout: `py_compile` clean on every touched file; headless
`QApplication` + `ReconMainWindow()` smoke tests after each change (llm_tab
backend type, tab counts/labels, hidden `+`/`⌄`, non-closable tabs, block
vs pill style flags); the `$HOME`-empty guard and the `-e` fix both
reproduced-then-verified via direct `wsl.exe` invocations before and after;
real `set_llm_key`/`has_llm_key`/`remove_llm_key` round-trip against the
actual `llm` keys store. Not yet done: manual GUI click-through of both new
tabs in the running app (`python -m src.main`) — everything above was
verified via headless construction + isolated WSL reproduction, not by
clicking through the live UI.

---

## 2026-08-01 — Sudo support, per-tool warheads, Results Display for masscan/hydra/ncrack, splash screen

Big pass, several independently-requested pieces landed together.

**WSL lifecycle / startup UX:**
- **App-close confirmation + WSL shutdown** — `main_window.closeEvent` now
  asks Yes/No before closing; on Yes (Windows), runs `wsl.exe --shutdown`
  after stopping all terminals. Fixes: closing the app used to leave the
  WSL2 VM running in the background (killing the PTY's `wsl.exe` client
  process doesn't stop the VM itself).
- **No more hardcoded "Ubuntu"** — `terminal_tabs.py` no longer passes
  `-d Ubuntu` to `wsl.exe`; launches whatever the user's WSL *default*
  distro is. `_wsl_available()` checks for *any* real distro (excludes
  Docker Desktop's pseudo-entries) and shows a plain "install WSL"
  placeholder instead of a silently-blank terminal if none exists.
  `main_window.closeEvent`'s `--shutdown` also doesn't need a distro name
  (tears down the whole VM, not one distro).
- **Terminal tab cap** — `_MAX_TABS = 4`; `+`/`⌄` disable at cap. Each tab is
  a separate Chromium renderer + PTY, a real resource cost on lower-spec
  machines.
- **Startup splash screen** (`src/main.py`) — shown until the Wizard
  Console's first terminal actually produces output
  (`XtermTerminal.firstOutput` → `TerminalTabsWidget.firstTabReady`), not
  just until widget construction returns. First cut waited on
  `backendReady` (PTY *spawned*) which fires almost instantly — WSL can
  still take several seconds to actually boot after that, so the splash
  was closing too early; fixed by adding the separate `firstOutput` signal
  tied to real bytes coming back. 20s safety-cap timer either way.

**Sudo + shell-metacharacter validation:**
- **Bare `sudo <tool>` now allowed** (`validation/common.py`,
  `confirmation_gate.py`) — masscan always needs raw sockets in WSL, nmap's
  `-sS`/`-O`/privileged ping probes do too, `setcap` isn't always set up.
  Only the bare form (`sudo nmap ...`, no sudo flags) passes; the impact
  preview gets an explicit "[!] running as root" line whenever it fires.
- **Quote-aware dangerous-metacharacter check** — replaced the old
  `re.search` over the whole raw string (which blocked `;|&`$()<>\`
  *anywhere*, including inside legitimate quoted data) with
  `_has_unquoted_shell_metachar()`, a small scanner that tracks
  `'...'`/`"..."` regions and only rejects those characters *outside* a
  quoted region. Found via testing: this was rejecting a real, useful
  warhead (`Hydra - Targeted Web Login`, whose `http-post-form` payload
  has a literal `&` inside quotes). Security posture unchanged for actual
  injection shapes (unquoted `;`, `|`, `&`, backtick, `$()` all still
  rejected) — verified with 9 test cases covering both the fix and the
  still-blocked attack patterns.
- **`convert_windows_paths_to_wsl()`** — rewrites `C:\...`-style paths
  (quoted or bare) to `/mnt/c/...` before validation, on Windows. Lets a
  user paste a Windows Explorer path for a hydra/ncrack wordlist directly
  instead of hand-translating it (the command actually executes inside WSL
  bash, which has no drive letters).

**Warhead profiles reworked (per user request: "warhead แยกชื่อแต่ละเครื่องมือ"):**
- Moved `TOOL_COMMANDS`/`WARHEAD_COMMANDS` out of hardcoded `config.py`
  dicts into `src/resources/tool_commands.json` + one
  `src/resources/warheads/<tool>.json` per tool (resource-driven, per
  CLAUDE.md's own rule — this data was a hardcoded-string violation of it).
  `config.py` still exposes the same `TOOL_COMMANDS`/`WARHEAD_COMMANDS`/
  `WARHEAD_BY_TOOL` names, so nothing downstream needed to change.
- **Deleted genuinely-dead code found in the process**: `TOOL_LIST` (7
  "legacy display name" entries) was an unreachable fallback —
  `ToolManager.tools` is a fixed 6-entry dict, never empty, so
  `tool_names if tool_names else TOOL_LIST` could never take the `TOOL_LIST`
  branch. Deleted the constant, its 7 dead `tool_commands.json` entries,
  and the dead branch in `widgets.py`.
- **36 new warhead profiles** — 6 per tool (nmap/masscan/ncat/hydra/ncrack/
  evil-winrm), 2 stealth / 2 critical / 2 quality-normal each.
  `TopBar.set_warhead_profiles(tool)` repopulates WARHEAD PROFILE from
  `WARHEAD_BY_TOOL[tool]` whenever TOOLS changes (`blockSignals` during the
  swap so it doesn't fire a stray `_on_warhead_change` mid-rebuild).
  `sudo` prefixed onto the masscan warheads (all need it) and the nmap ones
  using `-sS`/`-O`/raw ping (4 of 6 — `Vulnerability Scan`/`Web Focus` don't
  need root).
- **Bug found + fixed during testing**: masscan warheads originally wrote
  glued flag+value (`-p1-65535`, `--rate=100000`) — real, valid masscan
  syntax, but it meant the token never exact-matched the `-p`/`--rate` keys
  in `flag_impacts.json`, so no impact-warning line ever showed. Rewrote to
  spaced form (`-p 1-65535 --rate 100000`, masscan accepts both) so the
  matcher actually fires. Verified all 42 (6 base + 36 warhead) commands
  pass `ConfirmationGate` end-to-end after the fix.

**Per-tool impact warnings** — `nmap.analyzer.generate_impact_description`
generalized to take a `tool` argument and read
`src/resources/<tool>/flag_impacts.json`; added that file for `masscan`,
`ncat`, `hydra`, `ncrack`, `evil-winrm` (previously nmap-only). Confirmation
preview now shows a real per-flag warning for every tool's command, not
just nmap's.

**Results Display now covers 4 of 6 tools:**
- **Masscan** — `main_window._scan_xml_capture_paths` (renamed from
  `_nmap_xml_capture_paths`) now also recognizes a bare masscan invocation
  and auto-appends `-oX <file>`. No new parser needed: `parse_nmap_xml`
  never checks `scanner=`, it just walks `<host>`/`<address>`/`<ports>`/
  `<port>`, and masscan's `-oX` output is a compatible subset of nmap's
  schema.
- **Hydra/Ncrack → new "Credentials Found" view** (user chose this over
  forcing them into the nmap host/port shape, which doesn't fit what they
  produce). New `src/tools/hydra/parser.py` / `src/tools/ncrack/parser.py`
  (regex over `hydra -o <file>` / `ncrack -oN <file>` output — first real
  callers, so adding these packages doesn't violate the "don't scaffold
  unwired tool packages" rule). `main_window._cred_capture_paths()` mirrors
  the scan-capture mechanism to auto-append the right output flag.
  `ResultsDisplayTab` gained `add_credential_results()` /
  `_render_credentials_detail()` — a `kind: "credentials"` entry rendered
  as a Host/Port/Service/Login/Password table instead of the nmap detail
  view, living in the same host_list/detail_tree split view so every
  tool's results show up in one place.
- **Ncat/Evil-WinRM intentionally left alone** — interactive sessions, no
  structured "scan result" to parse; stay as live terminal output only.

Verified throughout: all edits `py_compile` clean; headless `QApplication` +
`ReconMainWindow()` construction smoke-tested after each change (tool/
warhead combo repopulation, `_scan_xml_capture_paths`/`_cred_capture_paths`
routing for all 9 representative commands including `sudo`-prefixed ones,
`ResultsDisplayTab.add_credential_results` rendering); parser unit tests for
both new hydra/ncrack parsers against synthetic output files; app actually
launched once via `python -m src.main` (window opened, correct title,
closed cleanly, exit code 0, no traceback).

Next: gap #2 in `CURRENT_STATE.md` — `main_window.py`'s `QMessageBox`
prompt text (Execute confirmation body, close-confirmation prompt) is still
hardcoded Python strings, not resources. Linux-native verification of the
whole pass (everything above was only exercised on Windows/WSL2) still
pending, same open item as before.

---

## 2026-07-31 — Direct Tool Mode + Zenmap scan queue, dead-code sweep

Big feature + cleanup pass. GUI now has a real Direct Tool Mode end-to-end,
plus a substantial dead-code removal (~750 lines / 8 files deleted).

Direct Tool Mode (feature):
- **`InputManagementTab` rebuilt** as a Zenmap-style scan queue
  (`Status | Command`) with **Append / Remove / Cancel Scan**. Append opens a
  saved nmap `-oX` XML and reads its command back (`<nmaprun args="…">`);
  double-click a row sends its command to the top-bar box (`reuseRequested`).
  Every top-bar Execute lands a row (Running → Done/Error). Old key/value
  param table removed.
- **`RawOutputTab`** now uses `make_terminal("shell")` (same xterm.js+PTY
  backend as the Wizard Console, not a plain pipe) and gained
  `run_command()` / `interrupt()` / `focus()`. `XtermTerminal` gained
  `write_text` / `run_command` (sentinel `printf __TR_DONE_<tok>_$?__` →
  `commandDone(token, exit_code)`) / `interrupt` / `focus`; parity stubs added
  to `PtyTerminal` and `InteractiveTerminal`.
- **`main_window._on_execute_clicked`** still gates through `ConfirmationGate`
  (preview + literal "yes"), then runs the command **in Raw Output** (auto-
  jumps + focuses the terminal so Ctrl+C interrupts) instead of the old
  QProcess+QMessageBox. Completion marks the queue row and logs the real
  exit via `mark_executed_result`. `skip_scope=True` — Direct Tool Mode
  targets are the user's own lab IP typed into TARGET; typing a new TARGET
  live-swaps it into the command box (`_on_target_changed`).
- **8 new warhead profiles** added from the user's `warhead.txt` (evasion
  ping, honeypot version, common TCP SYN, quick/intense/comprehensive scans,
  telnet). #3's `...` port list fixed to `17,19,21-32764,5985,5986`; #9's
  `-iR 100` (random-internet) replaced with a scoped target placeholder.
  Warhead combo widened 180→300px.
- **Settings moved to the title bar** (top-left): sidebar collapse toggle
  (fully hides the sidebar + divider, Claude Code desktop-style) + a Settings
  dropdown trimmed to what the app can do — New/Stop Scan, Open/Save/Save-All
  Scan (XML round-trip), Quit. Open Scan fills the command box + TARGET +
  Input Management row.

Dead-code sweep (no runtime behavior change):
- **Deleted files**: `src/core/auto_chain.py`, `src/core/api_key_manager.py`
  (nothing imported them), `src/scripts/llm-tools-nmap.py` (orphaned +
  closed the direct-nmap safety gap), `src/ui/widgets.py::CommandEditorTab`
  (sidebar page removed → 5 pages, Raw Output now index 2), and 5 orphaned
  resource JSONs (`wizard/menu.json`, `wizard/messages.json`,
  `nmap/scan_profiles.json`, `nmap/service_tools.json`, `common/warnings.json`
  — only `nmap/flag_impacts.json` is still loaded).
- **`audit_log.py`** trimmed to just `audit_log_llm` (the active safety
  trail, `logs/audit_log.jsonl`); dropped dead `audit_log_confirmation/
  cancel/fallback`.
- **`config.py`** dropped the dead LLM/tool-selection constants
  (`DIRECT_TOOL_CONTENT`, `WIZARD_CONTENT`, `LLM_DEMO_TEXT`, `SYSTEM_PROMPT`,
  `AI_MODE_PROVIDERS`, `KEYRING_SERVICE_NAME`, `TOOL_ENABLEMENT`,
  `NCRACK_*`, `TOOL_NOT_SUPPORTED_MESSAGE`, `LLM_TOOLS_NMAP_PATH`).
- **`nmap/analyzer.py`** dropped the unused `recommend_next_tools` +
  `_service_tool_map`. `nmap/builder|parser|validator.py` kept unwired to
  preserve the documented four-file layout.
- Removed all unused imports (pyflakes clean across `src/`).
- Verified: `compileall src` OK, `pyflakes src/` clean, headless
  `ReconMainWindow` smoke test (5 pages, sidebar toggle, XML save/open
  round-trip) OK.

Next: manual GUI pass (`python -m src.main`) — verify Direct Tool Mode run in
Raw Output, Ctrl+C interrupt, Settings dropdown/file dialogs, sidebar
collapse; Linux native run still pending.

---

## 2026-07-31 — VS Code-style tabbed terminal + copy/paste hotkeys

Built on the xterm.js terminal (entry below). GUI layout unchanged — the
Wizard Console page's single terminal is now a tabbed container.

Done:
- **`src/ui/terminal_tabs.py` (`TerminalTabsWidget`)** — `QTabBar` +
  `QStackedWidget` over the terminal backends. First tab = **Wizard**
  (`chain_wizard` CLI, original behavior); `+` opens a plain **Shell** (WSL
  Ubuntu bash / bash), `⌄` menu opens either profile. Close (×) stops that
  tab's PTY; the last tab can't be closed. **PyCharm-style tabs** — content-
  sized rounded pills (`setExpanding(False)`), active tab = filled panel bg +
  orange bottom-accent underline, and **drag-reorderable** (`setMovable(True)`
  + `tabMoved` → `_on_tab_moved` reorders the stack to stay index-synced with
  the bar). `make_terminal(profile)` factory (moved out of `widgets.py`) keeps
  the Xterm→Pty→Interactive fallback chain for both profiles.
- **`widgets.py`** — `MainContentArea._make_wizard_terminal` deleted; the page
  now instantiates `TerminalTabsWidget`. Dropped now-dead imports
  (`PtyTerminal`/`XtermTerminal`/`os`); `InteractiveTerminal` still used by
  Raw Output / LLM Mode.
- **Copy/paste hotkeys in `webterm/term.html`** — `attachCustomKeyEventHandler`:
  Ctrl+C copies when text is selected else falls through to SIGINT; Ctrl+V
  pastes (`term.paste`, bracketed-paste aware); Ctrl+Shift+C/V explicit;
  right-click pastes. `xterm_widget.py` enables `JavascriptCanAccessClipboard`
  + `JavascriptCanPaste` so clipboard works with no permission prompt.
  Ctrl+L / `clear` / Ctrl+D / Ctrl+Z / arrows / Home/End / Tab pass straight
  to the shell.
- **Verified** — tab smoke test (headless QApplication): first tab Wizard, `+`
  adds Shell/Shell (2), stack stays index-synced with the tab bar, close
  removes correctly, last tab refuses to close. `py_compile` clean.

Next: manual GUI check of clipboard copy/paste and tab UX in the running app
(`python -m src.main`); Linux native run still pending (below).

---

## 2026-07-31 — Wizard Console terminal replaced with xterm.js (IDE-grade)

Replaced the pyte→HTML `PtyTerminal` as the primary Wizard Console terminal
with a real xterm.js emulator (the one VS Code ships) hosted in a
`QWebEngineView`. GUI layout unchanged — only the terminal widget inside the
Wizard Console page swapped. Solves the two limits the user rejected in
`CROSS_PLATFORM_TERMINAL_PLAN.md`: no reflow-on-resize, and pywinpty being
Windows-only (no color/sudo on Linux).

Done:
- **New `src/ui/webterm/`** package:
  - `xterm_widget.py` (`XtermTerminal`) — QWidget wrapping `QWebEngineView`.
    `_Bridge` (QWebChannel) shuttles PTY bytes (base64, so UTF-8 never splits)
    to `term.write`, and keystrokes/paste/resize back to the PTY. `_Reader`
    (QThread) pumps blocking PTY reads off the GUI thread. PTY backends:
    `_WinPty` (pywinpty ConPTY, Windows) and `_PosixPty` (stdlib
    `pty.fork` + `termios` winsize, Linux — no third-party dep). Spawn is
    deferred until JS `ready(cols,rows)` fires so the shell starts at the
    correct size.
  - `term.html` — xterm.js + fit addon + qwebchannel bootstrap; `__BG__`/
    `__FG__` tokens substituted from `src/config.py` at load. Loaded via
    `setHtml` with a `file://` base URL so relative `vendor/*.js` resolve.
  - `vendor/` — xterm.js 5.3.0, addon-fit 0.8.0, xterm.css, qwebchannel.js
    (committed, offline, no CDN).
- **Wiring** — `src/ui/widgets.py` `_make_wizard_terminal` now selects
  `XtermTerminal` → `PtyTerminal` → `InteractiveTerminal` (first available).
  Same launch command across all three. Import + `XTERM_AVAILABLE` added.
- **Deps** — `PySide6-QtWebEngine>=6.6.0` added to `requirements.txt` (already
  installed on this machine; WebEngine + WebChannel + winpty all present).
- **Verified** — headless-ish smoke test (QApplication, 14s): page loaded,
  QWebChannel connected, `ready` fired (100×30), PTY spawned `wsl.exe -d
  Ubuntu`, real output flowed back (`XTERM-SMOKE-OK` + `uname -a` + WSL boot,
  463 bytes, UTF-8 correct). `py_compile` clean on all touched files.

Next:
- **Linux native verify** — the `_PosixPty` path is written but not yet run on
  a real Linux box (install the 6 tools, `python -m src.main`, open Wizard
  Console). ptyprocess intentionally not a dep — stdlib `pty` used.
- Old `CROSS_PLATFORM_TERMINAL_PLAN.md` reparent-conhost/xterm task is now
  moot (superseded by this approach) — mark it there if continuing.
- `PtyTerminal` (pyte) kept only as a fallback; could be deleted once the
  xterm path is confirmed on both platforms.

---

## 2026-07-31 — Stale docs cleanup

- **Deleted `docs/GUI_MISSION_CONTROL.md`** — last touched 2026-07-26, still
  described `wizard_console.py`/`wizard_terminal.py`/`llm_mode.py`/
  `tool_selection.py` as live code; all four were deleted across two later
  rewrites (the `wizard_terminal.py` pass, then the `chain_wizard/`
  rewrite). Also referenced a `Mockup HTML.txt` that doesn't exist anywhere
  in the repo. Content was fully redundant with `CLAUDE.md`'s GUI section
  and `CROSS_PLATFORM_TERMINAL_PLAN.md` — nothing worth preserving.
- **Rewrote `docs/CURRENT_STATE.md`** — it still described the deleted
  `wizard_terminal.py` as the live Wizard Console and listed
  hydra/masscan/ncat/ncrack/evil_winrm as `src/tools/` packages with a
  real/placeholder breakdown, even though all five were deleted the same day
  (see "Dead tool packages removed" entry below). Rewrote every section
  against the actual current tree: sidebar page table, `chain_wizard/`
  orchestration (unchanged in substance, just re-verified), `src/tools/nmap`
  as the sole surviving package, confirmation-gate scope narrowed to
  top-bar Execute only, safety-gap list renumbered to 3 (dropped items that
  no longer apply), external-tools table trimmed to the current WSL2/Linux
  install path.
- Removed the now-dangling `GUI_MISSION_CONTROL.md` pointers from
  `CLAUDE.md`'s doc-index paragraph and this file's header.

---

## 2026-07-31 — README rewritten as install-focused quick start

Pushed to `origin/main` (`243e29a`).

README still described PyQt5, `wizard_engine.py`, and a "Direct Tool Mode"
that no longer exist (leftover from before the `chain_wizard/` rewrite).
Dropped the Project Structure, Architecture Overview, Contributing, License,
Author, and Legal Notice sections — README's job now is just "how do I
install and run this," not a full architecture doc (that's `CLAUDE.md` +
`docs/`). New structure: what it does (short) → cross-platform install
(Windows = WSL2 + tools inside it, Linux = tools natively, same
apt/gem command either way) → run → pointer to `CLAUDE.md`/
`CURRENT_STATE.md` for detail → Disclaimer.

---

## 2026-07-31 — Dead tool packages removed, wizard folder renamed

Cleanup pass. No behavior change — pure dead-code removal + rename.

Done:
- **Deleted 5 dead `src/tools/<tool>/` packages** — hydra, masscan, ncat,
  ncrack, evil_winrm. Nothing imported them: `grep` for `tools.<name>` /
  `tools/<name>` across `src/` and the wizard returned zero hits. The live
  wizard (`chain_wizard/`) invokes those tools directly via
  `core/executor.py` (`subprocess`, `shell=True`), not through per-tool
  builder/validator/parser/analyzer modules. **`src/tools/nmap/` kept** — its
  `analyzer` is still imported by `src/core/confirmation_gate.py` (impact
  text, confirmation box, scope check) for the top-bar Execute path.
- **Renamed `new wizard/` → `chain_wizard/`** (dropped the space in the
  folder name). Updated every reference: `src/ui/widgets.py`
  (`_make_wizard_terminal` WSL + local launch paths), `requirements.txt`
  comment, `.gitignore` runtime-artifact globs, `src/config.py`
  `TOOL_ENABLEMENT` comment, and docs (`CLAUDE.md`,
  `CROSS_PLATFORM_TERMINAL_PLAN.md`, this file).
- **Docs de-drifted** — `CLAUDE.md`'s tool-package + `src/ui/` descriptions
  now match the real tree (only `nmap` survives; `tool_selection.py`/
  `llm_mode.py`/`wizard_console.py`/`wizard_terminal.py`/`src/wizard/engine.py`
  are gone); the stale 2026-07-25 audit section re-flagged as historical.
- Verified: `python -m compileall src` OK; `chain_wizard` py_compile OK; no
  leftover refs to deleted packages except the (now-fixed) config comment.

Next: `docs/CURRENT_STATE.md` still described the old 6-package layout /
removed UI files at the time — fixed in the entry below (2026-07-31,
"Stale docs cleanup"). Cross-platform terminal backend (conhost/xterm
reparent) remains the main open task — see `CROSS_PLATFORM_TERMINAL_PLAN.md`.

---

## 2026-07-30 — New chain wizard built, embedded in GUI; cross-platform terminal plan

**Big pass.** A brand-new standalone chain wizard was built under `chain_wizard/`
and wired into the GUI Wizard Console. **Read `docs/CROSS_PLATFORM_TERMINAL_PLAN.md`
before continuing — it is the authoritative handoff for the next task.**

Done:
- **`chain_wizard/` chain CLI** — scan → impact-ranked plan (AUTO/SEMI, tags
  `(recommended)`/`(optional)`/`(info)`) → hydra brute → credential harvest +
  per-target `loot_*.txt` → in-scope post-exploit (ncat ftp/telnet, nmap NSE
  smb/mysql, evil-winrm WinRM) → results echoed. nmap **stealth** scan profile
  with tunable `-T`. Arsenal + post-exploit are JSON resources
  (`attack_map.json`, `post_exploit.json`). Restricted to the 6 authorized
  tools. evil-winrm only after a real credential (never a standalone fake-cred
  step). Ctrl-C loops back to the menu; Ctrl-D exits. Colors auto-disable on
  non-TTY; banner/section width adapts to `shutil.get_terminal_size()`.
- **GUI embed** — `src/ui/pty_terminal.py` (`PtyTerminal`): real ConPTY
  (pywinpty) + pyte VT emulator, runs the CLI inside Ubuntu WSL with real
  color/sudo/TAB. Wizard Console launches it (`MainContentArea.
  _make_wizard_terminal`); deferred spawn on `showEvent` sizes it to the pane.
- **Dead code removed** — `src/ui/wizard_terminal.py`, `src/ui/wizard_console.py`,
  `src/wizard/engine.py` (all unwired). Kept: everything else in the GUI.
- **Deps** — `pyte` + `pywinpty` added to `requirements.txt` and installed in
  both the venv and the global WindowsApps python (the latter is what
  `python -m src.main` uses — without it the GUI silently falls back to the old
  plain terminal, which is the "still shows old" symptom to watch for).
- **Git** — branch `feat/new-wizard-chain` committed + pushed; PR not opened
  (`gh` CLI absent). rockyou/test lists/runtime artifacts gitignored.

Remaining / next (full list in `CROSS_PLATFORM_TERMINAL_PLAN.md`):
- Build the **cross-platform real-terminal backend**: Windows = reparent a real
  `conhost.exe wsl.exe … python3 -m wizard.main` into the pane via Win32
  `SetParent` (exact cmd-with-WSL experience, full reflow/resize the user
  asked for); Linux = `xterm -into <winId>` reparent, or a posix PTY
  (`ptyprocess`/stdlib `pty`) feeding pyte. Keep reparent → PtyTerminal →
  InteractiveTerminal as a fallback chain.
- Verify natively on Linux (install the 6 tools, run the CLI, then the GUI).
- Optional: remove remaining dead pages `src/ui/tool_selection.py` /
  `src/ui/llm_mode.py`; open the GitHub PR; DPI width polish.

---

## 2026-07-29 — WSL2 tool-runner finalized: all 6 tools installed in Ubuntu

Environment-only change, no code touched. User installed Docker Desktop +
WSL2, had 3 distros (`Ubuntu`, `docker-desktop`, `Arch`); confirmed `Ubuntu`
is WSL2 (kernel `6.6.87.2-microsoft-standard-WSL2`, Ubuntu 26.04 LTS),
deleted the unused `Arch` distro, kept Ubuntu as the sole tool-runner
(matches `wizard_terminal.py`'s `wsl.exe -e ...` calls, which target the
default distro).

Installed via `sudo apt-get install -y nmap masscan ncrack ruby ruby-dev &&
sudo gem install evil-winrm`, then a follow-up `sudo apt-get install -y ncat`
(Ubuntu's `nmap` apt package doesn't bundle ncat the way the Windows
installer does — had to be added separately). Verified all 6:
nmap v7.98, masscan v1.3.2, hydra v9.6 (already installed from the earlier
pass), ncrack v0.7, ncat v7.98, evil-winrm v3.9 (ruby 3.3.8). Full detail in
`CURRENT_STATE.md`'s "External tools" section, new "WSL2 Ubuntu install"
table.

Next: only hydra is actually routed through `wsl.exe -e ...` in
`wizard_terminal.py` today. masscan/ncat/ncrack/evil_winrm still have
placeholder builders (`src/tools/<tool>/builder.py`) — writing those and
wiring them into `WizardTerminal._route_command()` is the next real dev
work now that the environment is ready. Evil-WinRM stays top priority per
the entry below (next chain stage after hydra finds a credential).

---

## 2026-07-26 — Wizard Console rebuilt as gated nmap→hydra wizard, hydra implemented

Branch: `restyle-mission-control-gui` (still unpushed). Supersedes the
"Wizard Console → plain bash" entry below — Wizard Console is no longer a
raw shell. Raw Output / LLM Mode are unaffected, still plain bash.

**Why**: user pointed out the plain-bash Wizard Console defeated the whole
point — `whoami` printed the *host* WSL user, not a scoped tool wizard, and
nothing went through `ConfirmationGate`/validation/scope-check. Ask: rebuild
Wizard Console as a real scripted wizard (same shape as the classic
`hydra-wizard.sh` CLI: prompt → build command → preview → exact "yes" →
execute), chain nmap's open ports into whichever next tool applies, and
actually finish the hydra stage of that chain (not just a demo placeholder).

Done:
- **New `src/ui/wizard_terminal.py` (`WizardTerminal`)** replaces
  `InteractiveTerminal` on the Wizard Console page only
  (`src/ui/widgets.py` → `MainContentArea._build_pages`, `wizard_tab`).
  It is a state machine over the *same* `QTextEdit`-as-scrollback UI pattern
  as `InteractiveTerminal`, but it never spawns a shell — the only
  subprocess it ever runs is a fully validated/confirmed `nmap` or `hydra`
  invocation. Flow: target → scan profile (quick/stealth/version/
  aggressive/custom) → `ConfirmationGate` preview + literal `"yes"` → run
  nmap for real via `QProcess` → parse open ports → map ports to next-stage
  tools → (if hydra) sub-wizard for login/password/extra →
  `ConfirmationGate` again (masked) → run hydra for real via WSL → parse
  found credentials → (if any) note Evil-WinRM as the next stage.
- **Target validation bug fixed**: `192.168.182235` (missing a dot) used to
  pass `validate_target`'s hostname-pattern branch and get handed straight
  to nmap, which then failed with `Failed to resolve`. Added
  `WizardTerminal._looks_like_broken_ip()` — rejects an all-numeric/dotted
  token that isn't a valid IPv4 before it ever reaches nmap.
- **Scope check changed from hard block to warning**: `AUTHORIZED_SCOPE`
  (`192.168.1.0/24` in `src/config.py`) was rejecting *any* IP outside it
  outright, which made the wizard look broken for a user testing their own
  real network. Now `is_target_in_scope()` result is surfaced as a loud
  warning (both right after target entry and again in the confirmation box)
  but the exact-`"yes"` `ConfirmationGate` step is the actual enforcement —
  `ConfirmationGate.request(..., skip_scope=True)` is used here because the
  wizard already did its own scope check and shows the warning itself.
- **New resource `src/resources/nmap/service_tools.json`**: maps an open
  port's nmap service name (falls back to port number) to a next-stage tool
  + module + one-line reason — e.g. `ssh`→`hydra/ssh`, `wsman`→
  `evil-winrm/winrm`, `ms-wbt-server`→`ncrack/rdp`. Resource-driven per
  `docs/Resource System.md`, not hardcoded in the wizard.
- **New `src/tools/nmap/analyzer.py::recommend_next_tools(ports)`**: reads
  that resource and turns parsed open ports into a list of
  `{port, protocol, service, tool, module, why}` recommendations. This is
  what actually drives the wizard's "what's next" menu — it's built from the
  real scan result, not a static list.
- **Hydra tool package implemented for real** (was a 4-file `pass`
  placeholder, `TOOL_ENABLEMENT["hydra"]` flipped `False` → `True` in
  `src/config.py`):
  - `src/tools/hydra/builder.py` — `HydraSpec` dataclass +
    `build_hydra_argv()` (real argv, real password) /
    `build_hydra_command()` (masked display string, password shown as
    `********` unless it's a passlist file path, which isn't secret).
  - `src/tools/hydra/validator.py` — service whitelist (`ssh`, `ftp`,
    `http-get`, `smb`, `rdp`, ...), login/password field validation that
    auto-detects "single value" vs "file path" (`-l`/`-L`, `-p`/`-P`), `-e`
    extra-tries letters (`n`/`s`/`r`) validation. Reuses
    `src/validation/common.py` primitives, doesn't reinvent them.
  - `src/tools/hydra/parser.py` — regex for hydra's
    `[port][service] host: ... login: ... password: ...` result lines +
    `count_valid_credentials()` (prefers hydra's own summary line).
  - `src/tools/hydra/analyzer.py` — plain-language brute-force impact text
    (passlist size warning, lockout/fail2ban/IDS warning) for the
    confirmation box.
- **Hydra installed in WSL** (`sudo apt-get update && sudo apt-get install -y
  hydra` → v9.6-3, `/usr/bin/hydra`) — `apt-get update` was required first,
  the package wasn't found without it. No Windows-native hydra binary exists
  (confirmed again — `docs/CURRENT_STATE.md`'s external-tools table already
  said this), so `WizardTerminal._route_command()` runs the built argv via
  `wsl.exe -e hydra ...` on Windows, plain `hydra ...` on Linux/macOS.
- Verified end-to-end, headless (`QApplication` + synthetic keypresses, no
  `exec()`): malformed IP rejected before nmap; real nmap scan against
  `45.33.32.156` (scanme.nmap.org, deliberately out-of-scope) completed and
  parsed 5 open ports; chain menu built from those ports offered hydra for
  ssh/smtp/http; hydra sub-wizard against `127.0.0.1:22` (nothing listening)
  ran for real through WSL, got `Connection refused`, parsed 0 credentials,
  wizard reset cleanly. Also confirmed `ReconMainWindow` still constructs
  headlessly with `wizard_tab` now typed `WizardTerminal`.

Next (this is the actual TODO list for continuing the chain):
- **Evil-WinRM stage not implemented** — `src/tools/evil_winrm/` is still
  the 4-file `pass` placeholder. When hydra finds a credential for a
  WinRM/SMB service, the wizard currently only prints what the next command
  *would* be (`evil-winrm -i <host> -u <user> -p <password>`) and stops.
  To finish this leg of the chain: write `build_evil_winrm_command()` /
  argv in `src/tools/evil_winrm/builder.py` (mask password the same way
  hydra's builder does), a validator for host/user/password, and wire a
  `STATE_WINRM_*` sub-wizard into `src/ui/wizard_terminal.py` following the
  exact same shape as `_start_hydra`/`_go_to_hydra_confirm`/`_run_hydra`.
  Execution path: `evil-winrm-py` is `pip install`ed already (v1.6.0, see
  the "Windows demo tool install pass" entry below) but its console scripts
  aren't on PATH yet — either add that Scripts dir to PATH or invoke it via
  its full path / `python -m evil_winrm_py` if that's a valid entry point
  (needs checking, wasn't verified in this pass).
- `ncrack` stage (RDP) is mapped in `service_tools.json` but has no builder
  either — same placeholder status, lower priority than Evil-WinRM since
  `docs/CURRENT_STATE.md` already flags ncrack as installed-but-not-working
  on this machine (silent installer didn't take).
- `docs/CURRENT_STATE.md` needs its Wizard Console description and hydra
  row updated to match this entry — flagged there too, not just here.

---

## 2026-07-26 — Plain bash terminal pass

Branch: `restyle-mission-control-gui` (still unpushed).

User asked for: (1) WSL installed + all terminals on bash, (2) strip
app-injected/resource-driven text out of the terminal pages, (3) Raw
Output / LLM Mode behave as fully generic default bash (type anything,
no restrictions).

Done:
- **WSL install skipped by design** — installing a Windows optional feature
  is a system-settings change, outside what this assistant will run
  unattended. User needs to run `wsl --install` themselves (admin + reboot).
  Once installed, `InteractiveTerminal._default_shell()` (`src/ui/terminal.py`)
  already resolves `C:\Windows\System32\bash.exe` (the WSL shim) as one of its
  fallback candidates — no code change needed for that part.
- Removed all app-injected text from the Raw Output / LLM Mode terminal
  pages — they were never printing raw resource-JSON, but the top-bar
  Execute flow *was* mirroring `ConfirmationGate` preview/result text and the
  Wizard Console's executed commands into the same `QTextEdit` the live bash
  shell writes to, polluting the terminal view:
  - Deleted `RawOutputTab.append_log()` / `set_running()`
    (`src/ui/widgets.py`) — no more mirror sink.
  - Deleted `main_window._log_command()` and the
    `wizard_tab.commandEntered → _log_command` wiring — this was also gap #2
    from the 2026-07-25 audit (double-execution risk), now moot.
  - `main_window._on_execute_clicked()` / `_run_gated_command()` now show
    the ConfirmationGate preview and the finished-process result via
    `QMessageBox` dialogs instead of writing into `raw_output_tab`.
- `ConfirmationGate` validation/preview/exact-"yes"-confirm and
  `audit_log.py`'s audit trail are untouched — only the *display surface*
  changed (dialog instead of terminal text), not the safety gate itself.
- Result: `RawOutputTab.terminal` and `MainContentArea.llm_tab` are now
  plain `InteractiveTerminal` instances with nothing else touching them —
  default bash, type anything, no app text ever appears in them.

Next:
- Top-bar Execute now uses a modal dialog for long-running command output
  (no live streaming into a visible log anymore) — revisit if that's
  annoying in practice; a dedicated non-terminal status panel would be the
  fix rather than going back to mirroring into the bash view.

---

## 2026-07-26 — WSL confirmed installed, shell priority flipped to WSL

User installed WSL (Ubuntu, WSL2) and confirmed working (`wsl.exe echo` returns
output). Verified `where bash.exe` resolves Git Bash before the WSL launcher
in `PATH`, so `InteractiveTerminal` would have kept picking Git Bash even
with WSL present.

Done:
- `InteractiveTerminal._default_shell()` (`src/ui/terminal.py`) — candidate
  list reordered so `wsl.exe` (launches the default WSL distro, Ubuntu) is
  tried **before** Git Bash. Env override `BASH_PATH` still wins if set.
  `wsl.exe` takes no `-i` flag (unlike the bash.exe candidates) since it
  launches the distro's own login/interactive shell by default — candidate
  list is now `[(program, args), ...]` pairs instead of a flat path list to
  support that.
- Compile-checked; user confirmed `wsl.exe echo hello-from-wsl` works.

Next:
- Open Raw Output / LLM Mode tab in the running app once to visually confirm
  the prompt is now Ubuntu's (`user@host:~$`), not Git Bash's `MINGW64`.

---

## 2026-07-26 — Terminal merged to single view, Wizard Console → plain bash

User asked for: (1) drop the separate input line under the terminal, type
straight into the scrollback like a real terminal, default text color (no
tinted echo), (2) Wizard Console page also becomes a plain WSL bash terminal
like Raw Output/LLM Mode — nmap etc. needed to actually run from it now.

Done:
- Rewrote `InteractiveTerminal` (`src/ui/terminal.py`): removed the separate
  `QLineEdit` input row + `prompt_label` entirely. The single `QTextEdit`
  (`self.output`) is now editable directly — typing happens at the end of
  the scrollback, Enter sends that line to the shell's stdin. Tracks an
  `_input_start` cursor position so Backspace/Left/Home/typing can't touch
  already-printed output, only the current line. Up/Down history recall
  still works (replaces the current input line in place). Dropped all
  custom text tinting (`PURPLE` echo, `TERM_MUTE`/`ACCENT_RED` status
  color) — every line now renders in the plain default `CONSOLE_TEXT` color,
  no `_append(..., color=...)` param anymore.
  - Note: this is still non-PTY (stdin/stdout pipe, no real TTY) — same
    known limitation as before (see `GUI_MISSION_CONTROL.md`); curses-style
    REPLs that need `isatty()` still won't render right.
- Wizard Console page (`src/ui/widgets.py` → `MainContentArea._build_pages`)
  now instantiates a plain `InteractiveTerminal` instead of `WizardConsoleTab`
  — same as Raw Output / LLM Mode. `WizardConsoleTab` (`src/ui/wizard_console.py`)
  itself is untouched and not deleted, just unwired (same dead-code status
  llm_mode.py/tool_selection.py already had — user hasn't said to delete it).
  - `main_window._on_opmode_change()` simplified: both "Wizard Mode"/"Direct
    Tool Mode" combo values now just switch to stack index 0 — the old
    branch that called `wizard_tab.wizard_engine.reset()` /
    `wizard_tab.write_output(DIRECT_TOOL_CONTENT)` is gone since the page is
    a bash terminal with no such API. `DIRECT_TOOL_CONTENT`/`WIZARD_CONTENT`
    imports removed from `main_window.py` as a result (now unused there).
- Verified by instantiating `ReconMainWindow` headlessly
  (`QApplication` + construct, no `exec()`) — builds without error,
  `wizard_tab`/`llm_tab` both report as `InteractiveTerminal`.

Next:
- `ConfirmationGate`/`wizard/engine.py`/ nmap builder-validator-parser path is
  now fully bypassed for anything typed into the Wizard Console page (it's
  raw bash) — this is an intentional trade the user asked for (need nmap
  usable now), but it means the gated pipeline is currently only reachable
  via the top-bar Execute button. Worth flagging if this app gets pointed at
  a real target rather than staying a demo.

---

## 2026-07-26 — Windows demo tool install pass

Branch: `restyle-mission-control-gui` (still unpushed).

Done:
- Cloned 5 external tool sources into `tools/` (gitignored, not vendored):
  nmap, thc-hydra, evil-winrm-py, ncrack, ncat-w32.
- Confirmed nmap v7.98 already installed on this machine + on PATH; ncat
  comes bundled with it, also on PATH.
- `pip install evil-winrm-py` → v1.6.0 installed. Console scripts land in
  a Python Scripts dir not currently on PATH (`evil-winrm-py.exe`, `ewp.exe`)
  — usable via full path today, not yet a bare command.
- Downloaded official `ncrack-0.7-setup.exe` (1.79MB, nmap.org) into
  `tools/`. Silent `/S` install did not actually install (no registry entry,
  no install dir created) — needs a manual interactive run to get past UAC.
- `ncat-w32` and `thc-hydra` intentionally left uninstalled: ncat-w32 is
  redundant (nmap already ships `ncat.exe`); hydra has no official Windows
  binary and needs MSYS2/MinGW build or WSL — deferred per user decision.
- Added `tools/` to `.gitignore`.

Next:
- User to manually run `tools/ncrack-0.7-setup.exe` to finish ncrack
  install.
- Optional: add the Python Scripts dir to PATH for bare `ewp`/`evil-winrm-py`
  commands.
- Hydra on Windows still unresolved — revisit only if the demo actually
  needs brute-force via hydra specifically (nmap NSE brute scripts may cover
  some of that need without hydra at all).

---

## 2026-07-26 — Docs cleanup + current-state snapshot

- Reviewed all `.md` files in `docs/` + repo root: `ARCHITECTURE.md`,
  `AI_DEVELOPMENT.md`, `Coding Standards.md`, `Resource System.md`,
  `GUI_MISSION_CONTROL.md`, root `README.md`, `CLAUDE.md`. All still
  relevant (normative spec, or an up-to-date state doc) — **none deleted**,
  no stray/orphaned `.md` files found in the tree.
- Added `CURRENT_STATE.md` — snapshot of what's actually implemented vs.
  placeholder across every module, meant for a fresh AI session to read
  before touching code, so it doesn't have to re-derive it from scratch.
- Added this file (`PROGRESS.md`) to track ongoing progress going forward.

---

## Earlier (pre-2026-07-26, from `bb23b85` and prior commits)

- Mission Control GUI restyle: sidebar cut to 6 items (Tool Selection
  removed from nav), mission bar target field became an editable history
  combo, terminal chrome stripped to bare `InteractiveTerminal` (real bash
  via `QProcess`) for Raw Output + LLM Mode pages, Results Display starts
  empty (demo host data removed), Settings menu wired to a real Zenmap-style
  popup. Full detail in `GUI_MISSION_CONTROL.md`.
- 2026-07-25 architecture audit found the tool-package refactor structurally
  complete (all 6 tools have the 4-file layout, no circular imports, old
  `wizard_engine.py`/`wizard_safety.py` fully removed) but flagged several
  safety/layering gaps that are still open — see "Known live safety gaps"
  in `CURRENT_STATE.md`.
