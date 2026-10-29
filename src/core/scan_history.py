from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

RUNNING = "running"
FINISHED = "finished"
STOPPED = "stopped"
FAILED = "failed"
INTERRUPTED = "interrupted"

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "chain_wizard" / "results" / "history"

_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

CHECKPOINT_SUFFIX = ".checkpoint.json"
RESUMABLE_STATUSES = (INTERRUPTED, STOPPED, FAILED)


def _now() -> str:
    return datetime.now().strftime(_TIME_FORMAT)


@dataclass
class Run:
    id: str
    target: str
    started: str
    status: str = RUNNING
    updated: str = ""
    log_path: str = ""
    exit_code: int | None = None
    rows: list[list[str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Run:
        return cls(
            id=data["id"],
            target=data.get("target", ""),
            started=data.get("started", ""),
            status=data.get("status", INTERRUPTED),
            updated=data.get("updated", ""),
            log_path=data.get("log_path", ""),
            exit_code=data.get("exit_code"),
            rows=[list(row) for row in data.get("rows", [])],
        )


class ScanHistory:
    def __init__(self, root: Path | None = None):
        self._root = Path(root) if root is not None else DEFAULT_ROOT

    def start(self, target: str) -> Run:
        run = Run(id=uuid.uuid4().hex[:12], target=target, started=_now(), updated=_now())
        self._save(run)
        return run

    def add_row(self, run: Run, cells: tuple[str, ...]) -> None:
        run.rows.append([str(cell) for cell in cells])
        self._touch(run)

    def set_log_path(self, run: Run, log_path: str) -> None:
        run.log_path = log_path
        self._touch(run)

    def finish(self, run: Run, status: str, exit_code: int | None = None) -> None:
        if run.status != RUNNING:
            return
        run.status = status
        run.exit_code = exit_code
        self._touch(run)

    def load(self, run_id: str) -> Run | None:
        path = self._path(run_id)
        if not path.is_file():
            return None
        return Run.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def runs(self) -> list[Run]:
        if not self._root.is_dir():
            return []
        loaded = []
        for path in self._root.glob("*.json"):
            if path.name.endswith(CHECKPOINT_SUFFIX):
                continue
            try:
                loaded.append(Run.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError, KeyError):
                continue
        return sorted(loaded, key=lambda run: run.started, reverse=True)

    def reopen(self, run: Run) -> None:
        run.status = RUNNING
        run.exit_code = None
        self._touch(run)

    def checkpoint_path(self, run_id: str) -> Path:
        return self._root / f"{run_id}{CHECKPOINT_SUFFIX}"

    def resumable(self, run: Run) -> bool:
        if run.status not in RESUMABLE_STATUSES:
            return False
        path = self.checkpoint_path(run.id)
        if not path.is_file():
            return False
        try:
            return not json.loads(path.read_text(encoding="utf-8")).get("finished", False)
        except (OSError, ValueError):
            return False

    def mark_interrupted(self) -> int:
        marked = 0
        for run in self.runs():
            if run.status == RUNNING:
                run.status = INTERRUPTED
                self._touch(run)
                marked += 1
        return marked

    def _touch(self, run: Run) -> None:
        run.updated = _now()
        self._save(run)

    def _path(self, run_id: str) -> Path:
        return self._root / f"{run_id}.json"

    def _save(self, run: Run) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._path(run.id)
        tmp = path.with_suffix(".json.tmp")
        payload = {
            "id": run.id,
            "target": run.target,
            "started": run.started,
            "status": run.status,
            "updated": run.updated,
            "log_path": run.log_path,
            "exit_code": run.exit_code,
            "rows": run.rows,
        }
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
