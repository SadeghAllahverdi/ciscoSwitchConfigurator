from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QMessageBox, QSpinBox, QVBoxLayout,
)

from back.data_base import DataBase
from back.data_models import switch_device, conf, interface
from ui_switch_metadata import metadata_tab


class add_switch_dialog(QDialog):

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.created_switch_id = None
        self.setWindowTitle("Register New Switch")
        self.resize(500, 540)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.form = metadata_tab()
        outer.addWidget(self.form)

        self.fld_port_count = QSpinBox()
        self.fld_port_count.setRange(0, 256)
        self.fld_port_count.setValue(48)
        self.fld_port_count.setMinimumHeight(30)
        self.fld_port_count.setMinimumWidth(80)
        self.form.tech_row.addLayout(
            self.form._field_stack("GENERATE PORTS", self.fld_port_count)
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        button_wrap = QVBoxLayout()
        button_wrap.setContentsMargins(25, 0, 25, 25)
        button_wrap.addWidget(buttons)
        outer.addLayout(button_wrap)

    def _on_save(self):
        name = self.form.fld_name.text().strip()
        if not name or " " in name:
            QMessageBox.warning(self, "Invalid Name", "Name is required and cannot contain spaces.")
            return

        sw = switch_device(
            name=name,
            hostname=self.form.fld_hostname.text().strip(),
            platform=self.form.fld_platform.currentText(),
            location=self.form.fld_location.text().strip(),
            ip=self.form.fld_ip.text().strip(),
            mgmt_vrf=self.form.fld_mgmt_vrf.text().strip(),
            note=self.form.fld_notes.toPlainText().strip()[:255]
        )

        switch_conf = conf(switch=sw)

        port_count = self.fld_port_count.value()
        if port_count > 0:
            prefix = "Ethernet1/" if sw.platform == "cisco_nxos" else "GigabitEthernet0/"
            for i in range(1, port_count + 1):
                switch_conf.interfaces.append(interface(
                    name=f"{prefix}{i}",
                    mode="unused",
                    shutdown=True
                ))

        try:
            new_id = self.db.save_switch_conf_in_db(switch_conf)
            self.created_switch_id = new_id
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Database error: {e}")