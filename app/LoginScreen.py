from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox,
    QHBoxLayout, QSpacerItem, QSizePolicy
)
import importlib.resources

from api.api import API
from api.credentials import CredentialManager
import time

class LoginScreen(QWidget):
    """Login screen"""

    def __init__(self, on_login_success, api: API, credential_manager: CredentialManager):
        super().__init__()
        self.api = api
        self.creds = credential_manager
        self.on_login_success = on_login_success

        ## with open('styles/login.qss', 'r') as f:
        ##     style = f.read()
        ##     self.setStyleSheet(style)

        with importlib.resources.path('styles', 'login.qss') as style_path:
            f = open(style_path, 'r')
            style = f.read()
            self.setStyleSheet(style)
            f.close()

        self.init_ui()
        self.load_saved_credentials()

    def init_ui(self):

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        h_layout = QHBoxLayout()
        h_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        login_container = QFrame(self)
        login_container.setObjectName("loginContainer")
        login_container.setFixedWidth(400)
        login_container.setMinimumHeight(450)

        layout = QVBoxLayout(login_container)
        layout.setContentsMargins(40,40,40,40)
        layout.setSpacing(24)
        
        self.label = QLabel("Audiobookshelf Login")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setObjectName("appTitle")

        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("Server URL")
        self.server_input.setMinimumHeight(40)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.username_input.setMinimumHeight(40)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(40)

        self.remember_me = QCheckBox("Remember Me")

        self.login_button = QPushButton("Login")
        self.login_button.setMinimumHeight(44)
        self.login_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_button.clicked.connect(self.attempt_login)

        layout.addWidget(self.label)
        layout.addWidget(self.server_input)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.remember_me)
        layout.addSpacing(12)
        layout.addWidget(self.login_button)
        layout.addStretch()

        main_layout.addWidget(login_container, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(main_layout)

    def load_saved_credentials(self):
        """Load saved credentials if available"""
        creds = self.creds.get_credentials()
        if creds["server_url"]:
            self.server_input.setText(creds["server_url"])
        if creds["username"]:
            self.username_input.setText(creds["username"])
        if creds["password"]:
            self.password_input.setText(creds["password"])

        self.remember_me.setChecked(creds["remember_me"])

    def attempt_login(self):
        self.login_button.setEnabled(False)
        self.login_button.setText("Logging in...")
        
        server_url = self.server_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not server_url or not username or not password:
            QMessageBox.warning(self, "Error", "Please fill in all fields.")
            self.login_button.setEnabled(True)
            self.login_button.setText("Login")
            return

        self.api.set_base_url(server_url)
        success = self.api.login(username, password)

        if success:
            if self.remember_me.isChecked():
                self.creds.save_credentials(
                    server_url,
                    username,
                    password,
                    remember=True
                    )
            else:
                self.creds.save_credentials(
                    server_url,
                    "",
                    "",
                    remember=False
                    )
            self.on_login_success(self.api.token)
        else:
            QMessageBox.critical(self, "Login Failed", "Invalid Credentials.")

        self.login_button.setEnabled(True)
        self.login_button.setText("Login")
