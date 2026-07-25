"""
Audit log — append-only JSONL trail of confirmation decisions.
Reporting is responsible only for exporting/saving/formatting/history
(docs/Resource System.md #10, Reporting).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

_AUDIT_LOG_PATH = Path("logs") / "wizard_audit_log.jsonl"
_LLM_AUDIT_LOG_PATH = Path("logs") / "llm_mode_audit_log.jsonl"


def audit_log_llm(channel: str, command: str, target: str, response: str,
                   executed: bool, provider: Optional[str] = None,
                   extra: Optional[Dict] = None) -> None:
    """
    Dedicated audit trail for LLM Mode (Plain + AI). Records which channel
    (plain/ai) and provider (openai/anthropic/None) were used for every
    confirmation decision — but NEVER the API key itself.
    Best-effort, never raises.
    """
    try:
        _LLM_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
            "provider": provider,
            "command": command,
            "target": target,
            "response": response,
            "executed": executed,
        }
        if extra:
            entry.update(extra)
        with _LLM_AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def audit_log_confirmation(command: str, target: str, response: str, executed: bool) -> None:
    """Append a confirmation decision to the audit log (best-effort, never raises)."""
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "target": target,
            "response": response,
            "executed": executed,
        }
        with _AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # Audit logging must never block or crash the wizard flow.
        pass


def audit_log_fallback(
    *, target: str, step: str, rejected_tool: str, fallback_tool: str,
    detected_ports: List[int], reason: str,
) -> None:
    """Record an Auto Chain fallback decision without exposing credentials."""
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "auto_chain_fallback",
            "target": target,
            "step": step,
            "rejected_tool": rejected_tool,
            "fallback_tool": fallback_tool,
            "detected_ports": sorted(set(detected_ports)),
            "reason": reason,
        }
        with _AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def audit_log_cancel(command: str, target: str, reason: str = "user_cancelled") -> None:
    """Append a cancellation event to the audit log (best-effort, never raises)."""
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "cancel",
            "command": command,
            "target": target,
            "reason": reason,
        }
        with _AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
