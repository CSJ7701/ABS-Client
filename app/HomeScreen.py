import os
import re
from PyQt6 import QtGui
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QAction, QPixmap, QShowEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QWidget, 
    QLabel, 
    QVBoxLayout, 
    QHBoxLayout, 
    QPushButton, 
    QLineEdit, 
    QComboBox
)
import importlib.resources
from api.api import API
from api.book import Book
from app.Player import Player
from .BookScreen import BookScreen


class HomeScreen(QWidget):
    """
    Home screen widget for the AudiobookShelf client application.
    Displays library selection, search functionality, and the main content area.
    """
    
    def __init__(self, api: API, player: Player, parent: QStackedWidget):
        """
        Initialize the home screen with API connection.
        
        Args:
            api: API object for communicating with the AudiobookShelf server
        """
        super().__init__()
        self.parent_widget = parent
        self.api = api
        self.libraries = {}
        self.current_library = None
        self.current_items = []
        self.in_progress_items = []
        self.player = player

        with importlib.resources.path('styles', 'home.qss') as style_path:
            f = open(style_path, 'r')
            style = f.read()
            self.setStyleSheet(style)
            f.close()
        
        # Setup UI components
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the user interface components."""
        main_layout = QVBoxLayout()
        
        # Create and add top bar and main area
        self.top_bar_layout = self._create_top_bar()
        self.main_area = self._create_main_area()
        
        main_layout.addLayout(self.top_bar_layout)
        main_layout.addWidget(self.main_area)
        main_layout.addItem(QSpacerItem(20,90, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
        
        self.setLayout(main_layout)
    
    def showEvent(self, a0: QShowEvent):
        """
        Handle the widget show event to fetch initial data.
        
        Args:
            event: The show event
        """
        super().showEvent(a0)
        self._fetch_libraries()
        self._fetch_in_progress_books()

    def resizeEvent(self, a0: QtGui.QResizeEvent) -> None:
        super().resizeEvent(a0)

        if self.current_items:
            self._adjust_grid_layout()
        
    def _create_top_bar(self) -> QHBoxLayout:
        """
        Create the top navigation bar with library selector, search bar and menu button.
        
        Returns:
            QHBoxLayout containing the top bar widgets
        """
        top_bar = QHBoxLayout()
        
        # Library selection dropdown
        self.library_select = QComboBox()
        self.library_select.setPlaceholderText("Select Library")
        self.library_select.currentIndexChanged.connect(self._update_current_library)
        
        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.returnPressed.connect(self._perform_search)
        
        # Menu button
        self.menu_button = QPushButton("≡")
        self.menu_button.setFixedWidth(40)
        self.menu_button.clicked.connect(self._show_menu)
        self.menu_button.setObjectName("menu_button")
        
        # Add widgets to layout
        top_bar.addWidget(self.library_select)
        top_bar.addWidget(self.search_bar, stretch=1)  # Search bar expands to fill space
        top_bar.addWidget(self.menu_button)
        
        return top_bar
    
    def _create_main_area(self) -> QWidget:
        """
        Create the main content area widget.
        
        Returns:
            QWidget to display the main content
        """
        self.grid_container = QWidget()
        self.grid_container.setObjectName("gridContainer")                
        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.grid_container.setLayout(self.grid_layout)
        self.grid_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)
        self.loading_label = QLabel("Loading Books...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid_layout.addWidget(self.loading_label, 0,0,1,2)
        scroll_area.setWidget(self.grid_container)
        return scroll_area

    def _show_menu(self):
        menu = QMenu(self)

        if self.in_progress_items:
            continue_header = QAction("Continue Listening", self)
            continue_header.setEnabled(False)
            font=continue_header.font()
            font.setBold(True)
            continue_header.setFont(font)
            menu.addAction(continue_header)

            for book in self.in_progress_items:
                title = book.title
                if len(title) > 30:
                    title = title[:27] + "..."

                book_action = QAction(title, self)
                book_action.triggered.connect(lambda checked, book_id = book.id: self._open_book_detail(book_id))
                menu.addAction(book_action)

            menu.addSeparator()

        logout_action = QAction("Logout", self)
        logout_action.triggered.connect(self._logout)
        menu.addAction(logout_action)

        menu.popup(self.menu_button.mapToGlobal(QPoint(0, self.menu_button.height())))

    def _adjust_grid_layout(self):
        container_width = self.grid_container.width()

        card_width = 320
        min_columns = 2

        max_columns = max(min_columns, container_width // card_width)

        if max_columns != getattr(self, '_current_columns', 0):
            self._current_columns = max_columns
            self.display_books(self.current_items)

    def _logout(self):
        self.parent_widget.logout()
    
    def _fetch_libraries(self):
        """Fetch available libraries from the API and populate the dropdown."""
        self.libraries = self.api.libraries()
        
        # Clear and populate library dropdown
        self.library_select.clear()
        
        for lib_name in self.libraries:
            self.library_select.addItem(lib_name)
            
        # Select the first library if available

        self.current_library = list(self.libraries.values())[0]
        self.library_select.setCurrentText(self.current_library.name)
    
    def _update_current_library(self):
        """Update the current library based on user selection."""
        selected_lib_name = self.library_select.currentText()
        self.current_library = self.libraries.get(selected_lib_name)
        if self.current_library:
            self._fetch_books()
                    
    def _fetch_books(self):
        """Load books for the currently selected library."""
        if not self.current_library:
            return

        # Clear existing widgets from grid.
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget and widget is not self.loading_label:
                widget.deleteLater()

        self.loading_label = QLabel("Loading Books...")
        self.grid_layout.addWidget(self.loading_label, 0, 0, 1, 2)

        try:
            books = self.api.library_items(self.current_library.id)
            self.current_items = books
            self._adjust_grid_layout()
            self.display_books(books)
        except ValueError as e:
            print("Error loading books: ", e)

    def _fetch_in_progress_books(self):

        in_progress_ids = self.api.in_progress()

        if not in_progress_ids:
            self.in_progress_items = []
            return

        in_progress_books = []
        for book_id in in_progress_ids:
            try:
                book = self.api.book_details(book_id)
                if book:
                    in_progress_books.append(book)
            except Exception as e:
                print(f"Error fetching in-progress book {book_id}: {e}")

        self.in_progress_items = in_progress_books

    def display_books(self, books):
        # Clear loading message
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        if not books:
            self.grid_layout.addWidget(QLabel("No results found."), 0,0)
            return

        rows, cols = 0,0
        max_columns = getattr(self, '_current_columns', 3)

        for book in books:
            if not hasattr(book, 'cover_path') or not book.cover_path:
                book.cover_path = self.api.download_cover(book.id)

            book_card = self._create_book_card(book)
            book_card.setFixedSize(300,350)
            self.grid_layout.addWidget(book_card, rows, cols, 1, 1, Qt.AlignmentFlag.AlignCenter)

            cols += 1
            if cols >= max_columns:
                cols = 0
                rows += 1

    def _create_book_card(self, book, is_in_progress=False):
        """Creates a QWidget that represents a book."""
        frame = QFrame()
        layout = QVBoxLayout()

        cover_label = QLabel()
        cover_label.setFixedSize(220, 250)
        pixmap = QPixmap(book.cover_path) if book.cover_path and os.path.exists(book.cover_path) else None
        if not pixmap or pixmap.isNull():
            placeholder_path = "resources/PlaceholderCover.jpg"
            pixmap = QPixmap(placeholder_path)
        cover_label.setPixmap(pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio))
        cover_label.setProperty("class", "card_cover")

        title_label = QLabel(book.title)
        title_label.setWordWrap(False)
        title_label.setProperty("class", "card_title")

        author_label = QLabel(book.author)
        author_label.setProperty("class", "card_author")

        layout.addWidget(cover_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author_label, alignment=Qt.AlignmentFlag.AlignCenter)

        frame.setLayout(layout)
        frame.setVisible(True)
        frame.setProperty("class", "card")
        frame.mousePressEvent = lambda a0: self._open_book_detail(book.id)
        return frame

    def _perform_search(self):
        query = self.search_bar.text().strip()
        if not query:
            self.display_books(self.current_items)
            return

        if "::" in query:
            field, value = query.split("::", 1)
            field = field.lower()
        else:
            field = "title"
            value = query

        pattern = re.compile(re.escape(value), re.IGNORECASE)

        matching_items = []
        for item in self.current_items:
            attr_value = getattr(item, field, "")
            if field == "genre" and isinstance(attr_value, list):
                if any(pattern.search(genre) for genre in attr_value):
                    matching_items.append(item)
            elif isinstance(attr_value, str) and pattern.search(attr_value):
                matching_items.append(item)

        self.display_books(matching_items)

    def _open_book_detail(self, book_id: str):
        detail = self.api.book_details(book_id)
        self.detail_widget = BookScreen(detail, self.player, self.api, self._back_to_library)
        self.parent_widget.addWidget(self.detail_widget)
        self.parent_widget.switch_page(self.detail_widget)

    def _back_to_library(self):
        self.parent_widget.removeWidget(self.detail_widget)
        self.detail_widget = None
        self.parent_widget.switch_page(self)

