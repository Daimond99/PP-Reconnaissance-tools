"""
Port scanner abstraction — supports nmap and masscan.
"""

import os
from datetime import datetime
from core.display import section, warn
from core.executor import run_cmd
from core.models import ScanResult
from core.ui_driver import get_ui
from library.parser import parse_gnmap


def _confirm_impact(cmd: str, impact: str, title: str = "Port scan") -> bool:
    """Show the command + impact, ask for explicit 'yes'. Same pattern as
    the per-step confirmation later in the chain (wizard/chain.py) — Phase 1
    wasn't following it before, so a scan could fire with no impact warning
    shown at all."""
    return get_ui().confirm(cmd, impact, title=title)


# Single-shot profiles: build a cmd + impact string from `gnmap_file` and
# `target` only, no extra prompt needed first (unlike choice 4's -T prompt
# or choice 9's masscan sub-menu, which stay special-cased in `scan_target`).
# Template + confirm/run/break used to be copy-pasted once per choice —
# collapsed to one dict + one shared tail so a new profile is one entry,
# not another copy of the same four lines.
_SIMPLE_SCAN_PROFILES = {
    "5": (
        "nmap -sV -p 80,443,8080,8443 -oG {gnmap} {target}",
        "Checks only the web ports (80, 443, 8080, 8443) and what software runs on them. Very little traffic.",
    ),
    "6": (
        "nmap -sV --script vuln -oG {gnmap} {target}",
        "Checks the top 1000 ports for known vulnerabilities. Some checks send attack-like requests, "
        "which the target will log and which can crash weak services. Slower than a plain scan.",
    ),
    # -Pn skips the ping-based host check (many firewalls silently drop
    # ICMP, which would otherwise make nmap think the host is down and
    # skip it entirely), -f fragments packets past firewalls that only
    # inspect whole ones, and --source-port 53 makes the probes look like
    # DNS replies to stateless filters. Deliberately NOT the slow
    # ninja-mode timing of choice 4 — stays on common ports at normal
    # speed so it still finishes in a reasonable time.
    "7": (
        "sudo nmap -sS -sV -Pn -f --source-port 53 -T3 --top-ports 200 -oG {gnmap} {target}",
        "Checks the 200 most common ports at normal speed. It skips the ping check and splits "
        "packets, which can get past simple firewalls. The target can still log it.",
    ),
    "8": (
        "sudo nmap -A -T4 --top-ports 100 -oG {gnmap} {target}",
        "Checks the top 100 ports and tries to identify the operating system, the software "
        "versions, and the route to the target. Very thorough, and very easy for the target to notice.",
    ),
    # UDP needs its own scan type (-sU) -- it can't be combined with -sS in
    # one nmap invocation. Capped to the top 100 UDP ports rather than a
    # full 65535 sweep: nmap has to wait out a timeout on every port that
    # doesn't answer (most UDP services stay silent unless probed with
    # their own protocol), so a full-range UDP scan is dramatically slower
    # than the equivalent TCP one -- top-100 keeps this a reasonable single
    # menu option instead of needing its own timing sub-prompt like choice 4.
    "10": (
        "sudo nmap -sU -sV --top-ports 100 -T4 -oG {gnmap} {target}",
        "Checks the 100 most common UDP services (DNS, DHCP, SNMP). This is much slower than a TCP "
        "scan, and a closed port and a filtered port look the same, so the results can be unclear.",
    ),
    # ─── Basic everyday scans (11-16) ───
    "11": (
        "nmap -sT -T4 --top-ports 1000 -oG {gnmap} {target}",
        "Completes a full TCP connection to the top 1000 ports. Works without root, but every connection "
        "is logged by the target's services, so it is easy to see.",
    ),
    "12": (
        "nmap -sC -sV --top-ports 100 -oG {gnmap} {target}",
        "Checks the top 100 ports, identifies the software, and runs nmap's default safe scripts "
        "(banners, page titles, basic info). A good all-round first look.",
    ),
    "13": (
        "sudo nmap -O --top-ports 100 -oG {gnmap} {target}",
        "Checks the top 100 ports and tries to guess the target's operating system from its replies. Needs sudo.",
    ),
    "14": (
        "nmap -sV -p 21,22,23,25,53,80,110,139,143,443,445,3306,3389,5432,5900,8080 -oG {gnmap} {target}",
        "Checks the 16 most common service ports (FTP, SSH, web, SMB, databases, remote desktop) and "
        "identifies their software versions. Light traffic.",
    ),
    "15": (
        "nmap -F -oG {gnmap} {target}",
        "Fastest scan: checks the 100 most common ports without identifying the software. Short and quiet.",
    ),
    "16": (
        "nmap -sV -p 80,443,139,445 --script http-title,smb-os-discovery -oG {gnmap} {target}",
        "Checks web and file-sharing ports (80, 443, 139, 445) and reads the web page title and "
        "the Windows/Samba OS name. Light traffic.",
    ),
}

_SCAN_MENU_MAX = 16


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
        choice = get_ui().menu(
            "Select scanner:",
            [
                "1. nmap quick     (top 1000 ports, -sS -sV -T4)",
                "2. nmap top100  [RECOMMENDED]  (100 most common ports, -sS -sV -T4 — fastest useful sweep)",
                "3. nmap full      (all 65535 ports, -sS -sV -T4)",
                "4. nmap stealth   (ninja mode — slow, fragmented, decoys; evades IDS/firewall)",
                "5. nmap web       (web ports only: 80,443,8080,8443, -sV)",
                "6. nmap vuln      (top 1000 ports + NSE vuln scripts, -sV --script vuln)",
                "7. nmap evasion   (skips ping + fragments packets to slip past basic firewalls — popular ports only, still fast)",
                "8. nmap aggressive (top 100 ports + OS/version/script/traceroute in one pass — thorough, easy to detect)",
                "9. masscan        (fast raw-socket scanner — pick a profile next)",
                "10. nmap UDP       (top 100 UDP ports, -sU -sV — DNS/DHCP/SNMP-style services, slower than TCP)",
                "11. nmap TCP connect (top 1000 ports, no root needed — full TCP handshake, easy to see in logs)",
                "12. nmap default scripts (top 100 ports, -sC -sV — banners, titles, basic info)",
                "13. nmap OS detect  (top 100 ports, sudo -O — guesses the target operating system)",
                "14. nmap common services (16 common service ports, -sV — FTP/SSH/web/SMB/DB/RDP)",
                "15. nmap fast      (top 100 ports, -F — quickest, no version detection)",
                "16. nmap web + SMB (80,443,139,445, -sV + http-title / smb-os-discovery)",
            ],
        )
        if choice not in [str(n) for n in range(1, _SCAN_MENU_MAX + 1)]:
            warn(f"'{choice}' is not a valid choice — enter 1-{_SCAN_MENU_MAX}.")
            continue

        if choice in ("1", "2", "3"):
            flags = {"1": "", "2": "--top-ports 100", "3": "-p-"}[choice]
            cmd = (
                f"sudo nmap -sS -sV -T4 --min-rate=1000 "
                f"{flags} -oG {gnmap_file} {target}"
            )
            impact = {
                "1": "Checks the top 1000 ports and asks each open one what software it runs. The target may log it.",
                "2": "Checks the 100 most common ports. This is the fastest useful scan and makes less traffic than option 1 or 3.",
                "3": "Checks all 65535 ports. This takes a long time and makes a lot of traffic, so it is easy for the target to notice.",
            }[choice]
            if not _confirm_impact(cmd, impact):
                warn("Scan declined — back to scanner menu.")
                continue
            run_cmd(cmd, logfile)
            break

        elif choice in _SIMPLE_SCAN_PROFILES:
            tmpl, impact = _SIMPLE_SCAN_PROFILES[choice]
            cmd = tmpl.format(gnmap=gnmap_file, target=target)
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
            tval = get_ui().text("Timing -T [0-5, lower = stealthier, 'b' = back]", "1")
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
                f"Slow, quiet scan of the top 1000 ports (timing level {tval} of 0-5, lower is slower). "
                "It splits packets and adds fake sender addresses, but it is not invisible: the target can still log it."
            )
            if not _confirm_impact(cmd, impact):
                warn("Scan declined — back to scanner menu.")
                continue
            run_cmd(cmd, logfile)
            break

        elif choice == "9":
            gnmap_file = "masscan.gnmap"
            if _masscan_scan(target, logfile, gnmap_file) == "back":
                gnmap_file = "scan.gnmap"
                continue
            break

    # gnmap_file is a bare filename resolved inside the container's own
    # cwd (WORKDIR /results, see docker/Dockerfile) — the container writes
    # it to /results/<gnmap_file>, which docker/run.sh mounts to this
    # repo's chain_wizard/results/ on the host. The wizard process itself
    # runs with cwd=chain_wizard/ (src/core/wizard_driver.py), not
    # chain_wizard/results/, so it must look under "results/" to see the
    # same file the container just wrote.
    host_path = os.path.join("results", gnmap_file)

    # Parse results
    results = parse_gnmap(host_path) if os.path.exists(host_path) else []

    # Cleanup
    if os.path.exists(host_path):
        os.remove(host_path)

    return results


# Matches the loudest canned profile below ("2" — 100000 pkts/s, already
# labeled "very loud/fast" and shown its own confirmation impact text) —
# the ceiling the custom-rate prompt enforces, not an arbitrarily lower one.
_MAX_MASSCAN_RATE = 100_000


def _masscan_scan(target: str, logfile: str, gnmap_file: str) -> str | None:
    """Masscan profile sub-menu. Returns 'back' to reopen the scanner menu,
    else runs the chosen scan and returns None."""
    choice = get_ui().menu(
        "masscan profile:",
        [
            "1. Common services  (21,22,23,25,53,80,110,143,443,445,3389,8080 — rate 5000)",
            "2. Full port blast  (1-65535 — rate 100000, very loud/fast)",
            "3. Banner grab      (1-65535 --banners — rate 25000)",
            "4. Slow/stealthy    (1-1000 — rate 50)",
            "5. Low-rate probe   (22,80,443 only — rate 20, quietest option here)",
            "6. Custom           (enter your own ports + rate)",
        ],
    ).strip().lower()
    if choice == "b":
        return "back"

    profiles = {
        "1": ("-p 21,22,23,25,53,80,110,143,443,445,3389,8080 --rate 5000",
              "Sends a medium-speed burst of probes to 12 common service ports. Noticeable, but not extreme."),
        "2": ("-p 1-65535 --rate 100000",
              "Sends a very fast burst of probes to all 65535 ports. Very loud and almost certain to trigger "
              "an intrusion alert. It can look like a denial-of-service attack."),
        "3": ("-p 1-65535 --rate 25000 --banners",
              "Probes all 65535 ports and connects to read each service's banner (its name and version). "
              "Loud, and the banner requests show up in the target's service logs."),
        "4": ("-p 1-1000 --rate 50 --wait 5",
              "Slow probes to ports 1-1000. The quietest option that covers a full port range here, but still real traffic."),
        "5": ("-p 22,80,443 --rate 20 --wait 3",
              "Very slowly checks only SSH, HTTP and HTTPS. The quietest choice here, for when even a slow sweep is too noisy."),
    }
    if choice in profiles:
        flags, impact = profiles[choice]
    elif choice == "6":
        ports = get_ui().text("Ports (e.g. 1-1000 or 80,443) ['b' = back]", "1-65535")
        if ports == "b":
            return "back"
        rate_raw = get_ui().text("Rate (pkts/s)", "1000")
        # Every canned profile above has a rate the devs already picked and
        # capped at -- this is the one place a rate is free-typed, so it's
        # the one place that needs its own ceiling. `_MAX_MASSCAN_RATE`
        # matches profile "2" (the loudest canned option here) rather than
        # some arbitrary lower number: above that, the risk stops being
        # just "louder/more detectable" and starts being able to actually
        # degrade other hosts/switches sharing the target's network
        # (ARP/CAM-table flooding, link saturation) -- not something a
        # single confirmation-box "yes" should be able to wave through
        # unbounded, unlike port range or which service to hit.
        try:
            rate = int(rate_raw)
        except ValueError:
            warn(f"'{rate_raw}' is not a number — falling back to 1000 pkts/s.")
            rate = 1000
        if rate < 1:
            warn("Rate must be positive — falling back to 1000 pkts/s.")
            rate = 1000
        elif rate > _MAX_MASSCAN_RATE:
            warn(f"{rate} pkts/s is above the {_MAX_MASSCAN_RATE} pkts/s ceiling "
                 f"here — capped to {_MAX_MASSCAN_RATE} pkts/s so other hosts on "
                 "the target's own network don't get knocked over too.")
            rate = _MAX_MASSCAN_RATE
        flags = f"-p {ports} --rate {rate}"
        impact = f"Checks ports {ports} at {rate} packets per second. A higher rate means more traffic and is easier to detect."
    else:
        warn(f"'{choice}' is not valid — defaulting to Common services.")
        flags, impact = profiles["1"]

    cmd = f"sudo masscan {flags} -oG {gnmap_file} {target}"
    if not _confirm_impact(cmd, impact):
        return "back"
    run_cmd(cmd, logfile)
    return None
