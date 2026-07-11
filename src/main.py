import sys
from PyQt5.QtWidgets import QApplication
from src.config import STYLESHEET
from src.ui.main_window import ReconMainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = ReconMainWindow()
    window.show()
    exit_code = app.exec() if hasattr(app, "exec") else app.exec_()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
