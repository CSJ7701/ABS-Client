import sys
from PyQt6.QtCore import QSize, QTimer
from PyQt6.QtWidgets import QApplication, QStackedWidget
import time

from api.api import API
from api.credentials import CredentialManager
from .LoginScreen import LoginScreen
from .HomeScreen import HomeScreen
from .Player import Player
from .Player_UI import PlayerBar

class AudiobookApp(QStackedWidget):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.api = API("")
        self.player = Player(self.api)
        self.creds = CredentialManager(self.api.data_dir)
        self.api.set_player(self.player)

        self.player_bar = PlayerBar(self.player, self.api, self)
        self.player_bar.hide()

        self.player.set_player_bar(self.player_bar)

        self.setWindowTitle("AudiobookShelf Client")
        self.setMinimumSize(QSize(1000,800))
        self.setGeometry(100,100,1000,800)

        self.show_login()

        app = QApplication.instance()
        app.aboutToQuit.connect(self.cleanup)

    def try_auto_login(self):
        creds = self.creds.get_credentials()

        if creds["remember_me"] and creds["server_url"] and creds["username"] and creds["password"]:
            QTimer.singleShot(20, self.login_screen.attempt_login)

    def show_login(self):
        self.login_screen = LoginScreen(self.handle_login_success, self.api, self.creds)

        self.addWidget(self.login_screen)
        self.setCurrentWidget(self.login_screen)
        QTimer.singleShot(30, self.try_auto_login)

    def handle_login_success(self, token):
        self.home_screen = HomeScreen(self.api, self.player, self)
        self.addWidget(self.home_screen)
        self.setCurrentWidget(self.home_screen)

        self.player_bar.setParent(self)
        self.player_bar.raise_()
        self.player_bar.show()
        self.update_player_bar_position()        

    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        self.update_player_bar_position()

    def update_player_bar_position(self):
        if self.player_bar.isVisible():
            self.player_bar.setGeometry(0, self.height() - self.player_bar.height(), self.width(), self.player_bar.height())

    def switch_page(self, page):
        self.setCurrentWidget(page)
        self.player_bar.raise_()
        self.update_player_bar_position()

    def logout(self):
        self.api = API("")
        self.player = Player(self.api)
        self.player_bar.hide()
        self.player_bar = PlayerBar(self.player, self.api, self)
        self.removeWidget(self.home_screen)
        self.removeWidget(self.login_screen)
        self.home_screen = None
        self.show_login()

    def cleanup(self):
        self.player.stop()
        if hasattr(self, "api") and self.api:
            if self.api.current_session:
                try:
                    self.api.sync_session(self.api.current_session, self.player)
                except Exception as e:
                    print(f"Error syncing current session: {e}")
            for session in self.api.sessions:
                try:
                    print(f"Closing session for {session.title}")
                    self.api.close_session(session.id)
                except Exception as e:
                    print(f"Error closing session: {e}")

def main():
    app = QApplication(sys.argv)
    window = AudiobookApp()
    window.show()
    sys.exit(app.exec())
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudiobookApp()
    window.show()
    sys.exit(app.exec())
