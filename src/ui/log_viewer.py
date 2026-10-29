from __future__ import annotations

import html
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSplitter,
    QTextBrowser,
    QVBoxLayout, QWidget,
)

from src.config import (
    ACCENT_GREEN, ACCENT_RED, BG_APP, BG_INPUT, BORDER, BORDER_SOFT, ORANGE,
    PANEL, PURPLE, PURPLE_DIM, TERMINAL_FONT_FAMILY, TEXT, TEXT_DIM, TEXT_MUTE,
)
from src.core.log_parser import (
    LineKind, classify_line, header_fields, read_text, status_for, tool_of,
)

MODES = (
    ("all", "All"),
    ("findings", "Findings"),
    ("errors", "Errors"),
    ("warnings", "Warnings"),
    ("failed", "Failed commands"),
)
_MODE_KIND = {
    "findings": LineKind.FINDING,
    "errors": LineKind.ERROR,
    "warnings": LineKind.WARNING,
}
_LINE_COLOR = {
    LineKind.PLAIN: TEXT,
    LineKind.FINDING: ACCENT_GREEN,
    LineKind.ERROR: ACCENT_RED,
    LineKind.WARNING: ORANGE,
}
_STATUS_COLOR = {
    "ok": TEXT,
    "failed": ACCENT_RED,
    "timeout": ORANGE,
    "unknown": TEXT_MUTE,
}
_STATUS_LABEL = {
    "ok": "OK",
    "failed": "FAILED",
    "timeout": "TIMED OUT",
    "unknown": "NO EXIT CODE",
}
_GUTTER = TEXT_MUTE
RENDER_LIMIT = 6000
_COMMAND = PURPLE
_HIT = PURPLE_DIM
_CURRENT_HIT = ORANGE
_HIT_TEXT = BG_APP


@dataclass(frozen=True)
class ViewOptions:
    needle: str = ""
    regex: bool = False
    case_sensitive: bool = False
    mode: str = "all"
    tool: str | None = None
    only_matches: bool = False
    current_match: int = 0


@dataclass(frozen=True)
class Section:
    anchor: str
    started: str
    tool: str
    status: str
    findings: int
    errors: int
    warnings: int
    line: int
    visible: bool = False


@dataclass
class RenderResult:
    html: str
    sections: list[Section] = field(default_factory=list)
    total_lines: int = 0
    shown_lines: int = 0
    matches: int = 0
    pattern_error: str | None = None
    totals: dict[str, int] = field(default_factory=dict)
    tools: dict[str, int] = field(default_factory=dict)
    truncated: bool = False

    @property
    def visible_sections(self) -> list[Section]:
        return [section for section in self.sections if section.visible]


@dataclass
class _Block:
    start: int
    end: int
    fields: tuple[str, str, str] | None


class _SearchField(QLineEdit):
    previousRequested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)                 and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.previousRequested.emit()
            return
        super().keyPressEvent(event)


class _Counter:
    def __init__(self, current: int):
        self.count = 0
        self.current = current


def find_logs(chain_dir: Path) -> list[Path]:
    candidates = list((chain_dir / "results" / "logs").glob("*.log"))
    candidates += list(chain_dir.glob("chain_*.log")) + list(chain_dir.glob("scan_*.log"))
    unique = {path.resolve(): path for path in candidates if path.is_file()}
    return sorted(unique.values(), key=lambda p: p.stat().st_mtime, reverse=True)


def _scan(lines: list[str]) -> list[_Block]:
    blocks: list[_Block] = []
    index = 0
    while index < len(lines):
        fields = header_fields(lines, index)
        if fields is None:
            blocks.append(_Block(index, index + 1, None))
            index += 1
            continue
        end = index + 2
        while end < len(lines) and header_fields(lines, end) is None:
            end += 1
        blocks.append(_Block(index, end, fields))
        index = end
    return blocks


def _compile(options: ViewOptions) -> tuple[re.Pattern | None, str | None]:
    if not options.needle:
        return None, None
    flags = 0 if options.case_sensitive else re.IGNORECASE
    source = options.needle if options.regex else re.escape(options.needle)
    try:
        pattern = re.compile(source, flags)
    except re.error as exc:
        return None, str(exc)
    if pattern.match(""):
        return None, "pattern matches empty text"
    return pattern, None


def _highlight(text: str, pattern: re.Pattern | None, counter: _Counter) -> str:
    if pattern is None:
        return html.escape(text, quote=False)
    pieces: list[str] = []
    cursor = 0
    for match in pattern.finditer(text):
        pieces.append(html.escape(text[cursor:match.start()], quote=False))
        index = counter.count
        counter.count += 1
        color = _CURRENT_HIT if index == counter.current else _HIT
        pieces.append(
            f'<a name="m{index}"></a><span style="background-color:{color}; '
            f'color:{_HIT_TEXT}">{html.escape(match.group(0), quote=False)}</span>'
        )
        cursor = match.end()
    pieces.append(html.escape(text[cursor:], quote=False))
    return "".join(pieces)


def _gutter(number: int) -> str:
    return f'<span style="color:{_GUTTER}">{number:>5}   </span>'


def _body_line(number: int, text: str, pattern, counter: _Counter) -> str:
    color = _LINE_COLOR[classify_line(text)]
    return (f'{_gutter(number)}<span style="color:{color}">'
            f"{_highlight(text, pattern, counter)}</span>")


def _section_header(number: int, section: Section) -> str:
    color = _STATUS_COLOR.get(section.status, TEXT_MUTE)
    findings = f"{section.findings} finding(s)" if section.findings else "no findings"
    return (
        f'{_gutter(number)}<a name="{section.anchor}"></a>'
        f'<span style="color:{color}">▌ {_STATUS_LABEL[section.status]}</span>'
        f'   <span style="color:{TEXT_DIM}">{html.escape(section.started)}</span>'
        f'   <span style="color:{TEXT}">{html.escape(section.tool)}</span>'
        f'   <span style="color:{TEXT_DIM}">{findings}</span>'
    )


def _command_line(number: int, command: str, pattern, counter: _Counter) -> str:
    return (f'{_gutter(number)}<span style="color:{_COMMAND}">$ '
            f"{_highlight(command, pattern, counter)}</span>")


def _section_passes(section: Section, options: ViewOptions, pattern, texts: list[str]) -> bool:
    if options.tool and section.tool != options.tool:
        return False
    if options.mode == "failed" and section.status not in ("failed", "timeout"):
        return False
    if options.mode == "findings" and not section.findings:
        return False
    if options.mode == "errors" and not section.errors:
        return False
    if options.mode == "warnings" and not section.warnings:
        return False
    if options.only_matches and pattern is not None:
        return any(pattern.search(text) for text in texts)
    return True


def _line_passes(text: str, options: ViewOptions, pattern) -> bool:
    kind_needed = _MODE_KIND.get(options.mode)
    if kind_needed is not None and classify_line(text) is not kind_needed:
        return False
    if options.only_matches and pattern is not None and pattern.search(text) is None:
        return False
    return True


def _totals(blocks: list[_Block], lines: list[str]) -> dict[str, int]:
    totals = {"commands": 0, "findings": 0, "errors": 0, "warnings": 0,
              "failed": 0, "timed_out": 0}
    for block in blocks:
        if block.fields is None:
            kinds = [classify_line(lines[block.start])]
        else:
            totals["commands"] += 1
            status = status_for(block.fields[1])
            totals["failed"] += status == "failed"
            totals["timed_out"] += status == "timeout"
            kinds = [classify_line(line) for line in lines[block.start + 2:block.end]]
        totals["findings"] += kinds.count(LineKind.FINDING)
        totals["errors"] += kinds.count(LineKind.ERROR)
        totals["warnings"] += kinds.count(LineKind.WARNING)
    return totals


def render_log(text: str, options: ViewOptions | None = None) -> RenderResult:
    options = options or ViewOptions()
    pattern, error = _compile(options)
    lines = text.splitlines()
    blocks = _scan(lines)
    counter = _Counter(options.current_match)
    rendered: list[str] = []
    sections: list[Section] = []
    tools: dict[str, int] = {}
    shown = 0
    truncated = False

    def budget_left() -> bool:
        return len(rendered) < RENDER_LIMIT

    for block in blocks:
        if block.fields is None:
            line_passes = options.tool is None and options.mode != "failed"
            if line_passes and _line_passes(lines[block.start], options, pattern):
                if budget_left():
                    rendered.append(_body_line(block.start + 1, lines[block.start], pattern, counter))
                    shown += 1
                else:
                    truncated = True
            continue

        started, exit_text, command = block.fields
        body = lines[block.start + 2:block.end]
        tool = tool_of(command)
        tools[tool] = tools.get(tool, 0) + 1
        section = Section(
            anchor=f"sec{block.start + 1}",
            started=started,
            tool=tool,
            status=status_for(exit_text),
            findings=sum(classify_line(l) is LineKind.FINDING for l in body),
            errors=sum(classify_line(l) is LineKind.ERROR for l in body),
            warnings=sum(classify_line(l) is LineKind.WARNING for l in body),
            line=block.start + 1,
        )
        visible = _section_passes(section, options, pattern, [command] + body)
        section = replace(section, visible=visible)
        sections.append(section)
        if not visible:
            continue
        if not budget_left():
            truncated = True
            continue

        if rendered:
            rendered.append("")
        rendered.append(_section_header(block.start + 1, section))
        rendered.append(_command_line(block.start + 2, command, pattern, counter))
        shown += 2
        last = max((i for i, line in enumerate(body) if line.strip()), default=-1)
        for offset, line in enumerate(body[:last + 1]):
            if not budget_left():
                truncated = True
                break
            if _line_passes(line, options, pattern):
                rendered.append(_body_line(block.start + 3 + offset, line, pattern, counter))
                shown += 1

    return RenderResult(
        html=_wrap("\n".join(rendered)),
        sections=sections,
        total_lines=len(lines),
        shown_lines=shown,
        matches=counter.count,
        pattern_error=error,
        totals=_totals(blocks, lines),
        tools=tools,
        truncated=truncated,
    )


def _wrap(body: str) -> str:
    return (
        f'<html><body style="background-color:{BG_INPUT}; color:{TEXT};">'
        f'<pre style="font-family:\'{TERMINAL_FONT_FAMILY}\', monospace; font-size:10pt; '
        f'margin:0; white-space:pre-wrap;">{body}</pre></body></html>'
    )


class LogViewerDialog(QDialog):
    def __init__(self, paths: list[Path], selected: Path | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Scan log")
        self.resize(1200, 760)
        self.setStyleSheet(self._qss())

        self._text: str | None = None
        self._path: Path | None = None
        self._result: RenderResult | None = None
        self._current = 0

        self._files = QComboBox()
        self._files.setObjectName("LogFiles")
        self._files.setMinimumWidth(480)
        for path in paths:
            self._files.addItem(path.name, str(path))
        self._files.currentIndexChanged.connect(self._load_current)

        self._open_btn = QPushButton("Open file…")
        self._open_btn.clicked.connect(self._open_file)
        self._reload_btn = QPushButton("Reload")
        self._reload_btn.clicked.connect(self._load_current)
        self._meta = QLabel()
        self._meta.setObjectName("LogMeta")

        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        file_row.addWidget(self._files, 1)
        file_row.addWidget(self._open_btn)
        file_row.addWidget(self._reload_btn)

        self._stats = QLabel()
        self._stats.setObjectName("LogStats")

        self._mode_buttons: dict[str, QPushButton] = {}
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for key, label in MODES:
            button = QPushButton(label)
            button.setObjectName("Chip")
            button.setCheckable(True)
            button.setChecked(key == "all")
            button.clicked.connect(self._reset_and_render)
            self._mode_group.addButton(button)
            self._mode_buttons[key] = button
            chips.addWidget(button)
        chips.addStretch(1)

        self._search = _SearchField()
        self._search.setObjectName("LogSearch")
        self._search.setPlaceholderText("Find in this log   (Enter = next · Shift+Enter = previous)")
        self._search.setClearButtonEnabled(True)
        self._search.returnPressed.connect(self.find_next)
        self._search.previousRequested.connect(self.find_previous)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(140)
        self._debounce.timeout.connect(self._reset_and_render)
        self._search.textChanged.connect(lambda _t: self._debounce.start())

        self._regex = QPushButton(".*")
        self._regex.setObjectName("Toggle")
        self._regex.setCheckable(True)
        self._regex.setToolTip("Treat the search as a regular expression")
        self._regex.clicked.connect(self._reset_and_render)
        self._case = QPushButton("Aa")
        self._case.setObjectName("Toggle")
        self._case.setCheckable(True)
        self._case.setToolTip("Match case")
        self._case.clicked.connect(self._reset_and_render)
        self._prev_btn = QPushButton("‹")
        self._prev_btn.setObjectName("Toggle")
        self._prev_btn.setToolTip("Previous match (Shift+Enter, Shift+F3)")
        self._prev_btn.clicked.connect(self.find_previous)
        self._next_btn = QPushButton("›")
        self._next_btn.setObjectName("Toggle")
        self._next_btn.setToolTip("Next match (Enter, F3)")
        self._next_btn.clicked.connect(self.find_next)
        self._counter = QLabel("0 / 0")
        self._counter.setObjectName("LogMeta")
        self._counter.setMinimumWidth(64)
        self._counter.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._tool = QComboBox()
        self._tool.setObjectName("LogTool")
        self._tool.setMinimumWidth(170)
        self._tool.currentIndexChanged.connect(self._reset_and_render)
        self._only = QCheckBox("Only matching lines")
        self._only.toggled.connect(self._reset_and_render)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        search_row.addWidget(self._search, 1)
        search_row.addWidget(self._regex)
        search_row.addWidget(self._case)
        search_row.addWidget(self._prev_btn)
        search_row.addWidget(self._counter)
        search_row.addWidget(self._next_btn)

        option_row = QHBoxLayout()
        option_row.setSpacing(10)
        option_row.addWidget(QLabel("Tool"))
        option_row.addWidget(self._tool)
        option_row.addSpacing(12)
        option_row.addWidget(self._only)
        option_row.addStretch(1)

        self._timeline = QListWidget()
        self._timeline.setObjectName("LogTimeline")
        self._timeline.setMinimumWidth(270)
        self._timeline.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._timeline.setWordWrap(True)
        self._timeline.itemClicked.connect(self._jump_to_item)
        timeline_head = QLabel("COMMANDS")
        timeline_head.setObjectName("LogSectionHeader")

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(timeline_head)
        left_layout.addWidget(self._timeline, 1)

        self._browser = QTextBrowser()
        self._browser.setObjectName("LogBody")
        self._browser.setOpenLinks(False)
        self._browser.setReadOnly(True)
        self._browser.setFont(self._mono_font())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addLayout(search_row)
        right_layout.addLayout(option_row)
        right_layout.addWidget(self._browser, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 900])

        self._status = QLabel()
        self._status.setObjectName("LogStatus")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)
        root.addLayout(file_row)
        root.addWidget(self._meta)
        root.addWidget(self._stats)
        root.addLayout(chips)
        root.addWidget(splitter, 1)
        root.addWidget(self._status)

        self._install_shortcuts()

        if selected is not None:
            index = self._files.findData(str(selected))
            if index >= 0:
                self._files.setCurrentIndex(index)
        self._load_current()

    def _install_shortcuts(self) -> None:
        bindings = (
            (QKeySequence("F3"), self, self.find_next),
            (QKeySequence("Shift+F3"), self, self.find_previous),
            (QKeySequence("Ctrl+F"), self, self._search.setFocus),
            (QKeySequence("Escape"), self._search, self._search.clear),
        )
        for sequence, parent, handler in bindings:
            shortcut = QShortcut(sequence, parent)
            shortcut.activated.connect(handler)

    def _mode(self) -> str:
        for key, button in self._mode_buttons.items():
            if button.isChecked():
                return key
        return "all"

    def _options(self) -> ViewOptions:
        tool = self._tool.currentData()
        return ViewOptions(
            needle=self._search.text().strip(),
            regex=self._regex.isChecked(),
            case_sensitive=self._case.isChecked(),
            mode=self._mode(),
            tool=tool or None,
            only_matches=self._only.isChecked(),
            current_match=self._current,
        )

    def _reset_and_render(self, *_args) -> None:
        self._current = 0
        self._render()

    def _render(self, navigate: bool = False) -> None:
        if self._text is None:
            return
        scroll = self._browser.verticalScrollBar().value()
        self._result = render_log(self._text, self._options())
        self._browser.setHtml(self._result.html)
        if navigate and self._result.matches:
            self._browser.scrollToAnchor(f"m{self._current}")
        else:
            self._browser.verticalScrollBar().setValue(scroll)
        self._refresh_chrome()

    def _refresh_chrome(self) -> None:
        result = self._result
        totals = result.totals
        self._mode_buttons["findings"].setText(f"Findings  {totals.get('findings', 0)}")
        self._mode_buttons["errors"].setText(f"Errors  {totals.get('errors', 0)}")
        self._mode_buttons["warnings"].setText(f"Warnings  {totals.get('warnings', 0)}")
        failed = totals.get("failed", 0) + totals.get("timed_out", 0)
        self._mode_buttons["failed"].setText(f"Failed commands  {failed}")

        self._stats.setText(
            f"{totals.get('commands', 0)} commands    ·    "
            f"{totals.get('findings', 0)} findings    ·    "
            f"{totals.get('errors', 0)} error lines    ·    "
            f"{totals.get('warnings', 0)} warning lines    ·    "
            f"{totals.get('failed', 0)} failed    ·    "
            f"{totals.get('timed_out', 0)} timed out")

        needle = self._options().needle
        if result.matches and needle:
            self._counter.setText(f"{self._current + 1} / {result.matches}")
        else:
            self._counter.setText("0 / 0")

        self._fill_timeline(result)
        self._fill_tools(result)
        self._status.setText(self._status_text(result))

    def _status_text(self, result: RenderResult) -> str:
        parts = [f"Showing {result.shown_lines:,} of {result.total_lines:,} lines",
                 f"{len(result.visible_sections)} of {len(result.sections)} commands"]
        if self._options().needle and result.pattern_error:
            parts.append(f"invalid pattern: {result.pattern_error}")
        elif self._options().needle:
            parts.append(f"{result.matches} match(es)")
        if result.truncated:
            parts.append(f"first {RENDER_LIMIT:,} lines only — narrow the filter or search to see the rest")
        return "   ·   ".join(parts)

    def _fill_timeline(self, result: RenderResult) -> None:
        self._timeline.clear()
        for section in result.visible_sections:
            label = (f"{section.started[11:]}   {section.tool}\n"
                     f"{_STATUS_LABEL[section.status]}   ·   {section.findings} finding(s)"
                     f"   ·   line {section.line}")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, section.anchor)
            item.setForeground(QColor(_STATUS_COLOR.get(section.status, TEXT_MUTE)))
            self._timeline.addItem(item)

    def _fill_tools(self, result: RenderResult) -> None:
        selected = self._tool.currentData()
        self._tool.blockSignals(True)
        self._tool.clear()
        self._tool.addItem(f"All tools  ({sum(result.tools.values())})", "")
        for name, count in sorted(result.tools.items(), key=lambda kv: (-kv[1], kv[0])):
            self._tool.addItem(f"{name}  ({count})", name)
        index = self._tool.findData(selected) if selected else 0
        self._tool.setCurrentIndex(max(index, 0))
        self._tool.blockSignals(False)

    def _load_current(self, *_args) -> None:
        self._path = self._files.currentData()
        self._path = Path(self._path) if self._path else None
        if self._path is None:
            self._show_message("No log files yet.",
                               "A log appears here once a scan runs its first command. "
                               "Use “Open file…” to read any .txt or .log file.")
            return
        try:
            self._text = read_text(self._path)
            stat = self._path.stat()
        except OSError as exc:
            self._show_message("Could not read this file.", str(exc))
            return
        self._meta.setText(
            f"{self._path}   ·   {stat.st_size:,} bytes   ·   "
            f"modified {datetime.fromtimestamp(stat.st_mtime):%Y-%m-%d %H:%M}")
        self.setWindowTitle(f"Scan log — {self._path.name}")
        self._current = 0
        self._browser.verticalScrollBar().setValue(0)
        self._render()

    def _show_message(self, title: str, detail: str) -> None:
        self._text = None
        self._result = None
        self._meta.setText("")
        self._stats.setText("")
        self._status.setText(title)
        self._timeline.clear()
        self._counter.setText("0 / 0")
        self._browser.setHtml(
            f'<html><body style="background-color:{BG_INPUT};">'
            f'<p style="color:{TEXT}; font-size:12pt">{html.escape(title)}</p>'
            f'<p style="color:{TEXT_DIM}; font-size:10pt">{html.escape(detail)}</p>'
            f"</body></html>")

    def _jump_to_item(self, item: QListWidgetItem) -> None:
        anchor = item.data(Qt.ItemDataRole.UserRole)
        if anchor:
            self._browser.scrollToAnchor(anchor)

    def find_next(self) -> None:
        self._step(1)

    def find_previous(self) -> None:
        self._step(-1)

    def _step(self, delta: int) -> None:
        if self._result is None or not self._result.matches or not self._options().needle:
            return
        self._current = (self._current + delta) % self._result.matches
        self._render(navigate=True)

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open log file", "",
            "Log and text files (*.txt *.log);;All files (*)")
        if not path:
            return
        index = self._files.findData(path)
        if index < 0:
            self._files.addItem(Path(path).name, path)
            index = self._files.count() - 1
        self._files.setCurrentIndex(index)

    @staticmethod
    def _mono_font() -> QFont:
        font = QFont(TERMINAL_FONT_FAMILY)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        return font

    @staticmethod
    def _qss() -> str:
        return f"""
            QDialog {{ background: {PANEL}; }}
            QLabel {{ color: {TEXT_DIM}; font-size: 12px; background: transparent; }}
            QLabel#LogMeta {{ color: {TEXT_MUTE}; font-size: 11px; }}
            QLabel#LogStats {{ color: {TEXT}; font-size: 12px; }}
            QLabel#LogStatus {{ color: {TEXT_MUTE}; font-size: 11px; padding-top: 2px; }}
            QLabel#LogSectionHeader {{ color: {TEXT_MUTE}; font-size: 10px; }}
            QTextBrowser#LogBody {{
                background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 8px; padding: 12px;
            }}
            QListWidget#LogTimeline {{
                background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 8px; padding: 4px; font-size: 12px; outline: 0;
            }}
            QListWidget#LogTimeline::item {{
                padding: 8px 10px; border-radius: 6px; margin: 1px 0px;
            }}
            QListWidget#LogTimeline::item:hover {{ background: {BORDER_SOFT}; }}
            QListWidget#LogTimeline::item:selected {{ background: {PURPLE_DIM}; color: {TEXT}; }}
            QLineEdit, QComboBox {{
                background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 7px 10px; selection-background-color: {PURPLE_DIM};
            }}
            QLineEdit:focus, QComboBox:focus {{ border: 1px solid {PURPLE}; }}
            QComboBox QAbstractItemView {{
                background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
                selection-background-color: {PURPLE_DIM};
            }}
            QPushButton {{
                background: {BG_INPUT}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 7px 14px;
            }}
            QPushButton:hover {{ border: 1px solid {PURPLE_DIM}; }}
            QPushButton#Chip {{
                background: transparent; color: {TEXT_DIM}; border: 1px solid {BORDER};
                border-radius: 14px; padding: 6px 14px;
            }}
            QPushButton#Chip:hover {{ color: {TEXT}; border: 1px solid {PURPLE_DIM}; }}
            QPushButton#Chip:checked {{
                background: {PURPLE_DIM}; color: {TEXT}; border: 1px solid {PURPLE};
            }}
            QPushButton#Toggle {{
                background: {BG_INPUT}; color: {TEXT_DIM}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 6px 10px; min-width: 22px;
            }}
            QPushButton#Toggle:checked {{
                background: {PURPLE_DIM}; color: {TEXT}; border: 1px solid {PURPLE};
            }}
            QCheckBox {{ color: {TEXT_DIM}; spacing: 8px; }}
        """
