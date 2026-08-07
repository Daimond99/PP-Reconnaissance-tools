"""TopBar (Mission Bar) — Target / Operation Mode / Tool / Warhead profile +
the Execute button. Direct Tool Mode's command-building surface."""

from PySide6.QtWidgets import (
    QFrame, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QSizePolicy,
)

from src.config import WARHEAD_BY_TOOL, OPERATION_MODES
from src.core.tool_manager import get_tool_manager
from src.ui.widgets.dropdown import DropdownButton


class TopBar(QFrame):
    """แถบด้านบนสำหรับ Target, Mode และ Command"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MissionBar")
        self._build()

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("MissionFieldLabel")
        return lbl

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 14, 22, 14)
        outer.setSpacing(12)

        # row1: Target, Mode, Tool
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # All four controls share one fixed height so the QLineEdit and the
        # QPushButton-based DropdownButtons (whose native sizeHints don't
        # agree even with identical stylesheet padding) line up exactly.
        _FIELD_HEIGHT = 38

        target_col = QVBoxLayout()
        target_col.setSpacing(5)
        target_col.addWidget(self._field_label("TARGET"))
        self.target_input = QLineEdit()
        self.target_input.setObjectName("MissionCombo")
        self.target_input.setFixedWidth(150)
        self.target_input.setFixedHeight(_FIELD_HEIGHT)
        self.target_input.setText("192.168.1.0/24")
        target_col.addWidget(self.target_input)
        row1.addLayout(target_col)

        mode_col = QVBoxLayout()
        mode_col.setSpacing(5)
        mode_col.addWidget(self._field_label("OPERATION MODE"))
        self.opmode_combo = DropdownButton()
        self.opmode_combo.setObjectName("MissionCombo")
        # Defaults to "Wizard Mode" (index 0 of OPERATION_MODES) — the
        # command box/Execute stay disabled until Direct Tool Mode is
        # explicitly picked (see main_window._on_opmode_change).
        self.opmode_combo.addItems(OPERATION_MODES)
        self.opmode_combo.setFixedWidth(150)
        self.opmode_combo.setFixedHeight(_FIELD_HEIGHT)
        mode_col.addWidget(self.opmode_combo)
        row1.addLayout(mode_col)

        tool_col = QVBoxLayout()
        tool_col.setSpacing(5)
        tool_col.addWidget(self._field_label("TOOLS"))
        tm = get_tool_manager()
        tool_names = [info.display_name for info in tm.tools.values()]
        self.tool_combo = DropdownButton()
        self.tool_combo.setObjectName("MissionCombo")
        self.tool_combo.addItems(tool_names)
        self.tool_combo.setFixedWidth(130)
        self.tool_combo.setFixedHeight(_FIELD_HEIGHT)
        tool_col.addWidget(self.tool_combo)
        row1.addLayout(tool_col)

        profile_col = QVBoxLayout()
        profile_col.setSpacing(5)
        profile_col.addWidget(self._field_label("WARHEAD PROFILE"))
        self.warhead_combo = DropdownButton()
        self.warhead_combo.setObjectName("MissionCombo")
        self.warhead_combo.addItems(WARHEAD_BY_TOOL.get(tool_names[0] if tool_names else "", {}).keys())
        self.warhead_combo.setFixedWidth(220)
        self.warhead_combo.setFixedHeight(_FIELD_HEIGHT)
        profile_col.addWidget(self.warhead_combo)
        row1.addLayout(profile_col)

        row1.addStretch()
        outer.addLayout(row1)

        # row2: command preview/edit + execute
        row2 = QHBoxLayout()
        row2.setSpacing(14)

        self.command_input = QLineEdit("masscan -p1-65535 --rate=10000 192.168.1.0/24")
        self.command_input.setObjectName("CmdPreview")
        self.command_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.execute_btn = QPushButton("▶  EXECUTE MISSION")
        self.execute_btn.setObjectName("ExecuteButton")

        row2.addWidget(self.command_input, 1)
        row2.addWidget(self.execute_btn)
        outer.addLayout(row2)

    def target_text(self) -> str:
        return self.target_input.text().strip()

    def set_warhead_profiles(self, tool: str) -> None:
        """Repopulate WARHEAD PROFILE with just `tool`'s own warheads —
        each tool has its own attack profiles (stealth/critical/quality),
        not a single shared nmap-flavored list. Signals blocked during the
        swap so this doesn't fire a stray currentTextChanged for an
        in-between/empty combo state while it's being rebuilt."""
        self.warhead_combo.blockSignals(True)
        self.warhead_combo.clear()
        self.warhead_combo.addItems(WARHEAD_BY_TOOL.get(tool, {}).keys())
        self.warhead_combo.blockSignals(False)
