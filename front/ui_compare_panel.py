from datetime import datetime

from PyQt6.QtCore import Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
    QWidget,
)

from back.back_up import write_backup_to_file
from back.cisco_to_db import parse_conf
from back.connect_to_switch import pull_config_from_switch, push_config_to_switch
from back.db_to_cisco import generate_conf
from back.validate_conf import validate_switch_conf
from ui_credential_dialog import credential_dialog
from ui_push_confirm_dialog import push_confirm_dialog
from ui_worker import Worker


DIFF_COLOR = QColor("#ffb74d")
LEFT_ONLY_COLOR = QColor("#707070")


SECTIONS = [
    ("VLANs", "vlans", ("vlan_id",), [
        ("VLAN ID", "vlan_id"),
        ("Name", "name"),
        ("State", "state"),
        ("Shutdown", "shutdown"),
    ]),
    ("SVIs", "svis", ("vlan_ref_id",), [
        ("VLAN", "vlan_ref_id"),
        ("Description", "description"),
        ("Primary IP", "primary_ip_address"),
        ("Secondary IP", "secondary_ip_address"),
        ("HSRP Group", "hsrp_group"),
        ("HSRP VIP", "hsrp_virtual_ip"),
        ("VRF", "vrf"),
        ("MTU", "mtu"),
        ("Shutdown", "shutdown"),
    ]),
    ("Interfaces", "interfaces", ("name",), [
        ("Name", "name"),
        ("Description", "description"),
        ("Mode", "mode"),
        ("Access VLAN", "access_vlan_id"),
        ("Voice VLAN", "voice_vlan_id"),
        ("Allowed VLANs", "allowed_vlan_ids"),
        ("Native VLAN", "native_vlan_id"),
        ("Port-Channel", "port_channel"),
        ("LACP", "lacp_mode"),
        ("STP", "stp_port_type"),
        ("Speed", "speed"),
        ("Duplex", "duplex"),
        ("MTU", "mtu"),
        ("Shutdown", "shutdown"),
    ]),
    ("Port-Channels", "port_channels", ("po_number",), [
        ("PO #", "po_number"),
        ("Description", "description"),
        ("Mode", "mode"),
        ("Allowed VLANs", "allowed_vlan_ids"),
        ("Native VLAN", "native_vlan_id"),
        ("STP", "stp_port_type"),
        ("vPC ID", "vpc_id"),
        ("vPC Peer-Link", "vpc_peer_link"),
        ("Shutdown", "shutdown"),
    ]),
    ("Static Routes", "static_routes", ("destination_network", "next_hop", "vrf"), [
        ("Destination", "destination_network"),
        ("Next Hop", "next_hop"),
        ("VRF", "vrf"),
        ("Admin Distance", "admin_distance"),
        ("Track", "track"),
    ]),
]


class saved_switch_picker_dialog(QDialog):

    def __init__(self, switches, parent=None):
        super().__init__(parent)

        self._switches = switches
        self.selected_switch_id = None

        self._build()
        self._refresh_list()

    def _build(self):
        self.setWindowTitle("Choose saved switch")
        self.resize(520, 520)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        title = QLabel("Choose another saved switch")
        title.setObjectName("switch_picker_title")
        outer.addWidget(title)

        self.fld_search = QLineEdit()
        self.fld_search.setPlaceholderText(
            "Search by name, hostname, IP, location, platform..."
        )
        self.fld_search.textChanged.connect(self._refresh_list)
        outer.addWidget(self.fld_search)

        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("switch_picker_count")
        outer.addWidget(self.lbl_count)

        self.list_switches = QListWidget()
        self.list_switches.setObjectName("switch_picker_list")
        self.list_switches.itemDoubleClicked.connect(lambda item: self._accept_current())
        self.list_switches.itemSelectionChanged.connect(self._update_choose_button)
        outer.addWidget(self.list_switches, stretch=1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        action_row.addWidget(self.btn_cancel)

        self.btn_choose = QPushButton("Choose")
        self.btn_choose.setEnabled(False)
        self.btn_choose.clicked.connect(self._accept_current)
        action_row.addWidget(self.btn_choose)

        outer.addLayout(action_row)

    def _matches(self, sw, query):
        if not query:
            return True

        search_text = " ".join([
            sw.name or "",
            sw.hostname or "",
            sw.ip or "",
            sw.location or "",
            sw.platform or "",
            sw.note or "",
            sw.mgmt_vrf or "",
        ]).lower()

        return query in search_text

    def _refresh_list(self):
        query = self.fld_search.text().strip().lower()

        self.list_switches.clear()

        shown = 0
        for sw in self._switches:
            if not self._matches(sw, query):
                continue

            label = f"{sw.name}  ·  {sw.ip or 'no IP'}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, sw.id)

            self.list_switches.addItem(item)
            shown += 1

        total = len(self._switches)

        if shown == total:
            self.lbl_count.setText(f"{total} saved switch{'es' if total != 1 else ''}")
        else:
            self.lbl_count.setText(f"{shown} of {total} shown")

        if self.list_switches.count():
            self.list_switches.setCurrentRow(0)

        self._update_choose_button()

    def _update_choose_button(self):
        self.btn_choose.setEnabled(self.list_switches.currentItem() is not None)

    def _accept_current(self):
        item = self.list_switches.currentItem()

        if item is None:
            return

        self.selected_switch_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


def _fmt(value):
    if value is None:
        return ""

    if isinstance(value, bool):
        return "yes" if value else "no"

    return str(value)


def _key_of(item, key_attrs):
    return tuple(_fmt(getattr(item, attr)) for attr in key_attrs)


def _sort_key(key):
    return tuple((len(part), part) for part in key)


def _diff_rows(ref_items, left_items, key_attrs, columns):
    ref_map = {_key_of(item, key_attrs): item for item in ref_items}
    left_map = {_key_of(item, key_attrs): item for item in left_items}

    rows = []

    for key in sorted(set(ref_map) | set(left_map), key=_sort_key):
        ref = ref_map.get(key)
        left = left_map.get(key)

        if ref is not None and left is not None:
            values = []
            diff_cols = set()
            tips = {}

            for col, (header, attr) in enumerate(columns):
                ref_value = _fmt(getattr(ref, attr))
                left_value = _fmt(getattr(left, attr))

                values.append(ref_value)

                if ref_value != left_value:
                    diff_cols.add(col)
                    tips[col] = f"yours: {left_value or '(empty)'}"

            rows.append((tuple(values), "both", frozenset(diff_cols), tips))

        elif ref is not None:
            values = tuple(_fmt(getattr(ref, attr)) for header, attr in columns)
            rows.append((values, "ref_only", frozenset(), {}))

        else:
            values = tuple(_fmt(getattr(left, attr)) for header, attr in columns)
            rows.append((values, "left_only", frozenset(), {}))

    return rows


class diff_table(QTableWidget):

    def __init__(self, columns, parent=None):
        super().__init__(0, len(columns), parent)

        self.setHorizontalHeaderLabels([header for header, attr in columns])
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(32)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        header = self.horizontalHeader()

        for col in range(len(columns)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

        header.setStretchLastSection(True)

    def render(self, rows):
        self.setRowCount(0)
        self.setRowCount(len(rows))

        for row, (values, kind, diff_cols, tips) in enumerate(rows):
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)

                if kind == "ref_only":
                    item.setForeground(QBrush(DIFF_COLOR))
                    item.setToolTip("not in your editor")

                elif kind == "left_only":
                    item.setForeground(QBrush(LEFT_ONLY_COLOR))

                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)

                    item.setToolTip("only in your editor")

                elif col in diff_cols:
                    item.setForeground(QBrush(DIFF_COLOR))
                    item.setToolTip(tips.get(col, ""))

                self.setItem(row, col, item)


class compare_panel(QWidget):

    state_changed = pyqtSignal()

    def __init__(self, detail, parent=None):
        super().__init__(parent)

        self.detail = detail
        self.mode = None
        self.pulling = False
        self.pushing = False
        self._push_ci = None
        self._push_commands = None
        self._push_save_to_startup = False
        self._push_switch_name = ""
        self._ref = None
        self._cache = {}

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh_diff)

        self._build()

    def has_reference(self):
        return self._ref is not None

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()

        self._build_empty_page()
        self._build_reference_page()

        outer.addWidget(self.stack)

        self._update_buttons()

    def _build_empty_page(self):
        page_empty = QWidget()
        empty_layout = QVBoxLayout(page_empty)

        empty_layout.addStretch(1)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setObjectName("compare_plus")
        self.btn_plus.setFixedSize(110, 110)
        self.btn_plus.clicked.connect(self._on_plus_clicked)
        empty_layout.addWidget(self.btn_plus, alignment=Qt.AlignmentFlag.AlignHCenter)

        hint = QLabel("Add comparison")
        hint.setObjectName("compare_hint")
        empty_layout.addWidget(hint, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.choice_box = QFrame()
        self.choice_box.setObjectName("compare_choice_box")
        self.choice_box.setFixedWidth(280)
        self.choice_box.setVisible(False)

        choice_layout = QVBoxLayout(self.choice_box)
        choice_layout.setContentsMargins(10, 10, 10, 10)
        choice_layout.setSpacing(6)

        self.btn_live_choice = QPushButton("See live config")
        self.btn_live_choice.setObjectName("compare_choice_button")
        self.btn_live_choice.clicked.connect(self._see_live_config)
        choice_layout.addWidget(self.btn_live_choice)

        self.btn_saved_choice = QPushButton("See saved switch")
        self.btn_saved_choice.setObjectName("compare_choice_button")
        self.btn_saved_choice.clicked.connect(self._open_saved_picker)
        choice_layout.addWidget(self.btn_saved_choice)

        empty_layout.addSpacing(10)
        empty_layout.addWidget(self.choice_box, alignment=Qt.AlignmentFlag.AlignHCenter)

        empty_layout.addStretch(1)

        self.stack.addWidget(page_empty)

    def _build_reference_page(self):
        page_ref = QWidget()
        ref_layout = QVBoxLayout(page_ref)
        ref_layout.setContentsMargins(0, 0, 0, 0)
        ref_layout.setSpacing(8)

        header_row = QHBoxLayout()

        self.lbl_status = QLabel("")
        header_row.addWidget(self.lbl_status)

        header_row.addStretch(1)

        self.btn_close_ref = QPushButton("✕")
        self.btn_close_ref.setObjectName("compare_close")
        self.btn_close_ref.clicked.connect(self._on_close_clicked)
        header_row.addWidget(self.btn_close_ref)

        ref_layout.addLayout(header_row)

        action_row = QHBoxLayout()
        action_row.addStretch(1)

        self.btn_refresh_live = QPushButton("Refresh live")
        self.btn_refresh_live.clicked.connect(self._fetch_live_config)
        action_row.addWidget(self.btn_refresh_live)

        self.btn_pull = QPushButton("Pull")
        self.btn_pull.setToolTip("Copy the displayed right-side config into the left editor tables.")
        self.btn_pull.clicked.connect(self._pull_reference_to_editor)
        action_row.addWidget(self.btn_pull)

        self.btn_push = QPushButton("Push")
        self.btn_push.setToolTip(
            "Send the saved database config of this switch to the live switch."
        )
        self.btn_push.clicked.connect(self._start_push)
        action_row.addWidget(self.btn_push)

        ref_layout.addLayout(action_row)

        self.tabs = QTabWidget()
        self.tables = {}

        for label, attr, key_attrs, columns in SECTIONS:
            table = diff_table(columns)
            self.tables[attr] = table
            self.tabs.addTab(table, label)

        ref_layout.addWidget(self.tabs, stretch=1)

        self.stack.addWidget(page_ref)

    def _update_buttons(self):
        is_live = self.mode == "live"
        busy = self.pulling or self.pushing

        self.btn_refresh_live.setVisible(is_live)
        self.btn_refresh_live.setEnabled(is_live and not busy)
        self.btn_refresh_live.setText("Refreshing..." if self.pulling else "Refresh live")

        self.btn_pull.setEnabled(self.has_reference() and not busy)

        self.btn_push.setEnabled(is_live and self.has_reference() and not busy)
        self.btn_push.setText("Pushing..." if self.pushing else "Push")

        self.btn_close_ref.setEnabled(not busy)

    def _on_plus_clicked(self):
        self.btn_saved_choice.setToolTip(self._saved_switch_tooltip())
        self.choice_box.setVisible(not self.choice_box.isVisible())

    def _see_live_config(self):
        self.choice_box.setVisible(False)

        self.mode = "live"
        self._ref = None
        self._cache = {}

        self._timer.stop()
        self._clear_tables()

        self.lbl_status.setText("Connecting to live switch...")
        self.stack.setCurrentIndex(1)

        self._update_buttons()
        self.state_changed.emit()

        self._fetch_live_config()

    def _fetch_live_config(self):
        if self.mode != "live" or self.pulling or self.pushing:
            return

        ip = self.detail.tab_meta.fld_ip.text().strip()
        platform = self.detail.tab_meta.fld_platform.currentText()

        if not ip:
            QMessageBox.warning(
                self,
                "No IP",
                "This switch has no IP address set.",
            )
            return

        dialog = credential_dialog(ip=ip, platform=platform, parent=self)

        if not dialog.exec() or dialog.ci is None:
            self.lbl_status.setText("Live config check cancelled.")
            self._update_buttons()
            self.state_changed.emit()
            return

        self.pulling = True
        self.lbl_status.setText("Reading live config...")

        self._update_buttons()
        self.state_changed.emit()

        worker = Worker(pull_config_from_switch, dialog.ci)
        worker.signals.finished.connect(self._on_live_config_done)
        worker.signals.failed.connect(self._on_live_config_failed)

        QThreadPool.globalInstance().start(worker)

    def _on_live_config_done(self, result):
        self.pulling = False

        if not result.success:
            QMessageBox.critical(
                self,
                "Live Config Failed",
                result.error_message or "Could not read live config.",
            )
            self.lbl_status.setText("Could not read live config.")
            self._update_buttons()
            self.state_changed.emit()
            return

        sw = self.detail.tab_meta.dump()
        sw.id = self.detail.switch_id

        try:
            cfg = parse_conf(raw_switch_config=result.output, switch=sw)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Parse Failed",
                f"Live config was read, but could not be parsed:\n{e}",
            )
            self.lbl_status.setText("Live config was read, but parsing failed.")
            self._update_buttons()
            self.state_changed.emit()
            return

        self.detail.db.flag_last_pulled_at(self.detail.switch_id)

        stamp = datetime.now().strftime("%H:%M:%S")
        self._set_reference(cfg, f"{sw.name} live config - {stamp}")

        self.lbl_status.setText(
            f"Live config shown at {stamp}. Click Pull to copy it into the left tables."
        )

        self._update_buttons()
        self.state_changed.emit()

    def _on_live_config_failed(self, tb):
        self.pulling = False

        self.lbl_status.setText("Could not read live config.")

        self._update_buttons()
        self.state_changed.emit()

        QMessageBox.critical(
            self,
            "Live Config Failed",
            f"Something went wrong:\n\n{tb}",
        )

    def _start_push(self):
        if self.mode != "live" or not self.has_reference() or self.pulling or self.pushing:
            return

        answer = QMessageBox.question(
            self,
            "Push",
            "Push sends the config currently stored in the database, "
            "not unsaved edits.\n\nSave current changes first?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )

        if answer == QMessageBox.StandardButton.Cancel:
            return

        if answer == QMessageBox.StandardButton.Save:
            if not self.detail._save_to_db():
                return

        cfg = self.detail.db.load_switch_conf_from_db(switch_id=self.detail.switch_id)

        errors = validate_switch_conf(cfg)

        if errors:
            shown = "\n".join(errors[:20])

            if len(errors) > 20:
                shown += f"\n\n... and {len(errors) - 20} more error(s)."

            QMessageBox.warning(self, "Invalid Configuration", shown)
            return

        if not cfg.switch.ip:
            QMessageBox.warning(self, "No IP", "This switch has no IP address saved.")
            return

        commands = generate_conf(cfg)

        confirm = push_confirm_dialog(
            switch_name=cfg.switch.name,
            ip=cfg.switch.ip,
            commands=commands,
            parent=self,
        )

        if not confirm.exec():
            return

        dialog = credential_dialog(ip=cfg.switch.ip, platform=cfg.switch.platform, parent=self)

        if not dialog.exec() or dialog.ci is None:
            return

        self._push_ci = dialog.ci
        self._push_commands = commands
        self._push_save_to_startup = confirm.save_to_startup
        self._push_switch_name = cfg.switch.name

        self.detail.db.flag_last_push_in_progress(switch_id=self.detail.switch_id)

        self.pushing = True
        self.lbl_status.setText("Backing up the live config before push...")
        self._update_buttons()
        self.state_changed.emit()

        worker = Worker(pull_config_from_switch, self._push_ci)
        worker.signals.finished.connect(self._on_push_prebackup_done)
        worker.signals.failed.connect(self._on_push_worker_failed)
        QThreadPool.globalInstance().start(worker)

    def _on_push_prebackup_done(self, result):
        if not result.success:
            self._finish_push_failed(
                "Pre-push backup pull failed:\n" + (result.error_message or "")
            )
            return

        try:
            write_backup_to_file(
                self.detail.db,
                self.detail.switch_id,
                self._push_switch_name,
                result.output,
                "pre-push",
            )

        except Exception as e:
            self._finish_push_failed(f"Could not write pre-push backup:\n{e}")
            return

        self.lbl_status.setText(f"Pushing {len(self._push_commands)} lines...")

        worker = Worker(
            push_config_to_switch,
            self._push_ci,
            self._push_commands,
            save_to_startup=self._push_save_to_startup,
        )
        worker.signals.finished.connect(self._on_push_done)
        worker.signals.failed.connect(self._on_push_worker_failed)
        QThreadPool.globalInstance().start(worker)

    def _on_push_done(self, result):
        if not result.success:
            tail = ("\n\nLast output:\n" + result.output[-500:]) if result.output else ""
            self._finish_push_failed(
                "Push failed:\n" + (result.error_message or "") + tail
            )
            return

        self.detail.db.flag_last_push(switch_id=self.detail.switch_id, success=True)

        self.lbl_status.setText("Push done. Reading the live config back...")

        worker = Worker(pull_config_from_switch, self._push_ci)
        worker.signals.finished.connect(self._on_push_postbackup_done)
        worker.signals.failed.connect(self._on_push_worker_failed_after_push)
        QThreadPool.globalInstance().start(worker)

    def _on_push_postbackup_done(self, result):
        self.pushing = False
        self._update_buttons()
        self.state_changed.emit()

        if not result.success:
            QMessageBox.warning(
                self,
                "Push Succeeded",
                "The push worked, but reading the config back for the "
                "post-push backup failed:\n" + (result.error_message or ""),
            )
            self.lbl_status.setText("Push done. Post-push backup failed.")
            return

        try:
            write_backup_to_file(
                self.detail.db,
                self.detail.switch_id,
                self._push_switch_name,
                result.output,
                "post-push",
            )

        except Exception as e:
            QMessageBox.warning(
                self,
                "Push Succeeded",
                f"The push worked, but writing the post-push backup failed:\n{e}",
            )

        self.detail.db.flag_last_pulled_at(self.detail.switch_id)

        sw = self.detail.tab_meta.dump()
        sw.id = self.detail.switch_id

        try:
            cfg = parse_conf(raw_switch_config=result.output, switch=sw)
            stamp = datetime.now().strftime("%H:%M:%S")
            self._set_reference(cfg, f"{sw.name} live config after push - {stamp}")

        except Exception:
            pass

        QMessageBox.information(
            self,
            "Push Successful",
            "The config was pushed.\n\nPre-push and post-push backups were saved.",
        )
        self.lbl_status.setText(
            "Push done. Right side now shows the live config after the push."
        )

    def _finish_push_failed(self, message):
        self.pushing = False

        try:
            self.detail.db.flag_last_push(switch_id=self.detail.switch_id, success=False)
        except Exception:
            pass

        self._update_buttons()
        self.state_changed.emit()

        self.lbl_status.setText("Push failed.")
        QMessageBox.critical(self, "Push Failed", message)

    def _on_push_worker_failed(self, tb):
        self._finish_push_failed(f"Something went wrong:\n\n{tb}")

    def _on_push_worker_failed_after_push(self, tb):
        self.pushing = False
        self._update_buttons()
        self.state_changed.emit()

        self.lbl_status.setText("Push done. Post-push backup failed.")
        QMessageBox.warning(
            self,
            "Push Succeeded",
            f"The push worked, but the post-push backup step crashed:\n\n{tb}",
        )

    def _open_saved_picker(self):
        others = self._other_switches()

        if not others:
            QMessageBox.information(
                self,
                "No switches",
                "There are no other saved switches.",
            )
            return

        dialog = saved_switch_picker_dialog(others, self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if dialog.selected_switch_id is None:
            return

        self._show_saved_switch(dialog.selected_switch_id)

    def _show_saved_switch(self, other_id):
        self.choice_box.setVisible(False)

        cfg = self.detail.db.load_switch_conf_from_db(switch_id=other_id)

        self.mode = "saved"
        self.stack.setCurrentIndex(1)

        self._set_reference(cfg, f"{cfg.switch.name} saved config")

        self.lbl_status.setText(
            f"Saved config shown from {cfg.switch.name}. Click Pull to copy it into the left tables."
        )

        self._update_buttons()
        self.state_changed.emit()

    def _other_switches(self):
        return [
            sw for sw in self.detail.db.get_all_switches_from_db()
            if sw.id != self.detail.switch_id
        ]

    def _saved_switch_tooltip(self):
        others = self._other_switches()

        if not others:
            return "No other saved switches."

        shown = others[:8]
        lines = ["Saved switches:"]

        for sw in shown:
            lines.append(f"- {sw.name} ({sw.ip or 'no IP'})")

        if len(others) > len(shown):
            lines.append(f"... and {len(others) - len(shown)} more")

        return "\n".join(lines)

    def _on_close_clicked(self):
        self.mode = None
        self._ref = None
        self._cache = {}

        self._timer.stop()
        self._clear_tables()

        self.choice_box.setVisible(False)
        self.stack.setCurrentIndex(0)

        self._update_buttons()
        self.state_changed.emit()

    def _set_reference(self, cfg, label):
        self._ref = cfg
        self._cache = {}

        self.lbl_status.setText(f"Reference: {label}")

        self._refresh_diff()
        self._timer.start()

        self._update_buttons()
        self.state_changed.emit()

    def _left_items(self, attr):
        tabs = {
            "vlans": self.detail.tab_vlans,
            "svis": self.detail.tab_svis,
            "interfaces": self.detail.tab_interfaces,
            "port_channels": self.detail.tab_port_channels,
            "static_routes": self.detail.tab_routes,
        }

        return tabs[attr].dump()

    def _refresh_diff(self):
        if self._ref is None:
            return

        for index, (label, attr, key_attrs, columns) in enumerate(SECTIONS):
            rows = _diff_rows(
                getattr(self._ref, attr),
                self._left_items(attr),
                key_attrs,
                columns,
            )

            if self._cache.get(attr) != rows:
                self._cache[attr] = rows
                self.tables[attr].render(rows)

            count = sum(1 for row in rows if row[1] != "both" or row[2])

            if count:
                self.tabs.setTabText(index, f"{label} ({count})")
            else:
                self.tabs.setTabText(index, label)

    def _clear_tables(self):
        for index, (label, attr, key_attrs, columns) in enumerate(SECTIONS):
            self.tables[attr].setRowCount(0)
            self.tabs.setTabText(index, label)

    def _load_cfg_into_editor(self, cfg):
        self.detail.tab_vlans.load(cfg.vlans)
        self.detail.tab_svis.load(cfg.svis)
        self.detail.tab_interfaces.load(cfg.interfaces)
        self.detail.tab_port_channels.load(cfg.port_channels)
        self.detail.tab_routes.load(cfg.static_routes)

        self.detail._sync_vlan_ids_to_svis()
        self.detail._update_validity_ui()

    def _pull_reference_to_editor(self):
        if self._ref is None:
            return

        answer = QMessageBox.question(
            self,
            "Pull",
            "Pull the displayed right-side config into the left tables?\n\n"
            "This replaces VLANs, SVIs, interfaces, port-channels, and static routes "
            "on the left side.\n\n"
            "Nothing is saved to the database until you press Save.",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self._load_cfg_into_editor(self._ref)
        self._refresh_diff()

        self.lbl_status.setText(
            "Pulled into the left tables. Press Save to store it in the database."
        )

        self._update_buttons()
        self.state_changed.emit()

    def copy_into_editor(self):
        self._pull_reference_to_editor()

    def start_pull(self):
        self._fetch_live_config()