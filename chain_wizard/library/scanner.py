"""
Port scanner abstraction — supports nmap and masscan.
"""

import os
from datetime import datetime
from core.display import section, warn, impact_box, cyan
from core.executor import run_cmd
from core.models import ScanResult
from library.parser import parse_gnmap


def _confirm_impact(cmd: str, impact: str) -> bool:
    """Show the command + a boxed impact note, ask for explicit 'yes'.
    Same pattern as the per-step confirmation later in the chain
    (wizard/chain.py::_execute_step) — Phase 1 wasn't following it before,
    so a scan could fire with no impact warning shown at all."""
    print(f"\n  $ {cmd}")
    impact_box(impact)
    confirm = input(f"  {cyan('Accept impact and proceed? (type yes to run) ')}").strip().lower()
    return confirm == "yes"


def scan_target(target: str) -> list[ScanResult]:
    """
    Interactive port scan — user picks scanner and parameters.
    Returns a list of open ports with service names.
    """
    section("PHASE 1 — PORT SCANNING")

    logfile = f"scan_{datetime.now():%Y%m%d_%H%M%S}.log"
    gnmap_file = "scan.gnmap"

    # Loop the menu itself: a sub-prompt (stealth timing, masscan profile)
    # can answer 'b' to back out to this menu instead of committing to a
    # scan type by mistake and having to Ctrl-C the whole wizard (which
    # also throws away the target/wordlists already entered).
    while True:
        print("  Select scanner:")
        print("    1. nmap quick    (top 1000 ports, -sS -sV -T4)")
        print("    2. nmap top100   (100 most common ports, -sS -sV -T4 — fastest useful sweep)")
        print("    3. nmap full     (all 65535 ports, -sS -sV -T4)")
        print("    4. nmap stealth  (ninja mode — slow, fragmented, decoys; evades IDS/firewall)")
        print("    5. nmap web      (web ports only: 80,443,8080,8443, -sV)")
        print("    6. nmap vuln     (top 1000 ports + NSE vuln scripts, -sV --script vuln)")
        print("    7. masscan       (fast raw-socket scanner — pick a profile next)")
        choice = input("  Choice [1-7]: ").strip()
        if choice not in ("1", "2", "3", "4", "5", "6", "7"):
            warn(f"'{choice}' is not a valid choice — enter 1-7.")
            continue

        if choice in ("1", "2", "3"):
            flags = {"1": "", "2": "--top-ports 100", "3": "-p-"}[choice]
            cmd = (
                f"sudo nmap -sS -sV -T4 --min-rate=1000 "
                f"{flags} -oG {gnmap_file} {target}"
            )
            impact = {
                "1": "SYN + version-probe packets against the top 1000 ports — may be detected/logged by target IDS/firewall.",
                "2": "SYN + version-probe packets against the 100 most common ports — lighter footprint than quick/full.",
                "3": "SYN + version-probe packets against all 65535 ports — much slower and noisier, higher detection chance.",
            }[choice]
            if not _confirm_impact(cmd, impact):
                warn("Scan declined — back to scanner menu.")
                continue
            run_cmd(cmd, logfile)
            break

        elif choice == "4":
            # Ninja stealth: half-open SYN, slow timing, fragmented packets,
            # spoofed DNS source port, random decoys + payload padding. No
            # -sV (version probes do full handshakes = loud). Top-1000
            # ports only — a stealth full sweep would take days.
            # Timing is tunable: lower = quieter/slower, higher = louder.
            #   0 paranoid · 1 sneaky · 2 polite · 3 normal · 4 aggressive · 5 insane
            tval = input("  Timing -T [0-5, lower = stealthier, 'b' = back] [1]: ").strip() or "1"
            if tval == "b":
                continue
            if tval not in ("0", "1", "2", "3", "4", "5"):
                warn(f"Invalid -T '{tval}' — falling back to -T1.")
                tval = "1"
            cmd = (
                f"sudo nmap -sS -T{tval} -f -g 53 -D RND:5 --data-length 25 "
                f"--randomize-hosts -oG {gnmap_file} {target}"
            )
            if tval in ("0", "1"):
                warn(f"Stealth -T{tval} is slow by design — even top-1000 ports can take a long while.")
            elif tval in ("4", "5"):
                warn(f"-T{tval} is fast but LOUD — stealth evasion is largely defeated at this timing.")
            impact = (
                f"Fragmented, decoy-padded half-open SYN scan at -T{tval} against the top 1000 ports — "
                "quieter than a plain scan but still a real, loggable probe, not invisible."
            )
            if not _confirm_impact(cmd, impact):
                warn("Scan declined — back to scanner menu.")
                continue
            run_cmd(cmd, logfile)
            break

        elif choice == "5":
            cmd = (
                f"nmap -sV -p 80,443,8080,8443 "
                f"-oG {gnmap_file} {target}"
            )
            impact = "Version-probes only ports 80/443/8080/8443 — light footprint, minimal noise."
            if not _confirm_impact(cmd, impact):
                warn("Scan declined — back to scanner menu.")
                continue
            run_cmd(cmd, logfile)
            break

        elif choice == "6":
            cmd = (
                f"nmap -sV --script vuln "
                f"-oG {gnmap_file} {target}"
            )
            impact = (
                "Runs intrusive NSE vulnerability-detection scripts on top of a version scan — "
                "sends extra probes some services may log loudly or even crash on; slower than a plain scan."
            )
            if not _confirm_impact(cmd, impact):
                warn("Scan declined — back to scanner menu.")
                continue
            run_cmd(cmd, logfile)
            break

        elif choice == "7":
            gnmap_file = "masscan.gnmap"
            if _masscan_scan(target, logfile, gnmap_file) == "back":
                gnmap_file = "scan.gnmap"
                continue
            break

    # Parse results
    results = parse_gnmap(gnmap_file) if os.path.exists(gnmap_file) else []

    # Cleanup
    if gnmap_file and os.path.exists(gnmap_file):
        os.remove(gnmap_file)

    return results


def _masscan_scan(target: str, logfile: str, gnmap_file: str) -> str | None:
    """Masscan profile sub-menu. Returns 'back' to reopen the scanner menu,
    else runs the chosen scan and returns None."""
    print("  masscan profile:")
    print("    1. Common services  (21,22,23,25,53,80,110,143,443,445,3389,8080 — rate 5000)")
    print("    2. Full port blast  (1-65535 — rate 100000, very loud/fast)")
    print("    3. Banner grab      (1-65535 --banners — rate 25000)")
    print("    4. Slow/stealthy    (1-1000 — rate 50)")
    print("    5. Custom           (enter your own ports + rate)")
    choice = input("  Choice [1-5, 'b' = back]: ").strip().lower()
    if choice == "b":
        return "back"

    profiles = {
        "1": ("-p 21,22,23,25,53,80,110,143,443,445,3389,8080 --rate 5000",
              "Moderate-rate SYN blast against common service ports — noticeable but not extreme."),
        "2": ("-p 1-65535 --rate 100000",
              "Extremely high packet rate across all 65535 ports — very loud, near-certain IDS/IPS alert, "
              "traffic pattern can resemble a DoS."),
        "3": ("-p 1-65535 --rate 25000 --banners",
              "All 65535 ports plus live connections for service banners — loud, and the banner grabs "
              "themselves show up in target service logs."),
        "4": ("-p 1-1000 --rate 50 --wait 5",
              "Low, deliberately slow rate — quietest masscan profile here, still a real unencrypted probe."),
    }
    if choice in profiles:
        flags, impact = profiles[choice]
    elif choice == "5":
        ports = input("  Ports (e.g. 1-1000 or 80,443) ['b' = back] [1-65535]: ").strip()
        if ports == "b":
            return "back"
        ports = ports or "1-65535"
        rate = input("  Rate (pkts/s) [1000]: ").strip() or "1000"
        flags = f"-p {ports} --rate {rate}"
        impact = f"Custom masscan sweep — {ports} at {rate} pkts/s. Higher rate = louder, more detectable."
    else:
        warn(f"'{choice}' is not valid — defaulting to Common services.")
        flags, impact = profiles["1"]

    cmd = f"sudo masscan {flags} -oG {gnmap_file} {target}"
    if not _confirm_impact(cmd, impact):
        return "back"
    run_cmd(cmd, logfile)
    return None
