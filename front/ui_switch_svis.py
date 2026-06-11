from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from back.data_models import svi


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


class svis_tab(QWidget):

    validity_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._invalid_cells = set()
        self._revalidation_pending = False
        self._valid_vlan_ids = set()
        self._build()
        self.table.cellChanged.connect(self._on_cell_changed)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("+ Add SVI")
        self.btn_delete = QPushButton("Delete Selected")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "VLAN", "Description", "Primary IP", "Secondary IP", "HSRP Group",
            "HSRP Virtual IP", "VRF", "MTU", "Shutdown", "Note",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)

        header = self.table.horizontalHeader()
        for col in range(10):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 130)
        self.table.setColumnWidth(6, 90)
        self.table.setColumnWidth(7, 70)

        layout.addWidget(self.table)

        self.btn_add.clicked.connect(self._on_add_row)
        self.btn_delete.clicked.connect(self._on_delete_row)

    def set_valid_vlan_ids(self, vlan_ids):
        self._valid_vlan_ids = set(vlan_ids)
        self._schedule_revalidation()

    def is_valid(self):
        return len(self._invalid_cells) == 0

    def load(self, svis_list):
        self.table.setRowCount(0)
        self.table.setRowCount(len(svis_list))

        for row, s in enumerate(svis_list):
            vlan_item = QTableWidgetItem(str(s.vlan_ref_id))
            vlan_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, vlan_item)

            self.table.setItem(row, 1, QTableWidgetItem(s.description))
            self.table.setItem(row, 2, QTableWidgetItem(s.primary_ip_address))
            self.table.setItem(row, 3, QTableWidgetItem(s.secondary_ip_address))
            self.table.setItem(row, 4, QTableWidgetItem(
                str(s.hsrp_group) if s.hsrp_group is not None else ""
            ))
            self.table.setItem(row, 5, QTableWidgetItem(s.hsrp_virtual_ip))
            self.table.setItem(row, 6, QTableWidgetItem(s.vrf))
            self.table.setItem(row, 7, QTableWidgetItem(str(s.mtu)))

            shut_item = QTableWidgetItem()
            shut_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            shut_item.setCheckState(Qt.CheckState.Checked if s.shutdown else Qt.CheckState.Unchecked)
            self.table.setItem(row, 8, shut_item)

            self.table.setItem(row, 9, QTableWidgetItem(s.note))

        self._schedule_revalidation()

    def dump(self):
        dumped = []
        for row in range(self.table.rowCount()):
            vlan_text = self.table.item(row, 0).text().strip()
            if not vlan_text.isdigit():
                continue

            description = self.table.item(row, 1).text().strip()
            primary_ip = self.table.item(row, 2).text().strip()
            secondary_ip = self.table.item(row, 3).text().strip()
            hsrp_group = self._read_int(row, 4)
            hsrp_vip = self.table.item(row, 5).text().strip()
            vrf = self.table.item(row, 6).text().strip()
            mtu = self._read_int(row, 7)
            is_shut = self.table.item(row, 8).checkState() == Qt.CheckState.Checked
            note_item = self.table.item(row, 9)
            note = note_item.text().strip() if note_item else ""

            dumped.append(svi(
                vlan_ref_id=int(vlan_text),
                description=description,
                primary_ip_address=primary_ip,
                secondary_ip_address=secondary_ip,
                hsrp_group=hsrp_group,
                hsrp_virtual_ip=hsrp_vip,
                vrf=vrf,
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
        if col in (0, 1, 4, 7, 9):
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
            for col in (0, 1, 4, 7, 9):
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
            return self._check_vlan_ref(text, row)
        if col == 1:
            return self._check_description(text)
        if col == 4:
            return self._check_hsrp_group(text)
        if col == 7:
            return self._check_mtu(text)
        if col == 9:
            return self._check_note(text)
        return True, ""

    def _check_vlan_ref(self, text, current_row):
        if not text:
            return False, "VLAN is required"
        if not text.isdigit():
            return False, "Must be a number"
        n = int(text)
        if n < 1 or n > 4094:
            return False, "Must be 1-4094"
        for r in range(self.table.rowCount()):
            if r == current_row:
                continue
            other = self.table.item(r, 0)
            if other and other.text().strip() == text:
                return False, f"Duplicate of row {r + 1}"
        if n not in self._valid_vlan_ids:
            return False, "No VLAN with this ID exists on this switch"
        return True, ""

    def _check_description(self, text):
        if len(text) > 64:
            return False, "Max 64 characters"
        return True, ""

    def _check_hsrp_group(self, text):
        if not text:
            return True, ""
        if not text.isdigit():
            return False, "Must be a number"
        n = int(text)
        if n < 0 or n > 255:
            return False, "Must be 0-255"
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
        self.table.setItem(row, 2, QTableWidgetItem(""))
        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem(""))
        self.table.setItem(row, 5, QTableWidgetItem(""))
        self.table.setItem(row, 6, QTableWidgetItem(""))
        self.table.setItem(row, 7, QTableWidgetItem("1500"))

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
