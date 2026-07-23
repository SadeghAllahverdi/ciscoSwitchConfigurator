from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from back.data_models import interface


INVALID_COLOR = QColor("#ff4444")
_WARNING_ICON = None


def _warning_icon():
    global _WARNING_ICON
    if _WARNING_ICON is None:
        pix = QPixmap(12, 12)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(INVALID_COLOR))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 12, 12)
        p.end()
        _WARNING_ICON = QIcon(pix)
    return _WARNING_ICON


class interfaces_tab(QWidget):

    validity_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._invalid_cells = set()
        self._revalidation_pending = False
        self._build()
        self.table.cellChanged.connect(self._on_cell_changed)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Add Interface")
        self.btn_delete = QPushButton("Delete Selected")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 15)
        self.table.setHorizontalHeaderLabels([
            "Name", "Description", "Mode", "Access VLAN", "Voice VLAN",
            "Allowed VLANs", "Native VLAN", "Port-Channel", "LACP Mode",
            "STP Port Type", "Speed", "Duplex", "MTU", "Shutdown", "Note",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)

        header = self.table.horizontalHeader()
        for col in range(15):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(14, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 90)
        self.table.setColumnWidth(7, 100)
        self.table.setColumnWidth(8, 90)
        self.table.setColumnWidth(9, 110)
        self.table.setColumnWidth(10, 80)
        self.table.setColumnWidth(11, 70)
        self.table.setColumnWidth(12, 70)

        layout.addWidget(self.table)

        self.btn_add.clicked.connect(self._on_add_row)
        self.btn_delete.clicked.connect(self._on_delete_row)

    def is_valid(self):
        return len(self._invalid_cells) == 0

    def load(self, interfaces_list):
        self.table.setRowCount(0)
        self.table.setRowCount(len(interfaces_list))

        for row, i in enumerate(interfaces_list):
            self.table.setItem(row, 0, QTableWidgetItem(i.name))
            self.table.setItem(row, 1, QTableWidgetItem(i.description))

            mode_combo = QComboBox()
            mode_combo.addItems(["access", "trunk", "routed", "unused"])
            mode_combo.setCurrentText(i.mode)
            self.table.setCellWidget(row, 2, mode_combo)

            self.table.setItem(row, 3, QTableWidgetItem(
                str(i.access_vlan_id) if i.access_vlan_id is not None else ""
            ))
            self.table.setItem(row, 4, QTableWidgetItem(
                str(i.voice_vlan_id) if i.voice_vlan_id is not None else ""
            ))
            self.table.setItem(row, 5, QTableWidgetItem(i.allowed_vlan_ids))
            self.table.setItem(row, 6, QTableWidgetItem(
                str(i.native_vlan_id) if i.native_vlan_id is not None else ""
            ))
            self.table.setItem(row, 7, QTableWidgetItem(
                str(i.port_channel) if i.port_channel is not None else ""
            ))

            lacp_combo = QComboBox()
            lacp_combo.addItems(["", "active", "passive", "on"])
            lacp_combo.setCurrentText(i.lacp_mode or "")
            self.table.setCellWidget(row, 8, lacp_combo)

            stp_combo = QComboBox()
            stp_combo.addItems(["", "edge", "network", "normal"])
            stp_combo.setCurrentText(i.stp_port_type or "")
            self.table.setCellWidget(row, 9, stp_combo)

            speed_combo = QComboBox()
            speed_combo.addItems(["auto", "10", "100", "1000", "2500", "5000", "10000", "25000", "40000", "100000"])
            speed_combo.setCurrentText(i.speed)
            self.table.setCellWidget(row, 10, speed_combo)

            duplex_combo = QComboBox()
            duplex_combo.addItems(["", "auto", "half", "full"])
            duplex_combo.setCurrentText(i.duplex or "")
            self.table.setCellWidget(row, 11, duplex_combo)

            self.table.setItem(row, 12, QTableWidgetItem(str(i.mtu)))

            shut_item = QTableWidgetItem()
            shut_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            shut_item.setCheckState(Qt.CheckState.Checked if i.shutdown else Qt.CheckState.Unchecked)
            self.table.setItem(row, 13, shut_item)

            self.table.setItem(row, 14, QTableWidgetItem(i.note))

        self._schedule_revalidation()

    def dump(self):
        dumped = []
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().strip()
            if not name:
                continue

            description = self.table.item(row, 1).text().strip()
            mode = self.table.cellWidget(row, 2).currentText()
            access_vlan = self._read_int(row, 3)
            voice_vlan = self._read_int(row, 4)
            allowed_vlans = self.table.item(row, 5).text().strip()
            native_vlan = self._read_int(row, 6)
            po = self._read_int(row, 7)
            lacp_mode = self.table.cellWidget(row, 8).currentText()
            stp_port_type = self.table.cellWidget(row, 9).currentText()
            speed = self.table.cellWidget(row, 10).currentText()
            duplex = self.table.cellWidget(row, 11).currentText()
            mtu = self._read_int(row, 12)
            is_shut = self.table.item(row, 13).checkState() == Qt.CheckState.Checked
            note_item = self.table.item(row, 14)
            note = note_item.text().strip() if note_item else ""

            dumped.append(interface(
                name=name,
                description=description,
                mode=mode,
                access_vlan_id=access_vlan,
                voice_vlan_id=voice_vlan,
                allowed_vlan_ids=allowed_vlans,
                native_vlan_id=native_vlan,
                port_channel=po,
                lacp_mode=lacp_mode,
                stp_port_type=stp_port_type,
                speed=speed,
                duplex=duplex,
                mtu=mtu if mtu is not None else 1500,
                shutdown=is_shut,
                note=note,
            ))
        return dumped

    def _read_int(self, row, col):
        item = self.table.item(row, col)
        if item is None:
            return None
        text = item.text().strip()
        if text == "":
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def _on_cell_changed(self, row, col):
        if col in (0, 1, 3, 4, 6, 7, 12, 14):
            self._schedule_revalidation()

    def _schedule_revalidation(self):
        if self._revalidation_pending:
            return
        self._revalidation_pending = True
        QTimer.singleShot(0, self._do_revalidate)

    def _do_revalidate(self):
        self._revalidation_pending = False
        self.table.blockSignals(True)

        new_invalid = set()
        for row in range(self.table.rowCount()):
            for col in (0, 1, 3, 4, 6, 7, 12, 14):
                item = self.table.item(row, col)
                if item is None:
                    continue
                valid, msg = self._check_cell(row, col, item.text().strip())
                if valid:
                    self._clear_marks(item)
                else:
                    self._apply_marks(item, msg)
                    new_invalid.add((row, col))

        self.table.blockSignals(False)

        changed = new_invalid != self._invalid_cells
        self._invalid_cells = new_invalid
        if changed:
            self.validity_changed.emit()

    def _check_cell(self, row, col, text):
        if col == 0:
            return self._check_name(text, row)
        if col == 1:
            return self._check_description(text)
        if col == 3:
            return self._check_vlan_ref(text)
        if col == 4:
            return self._check_vlan_ref(text)
        if col == 6:
            return self._check_vlan_ref(text)
        if col == 7:
            return self._check_port_channel(text)
        if col == 12:
            return self._check_mtu(text)
        if col == 14:
            return self._check_note(text)
        return True, ""

    def _check_name(self, text, current_row):
        if not text:
            return False, "Name is required"
        if len(text) > 32:
            return False, "Max 32 characters"
        for r in range(self.table.rowCount()):
            if r == current_row:
                continue
            other = self.table.item(r, 0)
            if other and other.text().strip() == text:
                return False, f"Duplicate of row {r + 1}"
        return True, ""

    def _check_description(self, text):
        if len(text) > 64:
            return False, "Max 64 characters"
        return True, ""

    def _check_vlan_ref(self, text):
        if not text:
            return True, ""
        if not text.isdigit():
            return False, "Must be a number"
        n = int(text)
        if n < 1 or n > 4094:
            return False, "Must be 1-4094"
        return True, ""

    def _check_port_channel(self, text):
        if not text:
            return True, ""
        if not text.isdigit():
            return False, "Must be a number"
        n = int(text)
        if n < 1 or n > 4096:
            return False, "Must be 1-4096"
        return True, ""

    def _check_mtu(self, text):
        if not text:
            return True, ""
        if not text.isdigit():
            return False, "Must be a number"
        n = int(text)
        if n < 576 or n > 9216:
            return False, "Must be 576-9216"
        return True, ""

    def _check_note(self, text):
        if len(text) > 255:
            return False, "Max 255 characters"
        return True, ""

    def _apply_marks(self, item, message):
        item.setIcon(_warning_icon())
        item.setForeground(QBrush(INVALID_COLOR))
        item.setToolTip(message)

    def _clear_marks(self, item):
        item.setIcon(QIcon())
        item.setForeground(QBrush())
        item.setToolTip("")

    def _on_add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))

        mode_combo = QComboBox()
        mode_combo.addItems(["access", "trunk", "routed", "unused"])
        mode_combo.setCurrentText("unused")
        self.table.setCellWidget(row, 2, mode_combo)

        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem(""))
        self.table.setItem(row, 5, QTableWidgetItem(""))
        self.table.setItem(row, 6, QTableWidgetItem(""))
        self.table.setItem(row, 7, QTableWidgetItem(""))

        lacp_combo = QComboBox()
        lacp_combo.addItems(["", "active", "passive", "on"])
        self.table.setCellWidget(row, 8, lacp_combo)

        stp_combo = QComboBox()
        stp_combo.addItems(["", "edge", "network", "normal"])
        self.table.setCellWidget(row, 9, stp_combo)

        speed_combo = QComboBox()
        speed_combo.addItems(["auto", "10", "100", "1000", "2500", "5000", "10000", "25000", "40000", "100000"])
        self.table.setCellWidget(row, 10, speed_combo)

        duplex_combo = QComboBox()
        duplex_combo.addItems(["", "auto", "half", "full"])
        self.table.setCellWidget(row, 11, duplex_combo)

        self.table.setItem(row, 12, QTableWidgetItem("1500"))

        shut_item = QTableWidgetItem()
        shut_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        shut_item.setCheckState(Qt.CheckState.Unchecked)
        self.table.setItem(row, 13, shut_item)

        self.table.setItem(row, 14, QTableWidgetItem(""))

        self._schedule_revalidation()

    def _on_delete_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self._schedule_revalidation()
