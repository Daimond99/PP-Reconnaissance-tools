"""Shared test fixtures.

Puts the repo root on `sys.path` so `import src...` works no matter how
pytest is launched, and keeps every test off the real audit log on disk:
`ConfirmationGate` calls `audit_log_llm` on confirm/cancel, which would
otherwise append to `logs/audit_log.jsonl` during a test run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.core import confirmation_gate  # noqa: E402  (after sys.path setup)


@pytest.fixture
def audit(monkeypatch):
    """Capture audit-log calls instead of writing them to disk. Tests that
    want to assert on logging request this fixture; it returns the list of
    recorded kwargs dicts."""
    calls: list[dict] = []
    monkeypatch.setattr(confirmation_gate, "audit_log_llm",
                        lambda **kw: calls.append(kw))
    return calls


@pytest.fixture(autouse=True)
def _silence_audit(monkeypatch, request):
    """Every test that doesn't explicitly use `audit` still gets the audit
    logger stubbed to a no-op, so no test touches `logs/audit_log.jsonl`."""
    if "audit" in request.fixturenames:
        return  # the `audit` fixture installs its own recorder
    monkeypatch.setattr(confirmation_gate, "audit_log_llm", lambda **kw: None)
