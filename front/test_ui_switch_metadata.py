import os
import sys
from PyQt6.QtWidgets import QApplication

from back.data_models import switch_device
from ui_switch_metadata import metadata_tab


app = QApplication(sys.argv)

qss_path = os.path.join(os.path.dirname(__file__), "style.qss")
with open(qss_path, "r", encoding="utf-8") as f:
    app.setStyleSheet(f.read())

sw = switch_device(
    name="dc1-core-01",
    hostname="DC1-CORE-01",
    platform="cisco_nxos",
    ip="192.168.1.10",
    mgmt_vrf="management",
    location="DC1 rack A3",
    note="primary core switch",
)

tab = metadata_tab(sw=sw)
tab.resize(700, 600)
tab.show()

sys.exit(app.exec())