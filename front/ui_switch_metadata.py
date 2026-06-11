from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QWidget,
)

from back.data_models import switch_device


class metadata_tab(QWidget):

    def __init__(self, parent=None, sw=None):
        super().__init__(parent)
        self.platforms = ["cisco_nxos", "cisco_ios", "cisco_iosxe"]
        self._build()
        if sw is not None:
            self.load(sw)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        id_row = QHBoxLayout()
        self.fld_name = QLineEdit()
        self.fld_name.setPlaceholderText("dc1-core-01")
        id_row.addLayout(self._field_stack("NAME *", self.fld_name))

        self.fld_hostname = QLineEdit()
        self.fld_hostname.setPlaceholderText("Optional")
        id_row.addLayout(self._field_stack("HOSTNAME", self.fld_hostname))
        layout.addLayout(id_row)

        self.tech_row = QHBoxLayout()
        self.fld_platform = QComboBox()
        self.fld_platform.addItems(self.platforms)
        self.tech_row.addLayout(self._field_stack("PLATFORM", self.fld_platform))
        layout.addLayout(self.tech_row)

        net_row = QHBoxLayout()
        self.fld_ip = QLineEdit()
        self.fld_ip.setPlaceholderText("10.0.0.1")
        net_row.addLayout(self._field_stack("IP ADDRESS", self.fld_ip))

        self.fld_mgmt_vrf = QLineEdit()
        self.fld_mgmt_vrf.setPlaceholderText("management")
        net_row.addLayout(self._field_stack("MGMT VRF", self.fld_mgmt_vrf))
        layout.addLayout(net_row)

        self.fld_location = QLineEdit()
        layout.addLayout(self._field_stack("LOCATION", self.fld_location))

        self.fld_notes = QTextEdit()
        self.fld_notes.setFixedHeight(60)
        layout.addLayout(self._field_stack("NOTES", self.fld_notes))

        layout.addStretch()

    def _field_stack(self, label_text, widget):
        vbox = QVBoxLayout()
        vbox.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 10px; font-weight: bold; color: #888;")
        vbox.addWidget(lbl)
        vbox.addWidget(widget)
        return vbox

    def load(self, sw):
        self.fld_name.setText(sw.name)
        self.fld_hostname.setText(sw.hostname)
        self.fld_platform.setCurrentText(sw.platform)
        self.fld_ip.setText(sw.ip)
        self.fld_mgmt_vrf.setText(sw.mgmt_vrf)
        self.fld_location.setText(sw.location)
        self.fld_notes.setPlainText(sw.note)

    def dump(self):
        return switch_device(
            name=self.fld_name.text().strip(),
            hostname=self.fld_hostname.text().strip(),
            platform=self.fld_platform.currentText(),
            ip=self.fld_ip.text().strip(),
            mgmt_vrf=self.fld_mgmt_vrf.text().strip(),
            location=self.fld_location.text().strip(),
            note=self.fld_notes.toPlainText().strip()[:255],
        )