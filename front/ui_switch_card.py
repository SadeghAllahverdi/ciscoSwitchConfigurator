from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from back.data_models import switch_device


class switch_card(QFrame):

    open_requested = pyqtSignal(int)
    selection_changed = pyqtSignal()

    def __init__(self, sw: switch_device, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.sw = sw
        self._selected = False
        self.setObjectName("switch_card")
        self._build()
        self._refresh_selected_style()
        self.setToolTip(self._tooltip_text())

    @property
    def selected(self):
        return self._selected

    def set_selected(self, on: bool):
        if self._selected != on:
            self._selected = on
            self._refresh_selected_style()
            self.selection_changed.emit()

    def toggle_selected(self):
        self.set_selected(not self._selected)

    def _build(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 12, 6)
        row.setSpacing(10)

        row.addLayout(self._column("NAME",     self.sw.name,            160, "card_name"))
        row.addLayout(self._column("HOSTNAME", self.sw.hostname or "-", 160, "card_host"))
        row.addLayout(self._column("IP",       self.sw.ip or "-",       130, "card_ip"))
        row.addLayout(self._column("LOCATION", self.sw.location or "-", 180, "card_loc"))

        row.addStretch(1)

        self.lbl_platform = QLabel(self._short_platform())
        self.lbl_platform.setObjectName("card_platform_tag")
        row.addWidget(self.lbl_platform, alignment=Qt.AlignmentFlag.AlignVCenter)

    def _column(self, header_text: str, value_text: str, width: int, value_object_name: str):
        col = QVBoxLayout()
        col.setSpacing(2)
        col.setContentsMargins(0, 0, 0, 0)

        head = QLabel(header_text)
        head.setObjectName("card_field_header")
        head.setFixedWidth(width)

        val = QLabel(value_text)
        val.setObjectName(value_object_name)
        val.setFixedWidth(width)

        col.addWidget(head)
        col.addWidget(val)
        return col

    def _short_platform(self):
        p = self.sw.platform
        if p.startswith("cisco_"):
            return p[len("cisco_"):]
        return p

    def _tooltip_text(self):
        lines = [
            f"Name:         {self.sw.name}",
            f"Hostname:     {self.sw.hostname or '-'}",
            f"IP:           {self.sw.ip or '-'}",
            f"Platform:     {self.sw.platform}",
            f"Location:     {self.sw.location or '-'}",
            f"Mgmt VRF:     {self.sw.mgmt_vrf or '-'}",
            f"Push status:  {self.sw.last_push_status}",
            f"Last pushed:  {self.sw.last_pushed_at or 'never'}",
            f"Last pulled:  {self.sw.last_pulled_at or 'never'}",
        ]
        if self.sw.note:
            lines.append(f"Note:         {self.sw.note}")
        return "\n".join(lines)

    def _refresh_selected_style(self):
        self.setProperty("selected", "true" if self._selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_selected()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.sw.id is not None:
            event.accept()
            self.open_requested.emit(int(self.sw.id))
            return

        super().mouseDoubleClickEvent(event)