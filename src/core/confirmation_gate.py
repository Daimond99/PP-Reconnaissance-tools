"""
Confirmation Gate — shared "human in the loop" safety gate.

This wraps the validation/analysis/report safety primitives (impact
description, preview box rendering, exact "yes" confirmation, scope check,
audit logging) into a single reusable object so every execution path in the
app — Wizard Console, LLM Mode Plain, and LLM Mode AI — goes through the
exact same checks before anything ever touches QProcess.

No command is ever executed on the strength of an LLM suggestion alone:
`request()` only prepares a preview; `execute()` is a separate, explicit step
that requires an exact "yes" from the user.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.config import AUTHORIZED_SCOPE
from src.report.audit_log import audit_log_llm
from src.tools.nmap.analyzer import (
    format_confirmation_box,
    generate_impact_description,
    is_target_in_scope,
)
from src.validation.common import parse_command_line, validate_exact_confirmation


@dataclass
class GateResult:
    ok: bool
    message: str
    preview_box: Optional[str] = None
    argv: Optional[List[str]] = None


class ConfirmationGate:
    """
    One gate instance per pending command. Usage:

        gate = ConfirmationGate(channel="ai", provider="openai")
        result = gate.request(command, target)
        if not result.ok:
            show(result.message); return
        show(result.preview_box)
        # ... later, once the user types the exact word "yes" ...
        if gate.confirm(user_reply):
            argv = gate.argv
            # run argv via QProcess
        else:
            gate.cancel(user_reply)
    """

    def __init__(self, channel: str, provider: Optional[str] = None,
                 scope: str = AUTHORIZED_SCOPE):
        self.channel = channel  # "plain" | "ai" | "wizard"
        self.provider = provider
        self.scope = scope
        self.command: str = ""
        self.target: str = ""
        self.argv: List[str] = []
        self._pending = False

    def request(self, command: str, target: str, extra_impact: Optional[str] = None,
                argv_override: Optional[List[str]] = None, skip_scope: bool = False) -> GateResult:
        """
        Validate + build the preview box for a candidate command. Never executes.

        extra_impact  : appended to the auto-generated impact text — used for
                         tool-specific high-severity warnings (e.g. Ncat listen
                         mode opening a port, Evil-WinRM getting direct shell
                         access) that the generic nmap-flag-based impact
                         description can't know about.
        argv_override : if given, this is what actually gets executed instead
                         of the argv parsed from `command`. Lets the caller
                         pass a MASKED `command` string (e.g. with the real
                         password replaced by asterisks) for the preview box
                         and audit log, while still running the real argv.
                         The real secret is therefore never previewed, logged,
                         or stored on `self.command` — only `self.argv`.
        skip_scope     : skip the in-scope check — for operations with no
                         remote target (e.g. Ncat listen mode binds locally).
        """
        command = (command or "").strip()
        target = (target or "").strip()

        if not skip_scope:
            ok, err = is_target_in_scope(target, self.scope)
            if not ok:
                self._pending = False
                return GateResult(False, f"[!] Scope violation: {err}")

        ok, err, argv = parse_command_line(command)
        if not ok:
            self._pending = False
            return GateResult(False, f"[!] Rejected command: {err}")

        flags = [tok for tok in argv[1:] if tok != target]
        impact = generate_impact_description(flags, target)
        if extra_impact:
            impact = f"{impact}\n              {extra_impact}"
        preview = format_confirmation_box(command, target, impact)

        self.command = command  # masked display string — this is what gets logged, never the secret
        self.target = target
        self.argv = argv_override if argv_override is not None else argv
        self._pending = True
        return GateResult(True, "OK", preview_box=preview, argv=self.argv)

    def confirm(self, reply: str) -> bool:
        """Returns True only if `reply` is the exact literal 'yes'."""
        if not self._pending:
            return False
        confirmed = validate_exact_confirmation((reply or "").strip())
        audit_log_llm(
            channel=self.channel,
            command=self.command,
            target=self.target,
            response=reply,
            executed=confirmed,
            provider=self.provider,
        )
        if not confirmed:
            self._pending = False
        return confirmed

    def cancel(self, reason: str = "user_cancelled") -> None:
        audit_log_llm(
            channel=self.channel,
            command=self.command,
            target=self.target,
            response=reason,
            executed=False,
            provider=self.provider,
        )
        self._pending = False

    def mark_executed_result(self, exit_code: int) -> None:
        """Optional: log the outcome once the process finishes."""
        audit_log_llm(
            channel=self.channel,
            command=self.command,
            target=self.target,
            response="process_finished",
            executed=True,
            provider=self.provider,
            extra={"exit_code": exit_code},
        )
