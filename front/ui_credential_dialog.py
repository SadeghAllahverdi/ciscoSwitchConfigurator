from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QVBoxLayout, QLineEdit, QCheckBox,
    QDialogButtonBox, QMessageBox,
)

from back.data_models import connection_info


class credential_dialog(QDialog):

    def __init__(self, ip, platform, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.platform = platform
        self.ci = None
        self.setWindowTitle(f"Connect to {ip}")
        self.resize(420, 220)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        form = QFormLayout()
        outer.addLayout(form)

        ip_field = QLineEdit(self.ip)
        ip_field.setReadOnly(True)
        form.addRow("IP", ip_field)

        self.fld_user = QLineEdit()
        form.addRow("Username", self.fld_user)

        self.fld_pass = QLineEdit()
        self.fld_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password", self.fld_pass)

        self.fld_secret = QLineEdit()
        self.fld_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.fld_secret.setPlaceholderText("Leave blank if not used")
        form.addRow("Enable secret", self.fld_secret)

        self.chk_show = QCheckBox("Show password")
        self.chk_show.toggled.connect(self._toggle_show)
        outer.addWidget(self.chk_show)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _toggle_show(self, on):
        mode = QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
        self.fld_pass.setEchoMode(mode)
        self.fld_secret.setEchoMode(mode)

    def _on_ok(self):
        user = self.fld_user.text().strip()
        pw = self.fld_pass.text()

        if not user or not pw:
            QMessageBox.warning(self, "Missing", "Username and password are required.")
            return

        self.ci = connection_info(
            ip=self.ip,
            username=user,
            password=pw,
            platform=self.platform,
            secret=self.fld_secret.text(),
        )

        self.accept()