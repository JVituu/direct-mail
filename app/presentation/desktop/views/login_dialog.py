from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.shared.security.authenticator import authenticate
from app.shared.security.login_credentials import LOGIN_USERNAME


class LoginDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Login - Mala Direta")
        self.setModal(True)
        self.setFixedWidth(420)
        self._attempts = 0
        self._max_attempts = 3

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        title = QLabel("Mala Direta")
        title.setObjectName("LoginTitle")
        subtitle = QLabel("Informe o usuario e a senha para acessar o sistema.")
        subtitle.setObjectName("LoginSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)

        self.username_input = QLineEdit(self)
        self.username_input.setText(LOGIN_USERNAME)
        self.username_input.selectAll()

        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._try_login)

        form.addRow("Usuario:", self.username_input)
        form.addRow("Senha:", self.password_input)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setObjectName("LoginError")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Entrar")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")
        buttons.accepted.connect(self._try_login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setStyleSheet(
            """
            QDialog {
                background: #f6f8fb;
            }
            QLabel#LoginTitle {
                color: #0f2f5f;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#LoginSubtitle {
                color: #516482;
                font-size: 12px;
            }
            QLabel#LoginError {
                color: #b42318;
                min-height: 18px;
            }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #cfd9e8;
                border-radius: 6px;
                padding: 8px 10px;
            }
            QLineEdit:focus {
                border-color: #1f5eff;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cfd9e8;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background: #eef3f9;
            }
            """
        )

    def _try_login(self) -> None:
        if authenticate(self.username_input.text(), self.password_input.text()):
            self.accept()
            return

        self._attempts += 1
        remaining_attempts = self._max_attempts - self._attempts
        if remaining_attempts <= 0:
            QMessageBox.critical(
                self,
                "Acesso bloqueado",
                "Numero maximo de tentativas atingido.",
            )
            self.reject()
            return

        self.error_label.setText(f"Usuario ou senha invalidos. Tentativas restantes: {remaining_attempts}.")
        self.password_input.clear()
        self.password_input.setFocus()
