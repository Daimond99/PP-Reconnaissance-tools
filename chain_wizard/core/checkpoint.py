from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Checkpoint:
    target: str
    user_wordlist: str
    pass_wordlist: str
    logfile: str = ""
    scan: list[dict] | None = None
    selected: list[str] | None = None
    outcomes: dict[str, str] = field(default_factory=dict)
    finished: bool = False

    @staticmethod
    def step_key(port: int, service: str, tool: str, name: str) -> str:
        return f"{port}|{service}|{tool}|{name}"

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, target)

    @classmethod
    def load(cls, path: str | Path) -> Checkpoint:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            target=data["target"],
            user_wordlist=data.get("user_wordlist", ""),
            pass_wordlist=data.get("pass_wordlist", ""),
            logfile=data.get("logfile", ""),
            scan=data.get("scan"),
            selected=data.get("selected"),
            outcomes=dict(data.get("outcomes", {})),
            finished=bool(data.get("finished", False)),
        )
