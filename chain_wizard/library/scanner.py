"""
Port scanner abstraction — supports nmap and masscan.
"""

import os
from datetime import datetime
from core.display import section, warn, fail
from core.executor import run_cmd
from core.models import ScanResult
from library.parser import parse_gnmap


def scan_target(target: str) -> list[ScanResult]:
    """
    Interactive port scan — user picks scanner and parameters.
    Returns a list of open ports with service names.
    """
    section("PHASE 1 — PORT SCANNING")

    print("  Select scanner:")
    print("    1. nmap quick   (top 1000 ports, -sS -sV -T4)")
    print("    2. nmap full    (all 65535 ports, -sS -sV -T4)")
    print("    3. nmap stealth (ninja mode — slow, fragmented, decoys; evades IDS/firewall)")
    print("    4. masscan      (all ports, fast, requires sudo)")
    choice = input("  Choice [1-4]: ").strip()
    while choice not in ("1", "2", "3", "4"):
        warn(f"'{choice}' is not a valid choice — enter 1, 2, 3, or 4.")
        choice = input("  Choice [1-4]: ").strip()

    logfile = f"scan_{datetime.now():%Y%m%d_%H%M%S}.log"
    gnmap_file = ""

    if choice in ("1", "2"):
        flags = "-p-" if choice == "2" else ""
        gnmap_file = "scan.gnmap"
        cmd = (
            f"sudo nmap -sS -sV -T4 --min-rate=1000 "
            f"{flags} -oG {gnmap_file} {target}"
        )
        run_cmd(cmd, logfile)

    elif choice == "3":
        # Ninja stealth: half-open SYN, slow timing, fragmented packets,
        # spoofed DNS source port, random decoys + payload padding. No -sV
        # (version probes do full handshakes = loud). Top-1000 ports only —
        # a stealth full sweep would take days.
        # Timing is tunable: lower = quieter/slower, higher = louder/faster.
        #   0 paranoid · 1 sneaky · 2 polite · 3 normal · 4 aggressive · 5 insane
        tval = input("  Timing -T [0-5, lower = stealthier] [1]: ").strip() or "1"
        if tval not in ("0", "1", "2", "3", "4", "5"):
            warn(f"Invalid -T '{tval}' — falling back to -T1.")
            tval = "1"
        gnmap_file = "scan.gnmap"
        cmd = (
            f"sudo nmap -sS -T{tval} -f -g 53 -D RND:5 --data-length 25 "
            f"--randomize-hosts -oG {gnmap_file} {target}"
        )
        if tval in ("0", "1"):
            warn(f"Stealth -T{tval} is slow by design — even top-1000 ports can take a long while.")
        elif tval in ("4", "5"):
            warn(f"-T{tval} is fast but LOUD — stealth evasion is largely defeated at this timing.")
        run_cmd(cmd, logfile)

    elif choice == "4":
        rate = input("  Masscan rate (pkts/s) [1000]: ").strip() or "1000"
        gnmap_file = "masscan.gnmap"
        cmd = (
            f"sudo masscan -p1-65535 --rate={rate} "
            f"-oG {gnmap_file} {target}"
        )
        run_cmd(cmd, logfile)

    else:
        fail("Invalid scanner choice — aborting scan.")
        return []

    # Parse results
    results = parse_gnmap(gnmap_file) if os.path.exists(gnmap_file) else []

    # Cleanup
    if gnmap_file and os.path.exists(gnmap_file):
        os.remove(gnmap_file)

    return results