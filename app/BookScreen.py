import importlib.resources
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QProgressDialog, QPushButton, QSizePolicy, QSpacerItem, QTextEdit, QVBoxLayout, QWidget, QMessageBox
from api.api import API
from api.book import Book
from app.Player import Player

class BookLoader(QObject):
    loading_complete = pyqtSignal(bool, object)
    progress_updated = pyqtSignal(int, float)

    def __init__(self, api, player):
        super().__init__()
        self.api = api
        self.player = player
        self.thread = QThread()
        self.moveToThread(self.thread)
        self.thread.started.connect(self._load_book)

        self.player.set_download_progress_callback(self._on_download_progress)

    def load_book(self, book_id):
        self.book_id = book_id
        if not self.thread.isRunning():
            self.thread.start()

    def _load_book(self):
        book = self.api.play_item(self.book_id)
        if book:
            success = self.player.load_book(book)
            self.loading_complete.emit(success, book)
        else:
            self.loading_complete.emit(False, None)
        self.thread.quit()

    def _on_download_progress(self, file_index, progress):
        self.progress_updated.emit(file_index, progress)

    def cleanup(self):
        if self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()


class BookScreen(QWidget):
    def __init__(self, book: Book, player: Player, api: API, back_callback):
        super().__init__()
        ## with open('styles/book_detail.qss') as f:
        ##     style = f.read()
        ##     self.setStyleSheet(style)
        with importlib.resources.path('styles', 'book_detail.qss') as style_path:
            f = open(style_path, 'r')
            style = f.read()
            self.setStyleSheet(style)
            f.close()        
        self.setObjectName("bookScreen")
        self.api = api
        self.player = player
        self.book = book
        self.back_callback = back_callback

        self.book_loaded = False
        self.progress_dialog = None

        self.book_loader = BookLoader(api, player)
        self.book_loader.loading_complete.connect(self.on_book_loaded)
        self.book_loader.progress_updated.connect(self.on_download_progress)

        self._build_ui()
        self.preload_book()

    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24,24,24,24)
        main_layout.setSpacing(16)

        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(24,24,24,24)
        content_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        title_author_layout = QVBoxLayout()
        
        title_label = QLabel(self.book.title)
        title_label.setObjectName("titleLabel")
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        author_label = QLabel(f"by {self.book.author}")
        author_label.setObjectName("authorLabel")
        title_author_layout.addWidget(title_label)
        if self.book.series:
            series_label = QLabel(self.book.series)
            series_label.setObjectName("seriesLabel")
            title_author_layout.addWidget(series_label)
        title_author_layout.addWidget(author_label)

        back_button = QPushButton("Back")
        back_button.setObjectName("backButton")
        back_button.setFixedHeight(36)
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        back_button.clicked.connect(self.back_callback)

        header_layout.addLayout(title_author_layout)
        header_layout.addWidget(back_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        cover_section = QHBoxLayout()
        cover_frame = QFrame()
        cover_frame.setObjectName("coverFrame")
        cover_frame.setFixedSize(300,300)
        cover_layout=QHBoxLayout(cover_frame)
        cover = QLabel()
        pixmap = QPixmap(self.book.cover_path)
        cover.setPixmap(pixmap.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation))
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_layout.addWidget(cover)

        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("playButton")
        self.play_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_button.clicked.connect(self.play_book)
        
        cover_section.addWidget(cover_frame)
        cover_section.addWidget(self.play_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        desc = QTextEdit()
        desc.setReadOnly(True)
        desc.setText(self.book.description or "No description available.")
        desc.setFrameShape(QFrame.Shape.NoFrame)
        desc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.status_label = QLabel("Ready to play")
        self.status_label.setObjectName("statusLabel")


        content_layout.addLayout(header_layout)
        content_layout.addLayout(cover_section)
        content_layout.addWidget(desc)
        content_layout.addWidget(self.status_label)

       
        spacer = QSpacerItem(10, 90, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(content_frame)
        main_layout.addItem(spacer)
        self.setLayout(main_layout)

    def preload_book(self):
        """Start loading the book in background as soon as the screen is shown."""
        self.status_label.setText("Loading...")
        self.status_label.setProperty("class", "warning")
        self.play_button.setText("Loading")
        self.book_loader.load_book(self.book.id)

    def on_book_loaded(self, success, book):
        """Callback when book is loaded."""
        if success:
            self.book_loaded = True
            self.status_label.setText("Ready")
            self.status_label.setProperty("class", "success")
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
            self.status_label.update()
            self.play_button.setEnabled(True)
            self.play_button.setText("Play")
            if self.progress_dialog and self.progress_dialog.isVisible():
                self.progress_dialog.close()
                self.player.play()
        else:
            self.play_button.setEnabled(False)
            self.status_label.setText("Failed")
            self.book_loaded = False

            if self.progress_dialog and self.progress_dialog.isVisible():
                self.progress_dialog.close()
                QMessageBox.critical(self, "Error", "Failed to load book")

    def on_download_progress(self, file_index, progress):
        """Update progess dialog with download progress."""
        if self.progress_dialog and isinstance(self.progress_dialog, QProgressDialog):
            self.progress_dialog.setValue(int(progress))

    def play_book(self):
        #self.player.stop()
        if self.book_loaded:
            self.player.play()

        else:
            self.progress_dialog = QProgressDialog(f"Loading {self.book.title}...", "Cancel", 0,100,self)
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setWindowTitle("Loading")
            self.progress_dialog.setAutoClose(False)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.show()

            self.book_loader.load_book(self.book.id)

    def closeEvent(self, a0):
        self.book_loader.cleanup()
        super().closeEvent(a0)

    def on_play_book_loaded(self, success, book):
        """Callback for when book is loaded for immediate playback."""
        if self.progress_dialog:
            self.progress_dialog.close()

        if success:
            self.player.load_book(book)
            self.book_loaded = True

            self.player.play()
            self.status_label.setText("Now playing")
        else:
            QMessageBox.critical(self, "Error", "Failed to load book.")

    def back_wrapper(self):
        self.book_loaded = False
        self.book = None
        self.back_callback()

        
