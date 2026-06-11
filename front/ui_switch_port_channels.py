from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from back.data_models import port_channel


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


class port_channels_tab(QWidget):

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
        self.btn_add = QPushButton("+ Add Port-Channel")
        self.btn_delete = QPushButton("Delete Selected")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "PO #", "Description", "Mode", "Allowed VLANs", "Native VLAN",
            "STP Port Type", "vPC ID", "vPC Peer-Link", "Shutdown", "Note",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.btn_add.clicked.connect(self._on_add_row)
        self.btn_delete.clicked.connect(self._on_delete_row)

    def load(self, port_channels_list):
        self.table.setRowCount(0)
        self.table.setRowCount(len(port_channels_list))

        for row, pc in enumerate(port_channels_list):
            po_item = QTableWidgetItem(str(pc.po_number))
            po_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, po_item)

            self.table.setItem(row, 1, QTableWidgetItem(pc.description))

            mode_combo = QComboBox()
            mode_combo.addItems(["access", "trunk", "routed"])
            mode_combo.setCurrentText(pc.mode)
            self.table.setCellWidget(row, 2, mode_combo)

            self.table.setItem(row, 3, QTableWidgetItem(pc.allowed_vlan_ids))

            self.table.setItem(row, 4, QTableWidgetItem(
                str(pc.native_vlan_id) if pc.native_vlan_id is not None else ""
            ))

            stp_combo = QComboBox()
            stp_combo.addItems(["", "edge", "network", "normal"])
            stp_combo.setCurrentText(pc.stp_port_type or "")
            self.table.setCellWidget(row, 5, stp_combo)

            self.table.setItem(row, 6, QTableWidgetItem(
                str(pc.vpc_id) if pc.vpc_id is not None else ""
            ))

            peer_item = QTableWidgetItem()
            peer_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            peer_item.setCheckState(Qt.CheckState.Checked if pc.vpc_peer_link else Qt.CheckState.Unchecked)
            self.table.setItem(row, 7, peer_item)

            shut_item = QTableWidgetItem()
            shut_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            shut_item.setCheckState(Qt.CheckState.Checked if pc.shutdown else Qt.CheckState.Unchecked)
            self.table.setItem(row, 8, shut_item)

            self.table.setItem(row, 9, QTableWidgetItem(pc.note))

        self._schedule_revalidation()

    def dump(self):
        dumped = []
        for row in range(self.table.rowCount()):
            po_text = self.table.item(row, 0).text().strip()
            if not po_text.isdigit():
                continue

            description = self.table.item(row, 1).text().strip()
            mode = self.table.cellWidget(row, 2).currentText()
            allowed_vlans = self.table.item(row, 3).text().strip()
            native_vlan = self._read_int(row, 4)
            stp_port_type = self.table.cellWidget(row, 5).currentText()
            vpc_id = self._read_int(row, 6)
            vpc_peer = self.table.item(row, 7).checkState() == Qt.CheckState.Checked
            is_shut = self.table.item(row, 8).checkState() == Qt.CheckState.Checked
            note_item = self.table.item(row, 9)
            note = note_item.text().strip() if note_item else ""

            dumped.append(port_channel(
                po_number=int(po_text),
                description=description,
                mode=mode,
                allowed_vlan_ids=allowed_vlans,
                native_vlan_id=native_vlan,
                stp_port_type=stp_port_type,
                vpc_id=vpc_id,
                vpc_peer_link=vpc_peer,
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

    def _on_add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))

        mode_combo = QComboBox()
        mode_combo.addItems(["access", "trunk", "routed"])
        mode_combo.setCurrentText("trunk")
        self.table.setCellWidget(row, 2, mode_combo)

        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem(""))

        stp_combo = QComboBox()
        stp_combo.addItems(["", "edge", "network", "normal"])
        self.table.setCellWidget(row, 5, stp_combo)

        self.table.setItem(row, 6, QTableWidgetItem(""))

        peer_item = QTableWidgetItem()
        peer_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        peer_item.setCheckState(Qt.CheckState.Unchecked)
        self.table.setItem(row, 7, peer_item)

        shut_item = QTableWidgetItem()
        shut_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        shut_item.setCheckState(Qt.CheckState.Unchecked)
        self.table.setItem(row, 8, shut_item)

        self.table.setItem(row, 9, QTableWidgetItem(""))
        self._schedule_revalidation()

    def _on_delete_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self._schedule_revalidation()

    def is_valid(self):
        return len(self._invalid_cells) == 0

    def _on_cell_changed(self, row, col):
        if col in (0, 1, 4, 6, 9):
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
            for col in (0, 1, 4, 6, 9):
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
            return self._check_po_number(text, row)
        if col == 1:
            return self._check_description(text)
        if col == 4:
            return self._check_native_vlan(text)
        if col == 6:
            return self._check_vpc_id(text)
        if col == 9:
            return self._check_note(text)
        return True, ""

    def _check_po_number(self, text, current_row):
        if not text:
            return False, "PO number is required"
        if not text.isdigit():
            return False, "Must be a number"
        n = int(text)
        if n < 1 or n > 4096:
            return False, "Must be 1-4096"
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

    def _check_native_vlan(self, text):
        if not text:
            return True, ""
        if not text.isdigit():
            return False, "Must be a number"
        n = int(text)
        if n < 1 or n > 4094:
            return False, "Must be 1-4094"
        return True, ""

    def _check_vpc_id(self, text):
        if not text:
            return True, ""
        if not text.isdigit():
            return False, "Must be a number"
        n = int(text)
        if n < 1 or n > 4096:
            return False, "Must be 1-4096"
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