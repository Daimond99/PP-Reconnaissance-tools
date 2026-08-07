"""Shared widget helpers — small utilities used across the widget modules.

No app-internal dependencies, so every other widget module can import from
here without risking an import cycle.
"""

from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvg import QSvgRenderer


def svg_icon(path: str, color: str = "#edf0f5", size: int = 16) -> QIcon:
    """Build a crisp, dependency-free SVG icon for custom controls."""
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path d="{path}" fill="none" stroke="{color}" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round"/>
    </svg>'''
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def _restyle(widget: QWidget) -> None:
    """Force a stylesheet re-evaluation after a dynamic property changes."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def wrap_in_terminal(widget: QWidget) -> QFrame:
    """Wrap a console widget in plain terminal chrome — a blank rounded
    frame, no header bar, no title text."""
    frame = QFrame()
    frame.setObjectName("TermWindow")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(widget, 1)
    return frame
