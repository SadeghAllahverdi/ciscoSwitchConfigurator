from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QMessageBox, QPushButton, QSplitter,
    QTabWidget, QVBoxLayout,
)

from back.back_up import write_backup_to_file
from back.data_models import conf
from back.db_to_cisco import generate_conf
from back.validate_conf import validate_switch_conf

from ui_compare_panel import compare_panel
from ui_switch_interfaces import interfaces_tab
from ui_switch_metadata import metadata_tab
from ui_switch_port_channels import port_channels_tab
from ui_switch_static_routes import routes_tab
from ui_switch_svis import svis_tab
from ui_switch_vlans import vlans_tab


class switch_detail_screen(QDialog):

    def __init__(self, switch_id, db, parent=None):
        super().__init__(parent)

        self.switch_id = switch_id
        self.db = db

        self._build()
        self._load_everything()
        self._connect_signals()

        self._sync_vlan_ids_to_svis()
        self._update_validity_ui()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        self.tabs = QTabWidget()

        self.tab_meta = metadata_tab()
        self.tab_vlans = vlans_tab()
        self.tab_svis = svis_tab()
        self.tab_interfaces = interfaces_tab()
        self.tab_port_channels = port_channels_tab()
        self.tab_routes = routes_tab()

        self.tabs.addTab(self.tab_meta, "Metadata")
        self.tabs.addTab(self.tab_vlans, "VLANs")
        self.tabs.addTab(self.tab_svis, "SVIs")
        self.tabs.addTab(self.tab_interfaces, "Interfaces")
        self.tabs.addTab(self.tab_port_channels, "Port-Channels")
        self.tabs.addTab(self.tab_routes, "Static Routes")

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.tabs)

        self.panel = compare_panel(self)
        self.splitter.addWidget(self.panel)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        outer.addWidget(self.splitter, stretch=1)

        action_row = QHBoxLayout()

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._on_save_clicked)
        action_row.addWidget(self.btn_save)

        self.btn_backup = QPushButton("Backup")
        self.btn_backup.clicked.connect(self._on_backup_clicked)
        action_row.addWidget(self.btn_backup)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        action_row.addWidget(self.btn_cancel)

        action_row.addStretch(1)

        outer.addLayout(action_row)

    def _connect_signals(self):
        self.tab_vlans.validity_changed.connect(self._update_validity_ui)
        self.tab_svis.validity_changed.connect(self._update_validity_ui)
        self.tab_interfaces.validity_changed.connect(self._update_validity_ui)
        self.tab_port_channels.validity_changed.connect(self._update_validity_ui)
        self.tab_routes.validity_changed.connect(self._update_validity_ui)

        if hasattr(self.tab_vlans, "data_changed"):
            self.tab_vlans.data_changed.connect(self._sync_vlan_ids_to_svis)
        else:
            self.tab_vlans.validity_changed.connect(self._sync_vlan_ids_to_svis)

    def _load_everything(self):
        cfg = self.db.load_switch_conf_from_db(switch_id=self.switch_id)

        self.tab_meta.load(cfg.switch)
        self.tab_vlans.load(cfg.vlans)
        self.tab_svis.load(cfg.svis)
        self.tab_interfaces.load(cfg.interfaces)
        self.tab_port_channels.load(cfg.port_channels)
        self.tab_routes.load(cfg.static_routes)

        self.setWindowTitle(f"Switch Details: {cfg.switch.name}")
        self.resize(1500, 500)

    def _sync_vlan_ids_to_svis(self):
        vlan_ids = {v.vlan_id for v in self.tab_vlans.dump()}
        self.tab_svis.set_valid_vlan_ids(vlan_ids)

    def _on_save_clicked(self):
        if self._save_to_db():
            QMessageBox.information(
                self,
                "Saved",
                "Switch changes have been saved.",
            )

    def _collect_conf(self):
        sw = self.tab_meta.dump()
        sw.id = self.switch_id

        vlans = self.tab_vlans.dump()
        for v in vlans:
            v.switch_id = self.switch_id

        svis = self.tab_svis.dump()
        for s in svis:
            s.switch_id = self.switch_id

        interfaces = self.tab_interfaces.dump()
        for i in interfaces:
            i.switch_id = self.switch_id

        port_channels = self.tab_port_channels.dump()
        for pc in port_channels:
            pc.switch_id = self.switch_id

        static_routes = self.tab_routes.dump()
        for r in static_routes:
            r.switch_id = self.switch_id

        return conf(
            switch=sw,
            vlans=vlans,
            svis=svis,
            interfaces=interfaces,
            port_channels=port_channels,
            static_routes=static_routes,
        )

    def _save_to_db(self):
        try:
            new_conf = self._collect_conf()
            errors = validate_switch_conf(new_conf)

            if errors:
                shown = "\n".join(errors[:20])

                if len(errors) > 20:
                    shown += f"\n\n... and {len(errors) - 20} more error(s)."

                QMessageBox.warning(
                    self,
                    "Invalid Configuration",
                    shown,
                )
                return False

            self.db.save_switch_conf_in_db(new_conf)
            return True

        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not save changes:\n{e}",
            )
            return False

    def _on_backup_clicked(self):
        answer = QMessageBox.question(
            self,
            "Backup",
            "Backup saves the config currently stored in the database, "
            "not unsaved edits.\n\nSave current changes first?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )

        if answer == QMessageBox.StandardButton.Cancel:
            return

        if answer == QMessageBox.StandardButton.Save:
            if not self._save_to_db():
                return

        cfg = self.db.load_switch_conf_from_db(switch_id=self.switch_id)
        text = "\n".join(generate_conf(cfg))

        try:
            path = write_backup_to_file(
                self.db,
                self.switch_id,
                cfg.switch.name,
                text,
                "manual",
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Backup Failed",
                f"Could not write backup:\n{e}",
            )
            return

        QMessageBox.information(
            self,
            "Backup Saved",
            f"Saved to:\n{path}",
        )

    def _update_validity_ui(self):
        tabs_status = [
            (self.tab_vlans, 1, "VLANs"),
            (self.tab_svis, 2, "SVIs"),
            (self.tab_interfaces, 3, "Interfaces"),
            (self.tab_port_channels, 4, "Port-Channels"),
            (self.tab_routes, 5, "Static Routes"),
        ]

        all_ok = True

        for tab, index, label in tabs_status:
            if tab.is_valid():
                self.tabs.setTabText(index, label)
            else:
                self.tabs.setTabText(index, f"⚠ {label}")
                all_ok = False

        self.btn_save.setEnabled(all_ok)