"""Investo — desktop guide for PSX index investing."""
import sys
import signal

signal.signal(signal.SIGINT, signal.SIG_DFL)

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("IndexPK")
    app.setOrganizationName("IndexPK")

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())