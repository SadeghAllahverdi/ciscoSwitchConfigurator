import os
import sys

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
