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
        "Version-probes only ports 80/443/8080/8443 — light footprint, minimal noise.",
    ),
    "6": (
        "nmap -sV --script vuln -oG {gnmap} {target}",
        "Runs intrusive NSE vulnerability-detection scripts on top of a version scan — "
        "sends extra probes some services may log loudly or even crash on; slower than a plain scan.",
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
        "Skips the ping check and fragments packets to get past basic firewalls, while "
        "checking the ~200 most common ports at normal speed — still a real, loggable scan, "
        "just less likely to be dropped outright by simple filtering.",
    ),
    "8": (
        "sudo nmap -A -T4 --top-ports 100 -oG {gnmap} {target}",
        "Combines OS detection, version detection, default NSE scripts, and traceroute in one "
        "scan — the most thorough single-pass option here, and the easiest for a target to notice.",
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
        "UDP scan of the 100 most common UDP ports (DNS, DHCP, SNMP, etc.) -- much slower "
        "than a TCP scan of the same size, and closed vs. filtered ports are often "
        "indistinguishable (both just get no reply).",
    ),
}


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
                "2. nmap top100    (100 most common ports, -sS -sV -T4 — fastest useful sweep)",
                "3. nmap full      (all 65535 ports, -sS -sV -T4)",
                "4. nmap stealth   (ninja mode — slow, fragmented, decoys; evades IDS/firewall)",
                "5. nmap web       (web ports only: 80,443,8080,8443, -sV)",
                "6. nmap vuln      (top 1000 ports + NSE vuln scripts, -sV --script vuln)",
                "7. nmap evasion   (skips ping + fragments packets to slip past basic firewalls — popular ports only, still fast)",
                "8. nmap aggressive (top 100 ports + OS/version/script/traceroute in one pass — thorough, easy to detect)",
                "9. masscan        (fast raw-socket scanner — pick a profile next)",
                "10. nmap UDP       (top 100 UDP ports, -sU -sV — DNS/DHCP/SNMP-style services, slower than TCP)",
            ],
        )
        if choice not in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10"):
            warn(f"'{choice}' is not a valid choice — enter 1-10.")
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
                f"Fragmented, decoy-padded half-open SYN scan at -T{tval} against the top 1000 ports — "
                "quieter than a plain scan but still a real, loggable probe, not invisible."
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
              "Moderate-rate SYN blast against common service ports — noticeable but not extreme."),
        "2": ("-p 1-65535 --rate 100000",
              "Extremely high packet rate across all 65535 ports — very loud, near-certain IDS/IPS alert, "
              "traffic pattern can resemble a DoS."),
        "3": ("-p 1-65535 --rate 25000 --banners",
              "All 65535 ports plus live connections for service banners — loud, and the banner grabs "
              "themselves show up in target service logs."),
        "4": ("-p 1-1000 --rate 50 --wait 5",
              "Low, deliberately slow rate — quietest full-range masscan profile here, still a real unencrypted probe."),
        "5": ("-p 22,80,443 --rate 20 --wait 3",
              "Only checks SSH/HTTP/HTTPS at a very low rate — the quietest option here, useful when even "
              "a slow full sweep is too much noise."),
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
        impact = f"Custom masscan sweep — {ports} at {rate} pkts/s. Higher rate = louder, more detectable."
    else:
        warn(f"'{choice}' is not valid — defaulting to Common services.")
        flags, impact = profiles["1"]

    cmd = f"sudo masscan {flags} -oG {gnmap_file} {target}"
    if not _confirm_impact(cmd, impact):
        return "back"
    run_cmd(cmd, logfile)
    return None
