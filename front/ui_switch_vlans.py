from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from back.data_models import vlan


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


class vlans_tab(QWidget):

    validity_changed = pyqtSignal()
    data_changed = pyqtSignal()

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
        self.btn_add = QPushButton("+ Add VLAN")
        self.btn_delete = QPushButton("Delete Selected")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["VLAN ID", "Name", "State", "Shutdown", "Note"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        self.btn_add.clicked.connect(self._on_add_row)
        self.btn_delete.clicked.connect(self._on_delete_row)

    def is_valid(self):
        return len(self._invalid_cells) == 0

    def load(self, vlans_list):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.setRowCount(len(vlans_list))

        for row, v in enumerate(vlans_list):
            id_item = QTableWidgetItem(str(v.vlan_id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, id_item)

            self.table.setItem(row, 1, QTableWidgetItem(v.name))

            state_combo = QComboBox()
            state_combo.addItems(["active", "suspend"])
            state_combo.setCurrentText(v.state)
            state_combo.currentTextChanged.connect(self.data_changed.emit)
            self.table.setCellWidget(row, 2, state_combo)

            shut_item = QTableWidgetItem()
            shut_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            shut_item.setCheckState(Qt.CheckState.Checked if v.shutdown else Qt.CheckState.Unchecked)
            self.table.setItem(row, 3, shut_item)

            self.table.setItem(row, 4, QTableWidgetItem(v.note))

        self.table.blockSignals(False)
        self._schedule_revalidation()
        self.data_changed.emit()

    def dump(self):
        dumped = []

        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, 0)
            if id_item is None:
                continue

            id_text = id_item.text().strip()
            if not id_text.isdigit():
                continue

            name_item = self.table.item(row, 1)
            note_item = self.table.item(row, 4)
            shut_item = self.table.item(row, 3)
            state_combo = self.table.cellWidget(row, 2)

            dumped.append(vlan(
                vlan_id=int(id_text),
                name=name_item.text().strip() if name_item else "",
                state=state_combo.currentText() if state_combo else "active",
                shutdown=shut_item.checkState() == Qt.CheckState.Checked if shut_item else False,
                note=note_item.text().strip() if note_item else "",
            ))

        return dumped

    def _on_cell_changed(self, row, col):
        if col in (0, 1, 4):
            self._schedule_revalidation()

        if col in (0, 1, 3, 4):
            self.data_changed.emit()

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
            for col in (0, 1, 4):
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
            return self._check_vlan_id(text, row)
        if col == 1:
            return self._check_name(text)
        if col == 4:
            return self._check_note(text)
        return True, ""

    def _check_vlan_id(self, text, current_row):
        if not text:
            return False, "VLAN ID is required"

        if not text.isdigit():
            return False, "Must be a number"

        vid = int(text)
        if vid < 1 or vid > 4094:
            return False, "Must be 1-4094"

        for row in range(self.table.rowCount()):
            if row == current_row:
                continue

            other = self.table.item(row, 0)
            if other and other.text().strip() == text:
                return False, f"Duplicate of row {row + 1}"

        return True, ""

    def _check_name(self, text):
        if len(text) > 32:
            return False, "Max 32 characters"
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

        state_combo = QComboBox()
        state_combo.addItems(["active", "suspend"])
        state_combo.currentTextChanged.connect(self.data_changed.emit)
        self.table.setCellWidget(row, 2, state_combo)

        shut_item = QTableWidgetItem()
        shut_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        shut_item.setCheckState(Qt.CheckState.Unchecked)
        self.table.setItem(row, 3, shut_item)

        self.table.setItem(row, 4, QTableWidgetItem(""))

        self._schedule_revalidation()
        self.data_changed.emit()

    def _on_delete_row(self):
        current_row = self.table.currentRow()

        if current_row >= 0:
            self.table.removeRow(current_row)
            self._schedule_revalidation()
            self.data_changed.emit()
