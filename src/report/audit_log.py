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

# Size-based rotation so the compliance trail doesn't grow forever on a
# long-lived install: once the live file crosses this size it's rolled to
# .1 (bumping any existing .1..N-1 up a slot), oldest backup beyond
# _MAX_BACKUPS is dropped. History is kept, not deleted outright — just
# capped to roughly (_MAX_BACKUPS + 1) * _MAX_LOG_BYTES on disk.
_MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB per file
_MAX_BACKUPS = 3


def _backup_path(n: int) -> Path:
    return _AUDIT_LOG_PATH.parent / f"{_AUDIT_LOG_PATH.name}.{n}"


def _rotate_if_needed() -> None:
    if not _AUDIT_LOG_PATH.exists() or _AUDIT_LOG_PATH.stat().st_size < _MAX_LOG_BYTES:
        return
    oldest = _backup_path(_MAX_BACKUPS)
    if oldest.exists():
        oldest.unlink()
    for n in range(_MAX_BACKUPS - 1, 0, -1):
        src = _backup_path(n)
        if src.exists():
            src.rename(_backup_path(n + 1))
    _AUDIT_LOG_PATH.rename(_backup_path(1))


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
        _rotate_if_needed()
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
