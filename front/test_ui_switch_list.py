import os
import sys
import tempfile
from PyQt6.QtWidgets import QApplication
from back.data_base import DataBase
from back.data_models import switch_device
from ui_switch_list import switch_list_screen

def main():
    app = QApplication(sys.argv)

    qss_path = os.path.join(os.path.dirname(__file__), "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_list.sqlite")
        print(f"Created temporary database at: {db_path}")
        
        db = DataBase(db_path)

        if not db.get_all_switches_from_db():
            print("Empty DB, seeding...")
            db.add_switch_to_db(switch=switch_device(
                name="dc1-core-01", hostname="DC1-CORE-01",
                platform="cisco_nxos", ip="192.168.1.10", location="DC1 rack A3",
            ))
            db.add_switch_to_db(switch=switch_device(
                name="dc1-core-02", hostname="DC1-CORE-02",
                platform="cisco_nxos", ip="192.168.1.11", location="DC1 rack A3",
            ))
            db.add_switch_to_db(switch=switch_device(
                name="edge-02", platform="cisco_ios",
                ip="192.168.1.20", location="branch office",
            ))
            db.add_switch_to_db(switch=switch_device(
                name="test-broken", hostname="LAB-TEST",
                platform="cisco_nxos", ip="10.0.0.5", location="lab",
                note="acting up",
            ))
            db.add_switch_to_db(switch=switch_device(
                name="dc2-dist-01", hostname="DC2-DIST-01",
                platform="cisco_ios", ip="172.16.5.1", location="storage room",
                note="Check fans next week"
            ))
            
            db.add_switch_to_db(switch=switch_device(
                name="access-01", hostname="ACC-01",
                platform="cisco_ios", ip="10.50.1.5", location="Floor 2 East",
                note="scheduled maintenance"
            ))
            
            db.add_switch_to_db(switch=switch_device(
                name="lab-nexus-01", hostname="LAB-NEX-01",
                platform="cisco_nxos", ip="10.0.0.100", location="lab rack 1",
                note="vlan testing in progress"
            ))

        screen = switch_list_screen(db)
        screen.open_switch.connect(lambda sid: print(f"OPEN switch {sid}"))
        screen.resize(1000, 600)
        screen.show()

        exit_code = app.exec()
        
        print("GUI closed. Executing cleanup...")
        screen.deleteLater()
        screen = None 
        db.close()
        del db 
        print("Cleanup done. Letting Windows delete the temp folder now...")

    sys.exit(exit_code)

if __name__ == "__main__":
    main()