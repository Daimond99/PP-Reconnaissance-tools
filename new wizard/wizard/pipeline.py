"""
Pipeline — maps scan results to executable attack steps based on the selected mode.
"""

from core.models import ScanResult, Step, AttackPlan
from library.attack_map import steps_for_port, recommended_steps_for_port
from core.display import info, warn, cyan, green, yellow, bold, magenta

# Tools that are follow-up actions requiring a credential first — never queued
# as standalone plan steps. They are only reached AFTER a brute-force step
# harvests a credential (e.g. evil-winrm via chain._offer_winrm).
FOLLOWUP_TOOLS = {"evil-winrm"}


def _primary_steps(steps: list[Step]) -> list[Step]:
    """Drop credential-required follow-up steps; keep only runnable primaries."""
    return [s for s in steps if s.tool not in FOLLOWUP_TOOLS]


def step_priority(step: Step) -> int:
    """
    Rank a step by exploitation value (higher = closer to a shell/RCE):
      5 = direct RCE / shell       (evil-winrm, smb-vuln/EternalBlue)
      4 = brute-force on a high-value service (ssh, smb, rdp, winrm) → creds → shell
      3 = brute-force on other services, or nmap vuln scan
      2 = enumeration / info gathering only
    """
    name = step.name.lower()
    tool = step.tool

    if tool == "evil-winrm":
        return 5
    if tool == "nmap" and ("smb-vuln" in name or "eternalblue" in name):
        return 5
    if tool in ("hydra", "ncrack"):
        if any(s in name for s in ("ssh", "smb", "rdp", "winrm")):
            return 4
        return 3
    if tool == "nmap":
        return 3 if "vuln" in name else 2
    return 3


def build_plan(
    target: str,
    user_wordlist: str,
    pass_wordlist: str,
    scan_results: list[ScanResult],
    mode: str,  # "auto" or "semi"
) -> AttackPlan:
    """
    Build an AttackPlan from scan results.
    - auto: auto-selects only is_recommended steps per port.
    - semi: presents all available steps and lets user choose.
    """
    plan = AttackPlan(
        target=target,
        user_wordlist=user_wordlist,
        pass_wordlist=pass_wordlist,
    )

    for result in sorted(scan_results, key=lambda r: r.port):
        port = result.port
        service = result.service or "unknown"

        all_steps = _primary_steps(steps_for_port(port))
        if not all_steps:
            warn(f"Port {port} ({service}) — no registered attack steps.")
            continue

        if mode == "auto":
            selected = _primary_steps(recommended_steps_for_port(port))
            if not selected:
                selected = all_steps  # fallback
            for step in selected:
                plan.steps.append((port, service, step))
            info(f"Port {port}: {len(selected)} recommended step(s) queued.")

        elif mode == "semi":
            _show_steps_for_port(port, service, all_steps)
            picks = input(f"  {cyan('Select numbers (e.g. 1,2 or 0 to skip): ')}").strip()
            if picks == "0":
                warn(f"Skipping port {port}.")
                continue
            for part in picks.split(","):
                part = part.strip()
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(all_steps):
                        plan.steps.append((port, service, all_steps[idx]))

    return plan


def _show_steps_for_port(port: int, service: str, steps: list[Step]) -> None:
    """Print a numbered menu of available steps for a single port."""
    print(f"\n  {'─' * 50}")
    print(f"  Port {bold(str(port))} ({cyan(service)}) — available steps:")
    for i, step in enumerate(steps, 1):
        tag = green("[recommended]") if step.is_recommended else yellow("[alternative]")
        print(f"    {green(str(i))}. {magenta(f'[{step.tool}]')} {step.name} {tag}")
    print(f"    {green('0')}. {yellow('Skip this port')}")