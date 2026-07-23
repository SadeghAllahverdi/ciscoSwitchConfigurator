import os
import sys

# make "back.*" importable when started directly with "python front/main.py"
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# in a windowed (no-console) PyInstaller build stdout/stderr are None, but
# ciscoconfparse2 wires loguru to sys.stdout at import time and crashes on it
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from PyQt6.QtWidgets import QApplication

from back.data_base import DataBase
from ui_switch_list import switch_list_screen


def main():
    app = QApplication(sys.argv)

    qss_path = os.path.join(os.path.dirname(__file__), "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "switches.sqlite",
    )
    db = DataBase(db_path)

    screen = switch_list_screen(db)
    screen.resize(1000, 600)
    screen.show()

    exit_code = app.exec()

    screen.deleteLater()
    db.close()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
