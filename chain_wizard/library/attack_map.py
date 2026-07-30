"""
Central repository of attack steps, indexed by port number.
Each entry is a list of Step objects describing what can be run
against that service.

The arsenal itself now lives in `attack_map.json` (same directory) so it can
be edited as data, not code. This module loads that JSON into Step objects and
exposes the same lookup API as before. When adding new ports, edit the JSON —
do not hardcode steps here.
"""

import json
from pathlib import Path

from core.models import Step

_JSON_PATH = Path(__file__).with_name("attack_map.json")


def _load_attack_map() -> dict[int, list[Step]]:
    """Load the arsenal from attack_map.json into a {port: [Step, ...]} dict."""
    with open(_JSON_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    result: dict[int, list[Step]] = {}
    for port_str, steps in raw.items():
        result[int(port_str)] = [
            Step(
                name=s["name"],
                tool=s["tool"],
                command_template=s["command_template"],
                impact=s["impact"],
                is_recommended=s.get("is_recommended", False),
            )
            for s in steps
        ]
    return result


ATTACK_MAP: dict[int, list[Step]] = _load_attack_map()


def steps_for_port(port: int) -> list[Step]:
    """Return all attack steps registered for a port, or an empty list."""
    return ATTACK_MAP.get(port, [])


def recommended_steps_for_port(port: int) -> list[Step]:
    """Return only steps marked is_recommended=True for the given port."""
    return [s for s in ATTACK_MAP.get(port, []) if s.is_recommended]
