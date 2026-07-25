"""
Hydra Analyzer — risk/impact evaluation for the Human Confirmation Gate.

Analysis never modifies execution results and never executes anything
(docs/ARCHITECTURE.md, Analysis Layer). It produces the plain-language impact
text the confirmation gate shows before a brute-force run.
"""

from __future__ import annotations

from typing import List


def generate_impact_description(service: str, target: str,
                               login_is_file: bool, password_is_file: bool) -> str:
    """Plain-language impact summary for a hydra brute-force run."""
    notes: List[str] = [
        f"Brute-force login attack against {service} on {target}.",
    ]
    if password_is_file:
        notes.append(
            "Uses a PASSWORD LIST — potentially thousands of login attempts; "
            "this is noisy and will show up in the target's auth logs."
        )
    else:
        notes.append("Tries a single password.")
    if login_is_file:
        notes.append("Uses a USERNAME LIST — attempts multiplied across users.")

    notes.append(
        "[!] Repeated failed logins can lock out accounts or trip fail2ban / "
        "IDS. Only run against a target you are explicitly authorized to test."
    )
    return "\n              ".join(notes)
