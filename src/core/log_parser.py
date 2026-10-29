from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

_HEADER = re.compile(
    r"^# (?P<stamp>\d{4}-\d{2}-\d{2}T[\d:.]+)(?: exit=(?P<exit>\S+))?\s*$"
)
_COMMAND = re.compile(r"^\$ (?P<cmd>.*)$")

_OPEN_PORT = re.compile(r"^\d+/(tcp|udp)\s+open\b")
_CREDENTIAL = re.compile(
    r"login:\s*\S+.*password:|Discovered credentials|valid password", re.IGNORECASE
)
_ERROR = re.compile(
    r"\berror\b|\bexception\b|\bfailed\b|\bnot found\b|Errno|timed? ?out", re.IGNORECASE
)
_WARNING = re.compile(r"\bwarn(ing)?\b|\bfiltered\b", re.IGNORECASE)


class LineKind(Enum):
    PLAIN = "plain"
    FINDING = "finding"
    ERROR = "error"
    WARNING = "warning"


def classify_line(line: str) -> LineKind:
    if _OPEN_PORT.search(line) or _CREDENTIAL.search(line):
        return LineKind.FINDING
    if _ERROR.search(line):
        return LineKind.ERROR
    if _WARNING.search(line):
        return LineKind.WARNING
    return LineKind.PLAIN


def tool_of(command: str) -> str:
    tokens = command.split()
    if tokens and tokens[0] == "sudo":
        tokens = tokens[1:]
    return tokens[0] if tokens else "-"


def status_for(exit_text: str) -> str:
    if exit_text == "timeout":
        return "timeout"
    if exit_text == "?":
        return "unknown"
    try:
        return "ok" if int(exit_text) == 0 else "failed"
    except ValueError:
        return "unknown"


@dataclass
class LogEntry:
    started: str
    command: str
    exit_text: str
    output: list[str] = field(default_factory=list)

    @property
    def tool(self) -> str:
        return tool_of(self.command)

    @property
    def status(self) -> str:
        return status_for(self.exit_text)

    def count(self, kind: LineKind) -> int:
        return sum(1 for line in self.output if classify_line(line) is kind)

    @property
    def findings(self) -> int:
        return self.count(LineKind.FINDING)

    @property
    def errors(self) -> int:
        return self.count(LineKind.ERROR)

    def text(self) -> str:
        return "\n".join(self.output)


def _entry_start(lines: list[str], index: int) -> tuple[re.Match, re.Match] | None:
    if index + 1 >= len(lines):
        return None
    header = _HEADER.match(lines[index])
    command = _COMMAND.match(lines[index + 1])
    if header and command:
        return header, command
    return None


def header_fields(lines: list[str], index: int) -> tuple[str, str, str] | None:
    start = _entry_start(lines, index)
    if start is None:
        return None
    header, command = start
    return (
        header.group("stamp").replace("T", " ")[:19],
        header.group("exit") or "?",
        command.group("cmd"),
    )


def parse_log(text: str) -> list[LogEntry]:
    lines = text.splitlines()
    entries: list[LogEntry] = []
    index = 0
    while index < len(lines):
        fields = header_fields(lines, index)
        if fields is None:
            index += 1
            continue
        started, exit_text, command = fields
        body_end = index + 2
        while body_end < len(lines) and header_fields(lines, body_end) is None:
            body_end += 1
        body = lines[index + 2:body_end]
        while body and not body[-1].strip():
            body.pop()
        entries.append(LogEntry(started=started, command=command, exit_text=exit_text, output=body))
        index = body_end
    return entries


def read_log(path: Path) -> list[LogEntry]:
    return parse_log(read_text(path))


def read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")
