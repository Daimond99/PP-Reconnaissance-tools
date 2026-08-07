"""Sidebar — the left-hand nav list (Wizard Console / Input Management / Raw
Output / Results Display / LLM Mode)."""

from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout
from PySide6.QtCore import Signal, Qt

from src.ui.widgets.helpers import _restyle


class Sidebar(QFrame):
    navigate = Signal(int)
    """แถบนำทางด้านซ้าย — พับ/ขยายได้, ข้อความล้วนไม่มี emoji"""

    NAV_ITEMS = [
        "Wizard Console",
        "Input Management",
        "Raw Output",
        "Results Display",
        "LLM Mode",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(2)

        # The collapse toggle and Settings live in the title bar now (top-left),
        # so the sidebar itself is just the nav list.
        self.nav_buttons: list[QPushButton] = []
        for index, title in enumerate(self.NAV_ITEMS):
            btn = self._nav_button(title)
            btn.setProperty("selected", index == 0)
            btn.clicked.connect(lambda _=False, i=index: self._select_nav(i))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

    def _nav_button(self, title: str, settings: bool = False) -> QPushButton:
        btn = QPushButton(title)
        btn.setObjectName("SidebarSettingsItem" if settings else "SidebarNavItem")
        btn.setFixedHeight(36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setProperty("full_label", title)
        return btn

    def _select_nav(self, index: int) -> None:
        for item_index, button in enumerate(self.nav_buttons):
            button.setProperty("selected", item_index == index)
            _restyle(button)
        self.navigate.emit(index)

    def select_index(self, index: int) -> None:
        """Programmatic navigation (e.g. auto-jump to Raw Output on
        Execute) — same effect as the user clicking that nav item."""
        self._select_nav(index)
