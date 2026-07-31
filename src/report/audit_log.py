"""
Audit log — append-only JSONL trail of confirmation decisions.

The single active writer is `audit_log_llm`, called by `ConfirmationGate` for
every Direct Tool Mode Execute: it records the channel, command, target,
confirmation response, and executed/exit result — but NEVER any secret. This
is the app's safety/audit record, so it is deliberately kept even though
nothing reads it back inside the GUI.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

_AUDIT_LOG_PATH = Path("logs") / "audit_log.jsonl"


def audit_log_llm(channel: str, command: str, target: str, response: str,
                   executed: bool, provider: Optional[str] = None,
                   extra: Optional[Dict] = None) -> None:
    """
    Append one gated-command decision to the audit trail. Records the channel
    (e.g. "direct") and provider for every confirmation decision — never the
    real secret. Best-effort, never raises.
    """
    try:
        _AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
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
        with _AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
