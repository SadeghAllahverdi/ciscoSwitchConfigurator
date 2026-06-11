from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)


class push_confirm_dialog(QDialog):

    def __init__(self, switch_name, ip, commands, parent=None):
        super().__init__(parent)

        self.switch_name = switch_name
        self.ip = ip
        self.commands = commands
        self.save_to_startup = False

        self.setWindowTitle(f"Push to {switch_name} ({ip})")
        self.resize(700, 600)

        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setSpacing(10)

        lbl = QLabel(
            f"{len(self.commands)} lines will be sent to "
            f"{self.switch_name} ({self.ip}).\n"
            "A backup of the live config is taken before anything is sent."
        )
        outer.addWidget(lbl)

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText("\n".join(self.commands))
        outer.addWidget(preview, stretch=1)

        self.chk_startup = QCheckBox("Also save to startup-config after the push")
        outer.addWidget(self.chk_startup)

        action_row = QHBoxLayout()
        action_row.addStretch(1)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        action_row.addWidget(self.btn_cancel)

        self.btn_push = QPushButton("Push")
        self.btn_push.clicked.connect(self._on_push_clicked)
        action_row.addWidget(self.btn_push)

        outer.addLayout(action_row)

    def _on_push_clicked(self):
        answer = QMessageBox.question(
            self,
            "Really push?",
            f"Send {len(self.commands)} lines to {self.switch_name} ({self.ip})?\n\n"
            "This changes the running config of the real switch.",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.save_to_startup = self.chk_startup.isChecked()
        self.accept()
