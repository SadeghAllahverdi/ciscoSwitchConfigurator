import difflib
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget, QMessageBox, QDialog
)
from back.data_base import DataBase
from back.data_models import switch_device
from ui_switch_card import switch_card
from ui_add_switch_dialog import add_switch_dialog
from ui_switch_detail import switch_detail_screen

class switch_list_screen(QWidget):
    open_switch = pyqtSignal(int)

    def __init__(self, db: DataBase, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self._cards: list[switch_card] = []
        self._last_clicked_index: Optional[int] = None
        self._build()
        self.refresh()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(12)

        # Header bar
        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("Switches")
        title.setObjectName("page_title")
        header.addWidget(title)

        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("page_subtitle")
        header.addWidget(self.lbl_count)
        header.addStretch(1)
        outer.addLayout(header)
        # Action Row (Search + Buttons)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.fld_search = QLineEdit()
        self.fld_search.setPlaceholderText("Search by name, hostname, IP, location, platform, note...")
        self.fld_search.textChanged.connect(self._on_search_changed)
        action_row.addWidget(self.fld_search, stretch=1)

        self.btn_add = QPushButton("+ Add")
        self.btn_add.clicked.connect(self._on_add_clicked)
        action_row.addWidget(self.btn_add)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        action_row.addWidget(self.btn_delete)

        outer.addLayout(action_row)
        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(6)
        self.card_layout.addStretch(1)
        self.scroll.setWidget(self.card_container)
        outer.addWidget(self.scroll, stretch=1)

    def _add_card(self, sw: switch_device):
        card = switch_card(sw)
        card.open_requested.connect(self._on_switch_opened)
        card.mousePressEvent = self._wrap_mouse_press(card, card.mousePressEvent)
        insert_at = self.card_layout.count() - 1
        self.card_layout.insertWidget(insert_at, card)
        self._cards.append(card)

    def _delete_cards(self):
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        self._last_clicked_index = None

    def _does_search_match(self, card: switch_card, query: str):
        if not query:
            return True
        sw = card.sw
        search_text = " ".join([
            sw.name or "", sw.hostname or "", sw.ip or "", 
            sw.location or "", sw.platform or "", sw.note or "", sw.mgmt_vrf or ""
        ]).lower()

        if query in search_text:
            return True
        
        if any(char.isdigit() for char in query):
            return False

        search_words = search_text.split()
        close_matches = difflib.get_close_matches(query, search_words, n=1, cutoff=0.6)
        return len(close_matches) > 0

    def _update_count_label(self, shown: int, total: int):
        if shown == total:
            self.lbl_count.setText(f"{total} switch{'es' if total != 1 else ''}")
        else:
            self.lbl_count.setText(f"{shown} of {total} shown")

    def _wrap_mouse_press(self, card: switch_card, original_handler):
        def wrapped(event):
            if event.button() == Qt.MouseButton.LeftButton:
                modifiers = event.modifiers()
                ctrl_held = modifiers & Qt.KeyboardModifier.ControlModifier
                shift_held = modifiers & Qt.KeyboardModifier.ShiftModifier
                try:
                    clicked_idx = self._cards.index(card)
                except ValueError:
                    return
                if shift_held and self._last_clicked_index is not None:
                    start_idx = min(self._last_clicked_index, clicked_idx)
                    end_idx = max(self._last_clicked_index, clicked_idx)
                    if not ctrl_held:
                        for c in self._cards:
                            c.set_selected(False)
                    for i in range(start_idx, end_idx + 1):
                        self._cards[i].set_selected(True)
                elif ctrl_held:
                    card.toggle_selected()
                    self._last_clicked_index = clicked_idx
                else:
                    for other in self._cards:
                        if other is not card and other.selected:
                            other.set_selected(False)
                    card.set_selected(True)
                    self._last_clicked_index = clicked_idx
                self._on_selection_changed()
                return
            original_handler(event)
        return wrapped

    def selected_switches(self):
        return [c.sw for c in self._cards if c.selected]

    def _on_delete_clicked(self):
        to_delete = self.selected_switches()
        if not to_delete:
            return
        
        res = QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to delete {len(to_delete)} switch(es)?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if res == QMessageBox.StandardButton.Yes:
            for sw in to_delete:
                try:
                    self.db.delete_switch_from_db(sw.id)
                except Exception as e:
                    print(f"Failed to delete {sw.name}: {e}")
            self.refresh()
            self._on_selection_changed()

    def _on_add_clicked(self):
        dialog = add_switch_dialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_selection_changed(self):
        count = len(self.selected_switches())
        self.btn_delete.setText(f"Delete ({count})" if count else "Delete")
        self.btn_delete.setEnabled(count > 0)

    def _on_search_changed(self, text: str):
        query = text.strip().lower()
        visible_count = 0
        for card in self._cards:
            if self._does_search_match(card, query):
                card.setVisible(True)
                visible_count += 1
            else:
                card.setVisible(False)
        self._update_count_label(visible_count, len(self._cards))

    def _on_switch_opened(self, sid: int):
        sw = self.db.get_switch_from_db(switch_id=sid)
        if not sw:
            print(f"Error: Switch {sid} not found in DB.")
            return

        dialog = switch_detail_screen(switch_id=sid, db=self.db, parent=self)
        dialog.exec()

        QTimer.singleShot(0, self.refresh)

    def refresh(self):
        self._delete_cards()
        try:
            switches = self.db.get_all_switches_from_db()
        except Exception as e:
            print(f"DB error: {e}")
            switches = []
        for sw in switches:
            self._add_card(sw)
        self._update_count_label(len(switches), len(switches))