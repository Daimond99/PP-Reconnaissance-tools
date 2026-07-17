import sys
from PySide6.QtWidgets import QApplication
from src.config import STYLESHEET
from src.ui.main_window import ReconMainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = ReconMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
