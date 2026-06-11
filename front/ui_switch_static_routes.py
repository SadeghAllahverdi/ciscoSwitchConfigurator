from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from back.data_models import static_route


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

class routes_tab(QWidget):

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
        self.btn_add = QPushButton("+ Add Route")
        self.btn_delete = QPushButton("Delete Selected")
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Destination Network", "Next Hop", "VRF", "Admin Distance", "Track", "Note",
        ])
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(40)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(0, 190)  # Destination
        self.table.setColumnWidth(1, 150)  # Next Hop
        self.table.setColumnWidth(2, 90)   # VRF
        self.table.setColumnWidth(3, 130)  # Admin Distance
        self.table.setColumnWidth(4, 70)   # Track 

        layout.addWidget(self.table)

        self.btn_add.clicked.connect(self._on_add_row)
        self.btn_delete.clicked.connect(self._on_delete_row)

    def load(self, routes_list):
        self.table.setRowCount(0)
        self.table.setRowCount(len(routes_list))

        for row, r in enumerate(routes_list):
            self.table.setItem(row, 0, QTableWidgetItem(r.destination_network))
            self.table.setItem(row, 1, QTableWidgetItem(r.next_hop))
            self.table.setItem(row, 2, QTableWidgetItem(r.vrf))
            self.table.setItem(row, 3, QTableWidgetItem(str(r.admin_distance) if r.admin_distance is not None else ""))
            self.table.setItem(row, 4, QTableWidgetItem(str(r.track) if r.track is not None else ""))
            self.table.setItem(row, 5, QTableWidgetItem(r.note))

        self._schedule_revalidation()

    def dump(self):
        dumped = []
        for row in range(self.table.rowCount()):
            dest = self.table.item(row, 0).text().strip()
            next_hop = self.table.item(row, 1).text().strip()
            if not dest or not next_hop:
                continue

            vrf = self.table.item(row, 2).text().strip()
            ad = self._read_int(row, 3)
            track = self._read_int(row, 4)
            note = self.table.item(row, 5).text().strip()

            dumped.append(static_route(
                destination_network=dest,
                next_hop=next_hop,
                vrf=vrf,
                admin_distance=ad,
                track=track,
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
        self.table.setItem(row, 2, QTableWidgetItem(""))
        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem(""))
        self.table.setItem(row, 5, QTableWidgetItem(""))

    def _on_delete_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self._schedule_revalidation()

    def is_valid(self):
        return len(self._invalid_cells) == 0

    def _on_cell_changed(self, row, col):
        if col in (0, 1, 2, 3, 4, 5):
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
            for col in (0, 1, 2, 3, 4, 5):
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
            return self._check_destination(text, row)
        if col == 1:
            return self._check_next_hop(text)
        if col == 3:
            return self._check_admin_distance(text)
        if col == 4:
            return self._check_track(text)
        if col == 5:
            return self._check_note(text)
        return True, ""

    def _check_destination(self, text, current_row):
        if not text:
            return False, "Destination is required"

        next_hop_item = self.table.item(current_row, 1)
        vrf_item = self.table.item(current_row, 2)

        next_hop = next_hop_item.text().strip() if next_hop_item else ""
        vrf = vrf_item.text().strip() if vrf_item else ""

        for r in range(self.table.rowCount()):
            if r == current_row:
                continue

            other_dest = self.table.item(r, 0)
            other_hop = self.table.item(r, 1)
            other_vrf = self.table.item(r, 2)

            other_dest_text = other_dest.text().strip() if other_dest else ""
            other_hop_text = other_hop.text().strip() if other_hop else ""
            other_vrf_text = other_vrf.text().strip() if other_vrf else ""

            if (
                other_dest_text == text
                and other_hop_text == next_hop
                and other_vrf_text == vrf
            ):
                return False, f"Duplicate destination+next-hop+VRF of row {r + 1}"

        return True, ""

    def _check_next_hop(self, text):
        if not text:
            return False, "Next hop is required"
        return True, ""

    def _check_admin_distance(self, text):
        if not text:
            return True, ""
        if not text.isdigit():
            return False, "Must be a number"
        n = int(text)
        if n < 1 or n > 254:
            return False, "Must be 1-254"
        return True, ""

    def _check_track(self, text):
        if not text:
            return True, ""
        if not text.isdigit():
            return False, "Must be a number"
        n = int(text)
        if n < 1 or n > 500:
            return False, "Must be 1-500"
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