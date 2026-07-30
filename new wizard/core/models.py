"""
Shared data models used across all layers.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Step:
    """An atomic attack step mapped to a single port."""
    name: str
    tool: str
    command_template: str
    impact: str
    is_recommended: bool = False


@dataclass(frozen=True)
class ScanResult:
    """A single open port discovered during scanning."""
    port: int
    service: str  # may be empty string if unknown


@dataclass
class AttackPlan:
    """
    The full execution plan for a target.
    Built by the pipeline and consumed by the chain orchestrator.
    """
    target: str
    user_wordlist: str
    pass_wordlist: str
    steps: list[tuple[int, str, Step]] = field(default_factory=list)
    #  (port, service, step)

    logfile: str = field(default_factory=lambda: (
        f"chain_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    ))
