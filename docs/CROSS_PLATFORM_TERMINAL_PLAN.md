# Cross-Platform Terminal Plan — Wizard Console (handoff)

**Purpose:** hand-off doc for a fresh AI session. Read this + `CURRENT_STATE.md`
+ `PROGRESS.md` before touching the Wizard Console terminal. It records the
agreed design, what's already built, and the concrete next task.

Last updated: 2026-07-30.

---

## Context — what exists now

The live wizard is the standalone chain CLI under **`new wizard/`** (NOT
`src/wizard/`, NOT `src/ui/wizard_terminal.py` — both removed). It is wired
into the GUI's **Wizard Console** page (`src/ui/widgets.py` →
`MainContentArea._make_wizard_terminal`).

`new wizard/` layout (all source, no artifacts — those are gitignored):
- `wizard/main.py` — entry, mode/target/wordlist prompts, loops so Ctrl-C
  restarts and finish re-runs; Ctrl-D exits.
- `wizard/pipeline.py` — `build_plan()` (AUTO/SEMI), `step_priority()`,
  `FOLLOWUP_TOOLS`/`_primary_steps` (evil-winrm never queued standalone).
- `wizard/chain.py` — orchestration: scan → `_select_steps` (impact-ranked
  menu: `(recommended)`/`(optional)`/`(info)`) → per-step confirm → run →
  `_parse_creds`/`_save_loot` → `_offer_post_exploit`/`_offer_winrm` →
  `_echo_output`.
- `library/scanner.py` — nmap quick/full/**stealth (tunable -T)**/masscan.
- `library/attack_map.json` + `attack_map.py` — port→attack arsenal (JSON).
- `library/post_exploit.json` + `post_exploit.py` — service→post-exploit
  action, **in-scope tools only** (ncat for ftp/telnet, nmap NSE for
  smb/mysql; evil-winrm handled separately).
- `library/parser.py` — gnmap → ScanResult.
- `core/executor.py` — `subprocess.run(shell=True)` (no wsl prefix — see
  routing below), timeout, logfile.
- `core/color.py` — ANSI, **auto-disabled when stdout is not a TTY**.
- `core/display.py` — banner/section/impact_box, **width adapts to
  `shutil.get_terminal_size()`** so bars never wrap on a narrow pane.
- `core/models.py` — Step/ScanResult/AttackPlan dataclasses.

Hard rule: only the **6 authorized tools** (nmap, masscan, hydra, ncrack,
ncat, evil-winrm). Do not add or install anything else.

## The agreed design (platform routing)

| Platform | Tool execution | How the CLI is launched |
|---|---|---|
| **Linux** | tools run **native** (just install the 6) | run the CLI in the native shell |
| **Windows** | tools run **inside WSL Ubuntu** | launch the CLI *inside* WSL (`wsl.exe -d Ubuntu … python3 -m wizard.main`) |

Key point: routing is handled by **where the CLI runs**, not by prefixing each
command. `core/executor.py` calls the tool name directly via `shell=True`; on
Windows the whole CLI already runs inside WSL (tools native there), on Linux it
runs in the native shell (tools native there). So the CLI is portable as-is —
**no per-tool `wsl.exe` prefixing needed.**

## The remaining task — real embedded terminal, both platforms

Current GUI terminal = `src/ui/pty_terminal.py` (`PtyTerminal`): ConPTY via
**pywinpty** + **pyte** VT emulator rendered to a `QTextEdit` as HTML. It runs
the real WSL wizard (real color/sudo/TAB) but has two limits the user rejected:

1. **pyte does not reflow history on resize** — Windows Terminal rewraps every
   line when you narrow the window; ours truncates. Not pixel-exact.
2. **pywinpty is Windows-only** — on Linux `import winpty` fails →
   `PTY_AVAILABLE=False` → falls back to the plain-pipe `InteractiveTerminal`
   (no TTY: no color, no sudo).

**Chosen solution: a platform-specific terminal backend that embeds a REAL
terminal (not a pyte re-implementation), selected by `os.name`.**

- **Windows** → launch a real classic console running WSL, e.g.
  `conhost.exe wsl.exe -d Ubuntu bash -lc "cd '/mnt/d/TheRecon/new wizard' &&
  python3 -m wizard.main; exec bash"`, get its top-level **HWND**, and
  **reparent it into the Qt pane** with Win32 `SetParent` (ctypes `user32`):
  strip `WS_CAPTION`/borders (`GetWindowLong`/`SetWindowLong` with
  `WS_CHILD`), then `MoveWindow` to track the pane on `resizeEvent`. Result =
  the exact cmd-with-WSL-Ubuntu experience the user showed (full reflow, resize,
  color). Prefer classic **conhost** over `wt.exe` — Windows Terminal's window
  model is much harder to reparent reliably.
- **Linux** → reparent a real terminal via XEmbed, e.g. `xterm -into <winId>
  -e bash -lc "cd '<repo>/new wizard' && python3 -m wizard.main"`, tracking the
  pane the same way. (If XEmbed/xterm is unavailable, fall back to a posix PTY
  backend: `ptyprocess` or stdlib `pty`/`os.openpty` feeding the existing
  pyte renderer.)
- **Fallback chain** (keep, don't delete): reparent → `PtyTerminal` (pyte) →
  `InteractiveTerminal` (plain pipe). Guard every backend import so a missing
  dependency degrades instead of crashing.

Implementation notes / gotchas:
- Reparenting is **hacky**: expect first-frame flicker, focus handoff, and DPI
  quirks. Handle focus (`SetFocus`/click-through), resize tracking, and clean
  teardown (kill the child console on `stop()`/close).
- Finding the HWND: spawn, then poll `EnumWindows`/match by PID
  (`GetWindowThreadProcessId`) — the console HWND is not the `wsl.exe` PID
  directly; it's the hosting `conhost`/`WindowsTerminal` process.
- Keep the wizard-launch command identical across backends (only the host
  terminal differs).

## Remaining problems / TODO checklist

- [ ] **Cross-platform terminal backend** (the task above) — Windows conhost
      reparent + Linux xterm/ptyprocess, with fallback chain.
- [ ] **Linux verification** — install the 6 tools on Kali/Ubuntu, run
      `python3 -m wizard.main` natively (should already work), then the GUI.
- [ ] **PtyTerminal reflow** — only relevant if the reparent path is abandoned;
      pyte history reflow is hard, treat as won't-fix in favor of reparent.
- [ ] **GitHub PR** — branch `feat/new-wizard-chain` is pushed but no PR (the
      `gh` CLI is not installed). Either `winget install GitHub.cli` or open the
      PR via the browser link git printed.
- [ ] **Dead code still present** (not wizard, kept for now): `src/ui/
      tool_selection.py`, `src/ui/llm_mode.py` — remove if desired.
- [ ] **DPI/width polish** — on high-DPI displays column count may still feel
      tight; banner/section already adapt to terminal width.
- [ ] **evil-winrm end-to-end** — only reachable on a Windows target with WinRM
      (5985/5986); Metasploitable2 (Linux) can't exercise it. SSH brute against
      Metasploitable2 fails on legacy crypto (target-side, not a bug).

## Known-good verification commands

```bash
# CLI standalone (inside WSL on Windows, or native on Linux)
cd "/mnt/d/TheRecon/new wizard" && python3 -m wizard.main

# Compile-check everything
cd "/mnt/d/TheRecon/new wizard" && python3 -m py_compile core/*.py library/*.py wizard/*.py

# GUI (use the venv OR a python that has pyte+pywinpty)
python -m src.main    # Wizard Console page = the embedded terminal
```

Tested target: Metasploitable2 `192.168.229.134` (ftp/telnet/smb/mysql brute
with `msfadmin:msfadmin` → loot → post-exploit all verified).
