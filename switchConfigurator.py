import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from data_base import DataBase
from ui_main import MainWindow

def main():
    # 1. Initialize the App
    app = QApplication(sys.argv)
    
    # 2. Database Connection
    db_path = os.path.join(os.path.dirname(__file__), "switches.db")
    try:
        db = DataBase(db_path)
    except Exception as e:
        QMessageBox.critical(None, "DB Error", f"Could not load database: {e}")
        return

    # 3. Apply Stylesheet (The vibe)
    style_path = os.path.join(os.path.dirname(__file__), "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r") as f:
            app.setStyleSheet(f.read())

    # 4. Launch Window
    window = MainWindow(db)
    window.show()
    
    # 5. The loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()