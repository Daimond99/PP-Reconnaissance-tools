"""Auto Chain fallback policy and state for Recon -> Action.

The UI owns command construction and execution.  This module deliberately owns
only the decision policy so every caller (the PySide wizard and future UIs)
gets identical fallback behaviour and can send *each* proposal through the
normal ConfirmationGate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, Set

from src.report.audit_log import audit_log_fallback
from src.core.confirmation_gate import ConfirmationGate, GateResult


FALLBACK_MAP = {
    "nmap": "masscan",
    "masscan": "nmap",
    "hydra": "ncrack",
    "ncrack": "hydra",
}

# Ports accepted by the command builders in this application.  Hydra's RDP
# support is intentionally marked limited: it is a fallback, never the first
# recommendation for an RDP-only result.
NCRACK_PORTS = frozenset({21, 22, 23, 80, 110, 139, 143, 443, 445, 3389, 5900})
HYDRA_PORTS = frozenset({21, 22, 23, 80, 110, 139, 143, 443, 445, 3389, 5900})
HYDRA_LIMITED_PORTS = frozenset({3389})
WINRM_PORTS = frozenset({5985, 5986})


class ChainStep(str, Enum):
    PRE_SCAN = "pre_scan"
    BRUTE_FORCE = "brute_force"
    CREDENTIAL_SOURCE = "credential_source"
    EVIL_WINRM = "evil_winrm"
    COMPLETE = "complete"


@dataclass(frozen=True)
class FallbackSuggestion:
    tool: str
    reason: str
    warning: Optional[str] = None


@dataclass
class AutoChainState:
    """State shared between Auto Chain prompts; never stores a password."""

    target: str = ""
    current_step: ChainStep = ChainStep.PRE_SCAN
    detected_ports: Set[int] = field(default_factory=set)
    rejected_tools: Set[str] = field(default_factory=set)
    proposed_tool: Optional[str] = None
    credential_available: bool = False

    def set_detected_ports(self, ports: Iterable[int]) -> None:
        self.detected_ports = {int(port) for port in ports if int(port) > 0}


def suggest_fallback_tool(
    current_step: ChainStep, rejected_tool: str, detected_ports: Iterable[int],
) -> Optional[FallbackSuggestion]:
    """Return a compatible fallback and an operator-facing reason, if one exists.

    Compatibility is checked before a tool is presented.  In particular, Hydra
    is not advertised as the preferred choice for an RDP-only result; when it
    is the remaining fallback its limitation is explicit.
    """
    rejected_tool = rejected_tool.lower()
    candidate = FALLBACK_MAP.get(rejected_tool)
    ports = {int(port) for port in detected_ports}
    if not candidate:
        return None

    if current_step == ChainStep.PRE_SCAN:
        reasons = {
            "masscan": "สแกน subnet นี้ได้เร็วกว่ามาก จึงใช้แทนการสแกนละเอียดได้",
            "nmap": "ให้ผลการสแกนและระบุ service ละเอียดกว่า จึงใช้แทนการ sweep ได้",
        }
        return FallbackSuggestion(candidate, reasons[candidate])

    if current_step != ChainStep.BRUTE_FORCE:
        return None

    supported = NCRACK_PORTS if candidate == "ncrack" else HYDRA_PORTS
    compatible_ports = ports & supported
    if not compatible_ports:
        return None

    port_text = ", ".join(str(port) for port in sorted(compatible_ports))
    warning = None
    if candidate == "hydra" and compatible_ports <= HYDRA_LIMITED_PORTS:
        warning = (
            "[!] Hydra รองรับ RDP ได้จำกัดกว่า Ncrack "
            "ผลลัพธ์อาจไม่แม่นยำเท่า"
        )
    return FallbackSuggestion(
        candidate,
        f"รองรับ protocol เดียวกันบน port {port_text} ได้ จึงใช้ต่อกับผล scan เดียวกันได้",
        warning,
    )


class AutoChainFallbackController:
    """Advance fallback choices and write audit events.

    ``reject_current_tool`` is called only after the user answers ``no`` or
    ``skip`` at the existing confirmation gate.  The returned suggestion must
    be rendered through that gate again; this controller never executes tools.
    """

    def __init__(self, state: Optional[AutoChainState] = None) -> None:
        self.state = state or AutoChainState()

    def propose(self, tool: str) -> None:
        self.state.proposed_tool = tool

    def reject_current_tool(self, rejected_tool: str) -> Optional[FallbackSuggestion]:
        rejected_tool = rejected_tool.lower()
        self.state.rejected_tools.add(rejected_tool)
        suggestion = suggest_fallback_tool(
            self.state.current_step, rejected_tool, self.state.detected_ports
        )
        if suggestion and suggestion.tool not in self.state.rejected_tools:
            self.state.proposed_tool = suggestion.tool
            audit_log_fallback(
                target=self.state.target,
                step=self.state.current_step.value,
                rejected_tool=rejected_tool,
                fallback_tool=suggestion.tool,
                detected_ports=list(self.state.detected_ports),
                reason=suggestion.reason,
            )
            return suggestion
        self.state.proposed_tool = None
        return None

    def request_confirmation(
        self, gate: ConfirmationGate, command: str, suggestion: FallbackSuggestion,
    ) -> GateResult:
        """Put this proposal through the application's normal confirmation gate.

        Callers must create a fresh gate for each suggestion and must call
        ``gate.confirm(reply)`` before execution.  This keeps fallback tools
        subject to exactly the same scope validation, preview and exact-yes
        rule as an initially proposed tool.
        """
        impact = suggestion.reason
        if suggestion.warning:
            impact = f"{suggestion.warning}\n{impact}"
        return gate.request(command, self.state.target, extra_impact=impact)

    def no_brute_force_credential(self) -> FallbackSuggestion:
        self.state.current_step = ChainStep.CREDENTIAL_SOURCE
        self.state.proposed_tool = "manual_entry"
        return FallbackSuggestion(
            "manual_entry",
            "ไม่มี credential จากการ brute-force; การกรอกเองทำให้ดำเนินการต่อด้วย Evil-WinRM ได้",
        )

    def reject_manual_entry(self) -> None:
        self.state.proposed_tool = None
        self.state.current_step = ChainStep.COMPLETE
