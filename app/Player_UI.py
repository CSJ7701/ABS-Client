import importlib.resources
from typing import Optional
from PyQt6.QtCore import QEvent, QPointF, QPropertyAnimation, QRect, QTimer, QVersionNumber, Qt
from PyQt6.QtGui import QAction, QBrush, QFont, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QFrame, QListWidget, QListWidgetItem, QMenu, QProgressBar, QSizePolicy, QSlider, QTextEdit, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout

from api.api import API
from app.Player import Player

class PlayerBar(QWidget):
    def __init__(self, player: Player, api: API, parent=None):
        super().__init__(parent)
        self.player = player
        self.api = api
        self.setup_ui(parent)

        if self.player.book:
            self.update_book_info(self.player.book)
            self.update_play_button_state()


    def setup_ui(self, parent):
        self.setObjectName("playerBar")  # Set an object name so we can target this specific widget

        with importlib.resources.path('styles', 'player.qss') as style_path:
            f = open(style_path, 'r')
            style = f.read()
            self.setStyleSheet(style)
            f.close()        

        ## with open('styles/player.qss', 'r') as f:
        ##     style = f.read()
        ##     self.setStyleSheet(style)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.expanded = False
        self.collapsed_height = 100
        self.setFixedHeight(self.collapsed_height)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,10)
        main_layout.setSpacing(0)

        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(0,0,0,0)
        progress_layout.setSpacing(2)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.installEventFilter(self)

        progress_text_layout = QHBoxLayout()
        progress_text_layout.setContentsMargins(10,2,10,0)

        self.chapter_progress_left = QLabel("00:00:00")
        self.chapter_progress_left.setObjectName("chapterProgressLeft")
        self.chapter_progress_right = QLabel("00:00:00")
        self.chapter_progress_right.setObjectName("chapterProgressRight")

        self.total_progress = QLabel("00:00:00 / 00:00:00")
        self.total_progress.setObjectName("totalProgress")
        self.total_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)        

        progress_text_layout.addWidget(self.chapter_progress_left)
        progress_text_layout.addStretch()
        progress_text_layout.addWidget(self.total_progress)
        progress_text_layout.addStretch()
        progress_text_layout.addWidget(self.chapter_progress_right)

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addLayout(progress_text_layout)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(16,8,16,8)

        self.book_title_label = QLabel("No Book")
        self.book_title_label.setObjectName("barTitle")
        self.book_title_label.setFixedWidth(100)
        self.book_title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.book_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.chapter_title_label = QLabel("")
        self.chapter_title_label.setObjectName("barChapter")
        self.chapter_title_label.setFixedWidth(100)
        self.chapter_title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.chapter_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        book_info_layout = QVBoxLayout()
        book_info_layout.addWidget(self.book_title_label)
        book_info_layout.addWidget(self.chapter_title_label)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.setContentsMargins(0,0,0,0)

        icon_font = QFont()
        icon_font.setPointSize(14)

        self.prev_button = QPushButton("󰒮")
        self.prev_button.setFixedSize(40,40)
        self.prev_button.setObjectName("prevButton")
        self.prev_button.setFont(icon_font)

        self.skip_backward_button = QPushButton("󰼥")
        self.skip_backward_button.setFixedSize(40,40)
        self.skip_backward_button.setObjectName("skipBackwardButton")
        self.skip_backward_button.setFont(icon_font)

        self.play_button = QPushButton("󰐎")
        self.play_button.setFixedSize(50,50)
        self.play_button.setObjectName("playButton")
        play_font = QFont()
        play_font.setPointSize(16)
        self.play_button.setFont(play_font)

        self.skip_forward_button = QPushButton("󰒬")
        self.skip_forward_button.setFixedSize(40,40)
        self.skip_forward_button.setObjectName("skipForwardButton")
        self.skip_forward_button.setFont(icon_font)

        self.next_button = QPushButton("󰒭")
        self.next_button.setFixedSize(40,40)
        self.next_button.setObjectName("nextButton")
        self.next_button.setFont(icon_font)

        buttons_layout.addWidget(self.prev_button)
        buttons_layout.addWidget(self.skip_backward_button)
        buttons_layout.addWidget(self.play_button)
        buttons_layout.addWidget(self.skip_forward_button)
        buttons_layout.addWidget(self.next_button)

        self.centered_buttons_container = QWidget()
        self.centered_buttons_container.setLayout(buttons_layout)

        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        right_controls = QHBoxLayout()
        right_controls.setSpacing(15)

        self.stop_button = QPushButton("󰓛")
        self.stop_button.setFixedSize(40,40)
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setFont(icon_font)

        self.playback_speed_button = QPushButton("1.0x")
        self.playback_speed_button.setFixedSize(70,36)
        self.playback_speed_button.setObjectName("playbackSpeedButton")
        
        self.volume_slider = QSlider(Qt.Orientation.Vertical)
        self.volume_slider.setFixedHeight(50)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.installEventFilter(self)

        right_controls.addWidget(self.playback_speed_button)
        right_controls.addWidget(self.volume_slider)
        
        content_layout.addLayout(book_info_layout)
        content_layout.addStretch()
        content_layout.addWidget(self.centered_buttons_container)
        content_layout.addStretch()
        content_layout.addLayout(right_controls)

        main_layout.addLayout(progress_layout)
        main_layout.addLayout(content_layout)

        self.setLayout(main_layout)

        # Position the stop button as an overlay.
        centered_buttons_container_rect = self.centered_buttons_container.geometry()
        stop_button_x = centered_buttons_container_rect.right() + 15
        self.stop_button.setParent(self)
        self.stop_button.move(stop_button_x, centered_buttons_container_rect.center().y() - self.stop_button.height() // 2)

        self.fullscreen_player = PlayerFullScreen(parent)
        self.fullscreen_player.hide()
        self.expanded = False

        self.installEventFilter(self)

        # Rolling Marquee for playerbar title
        self.title_offset = 0
        self.title_timer = QTimer(self)
        self.title_timer.timeout.connect(self.animate_title)
        self.title_full_text = ""

        self.prev_button.clicked.connect(self.previous)
        self.skip_backward_button.clicked.connect(self.skip_backward)
        self.play_button.clicked.connect(self.play_pause)
        self.skip_forward_button.clicked.connect(self.skip_forward)
        self.next_button.clicked.connect(self.next)

        self.stop_button.clicked.connect(self.stop)
        self.playback_speed_button.clicked.connect(self.show_playback_speed_menu)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.progress_bar.mousePressEvent = self.on_progress_bar_click


        # Setup callbacks
        self.player.set_position_callback(self.on_position_change)
        self.player.set_chapter_callback(self.on_chapter_change)
        self.player.set_playback_end_callback(self.on_playback_end)
        self.player.set_file_callback(self.on_file_change)

    def eventFilter(self, a0, a1) -> bool:
        if a0 == self and a1.type() == QEvent.Type.MouseButtonPress:
            self.toggle_expand()
            return True
        return super().eventFilter(a0,a1)

    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        self.position_stop_button()

    def showEvent(self, a0):
        super().showEvent(a0)
        self.position_stop_button()

    def toggle_expand(self):
        self.expanded = not self.expanded

        if self.expanded:
            self.show_fullscreen_player()
        else:
            self.hide_fullscreen_player()

    def show_fullscreen_player(self):
        main_window = self.parent()
        screen_height = main_window.height()

        start_rect = QRect(0, screen_height, main_window.width(), screen_height - self.collapsed_height)
        end_rect = QRect(0,0,main_window.width(), screen_height - self.collapsed_height)

        self.fullscreen_player.setGeometry(start_rect)
        self.fullscreen_player.show()
        self.fullscreen_player.raise_()

        self.animation = QPropertyAnimation(self.fullscreen_player, b"geometry")
        self.animation.setDuration(300)
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        self.animation.start()

    def hide_fullscreen_player(self):
        main_window = self.parent()
        screen_height = main_window.height()

        start_rect = self.fullscreen_player.geometry()
        end_rect = QRect(0, screen_height, main_window.width(), screen_height - self.collapsed_height)
        self.animation = QPropertyAnimation(self.fullscreen_player, b"geometry")
        self.animation.setDuration(300)
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        self.animation.finished.connect(self.fullscreen_player.hide)
        self.animation.start()

    def position_stop_button(self):
        rect = self.centered_buttons_container.geometry()

        button_x = rect.right() + 30
        button_y = rect.center().y() - self.stop_button.height() // 2

        self.stop_button.setParent(self)
        self.stop_button.move(button_x, button_y)
        self.stop_button.show()

    def show_playback_speed_menu(self):
        speeds = ["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "1.75x", "2.0x", "2.5x", "3.0x"]
        speed_menu = QMenu(self)
        speed_menu.setObjectName("speedMenu")

        for speed in speeds:
            action = QAction(speed, self)
            speed_menu.addAction(action)
            action.triggered.connect(lambda _, s=speed: self.set_playback_speed(s))

        button_pos = self.playback_speed_button.mapToGlobal(self.playback_speed_button.rect().topLeft())
        button_pos.setY(button_pos.y() - speed_menu.sizeHint().height())
        speed_menu.exec(button_pos)

    def set_playback_speed(self, speed):
        self.playback_speed_button.setText(speed)
        speed = float(speed.rstrip("x"))
        self.player.set_playback_speed(speed)

    def play_pause(self):
        if not self.player.paused:
            self.player.pause()
        elif self.player.paused:
            self.player.play()
        self.update_play_button_state()

    def stop(self):
        self.player.stop()
        self.reset()

    def next(self):
        self.player.next_chapter()

    def previous(self):
        self.player.previous_chapter()

    def skip_forward(self):
        self.player.skip_forward()

    def skip_backward(self):
        self.player.skip_backward()

    def set_volume(self, volume):
        self.player.set_volume(volume)

    def on_book_loaded(self, book):
        if book:
            self.update_book_info(book)
            self.update_progress()
            self.fullscreen_player.update_book_info(book)

            self.title_full_text = book.title
            if len(book.title) > 30:
                self.title_timer.start(200)
            else:
                self.title_timer.stop()
                self.book_title_label.setText(book.title)

    def animate_title(self):
        """Animate the title as a rolling banner"""
        if not self.title_full_text:
            return

        text_width = self.book_title_label.fontMetrics().horizontalAdvance(self.title_full_text)
        visible_width = self.book_title_label.width()

        if text_width <= visible_width:
            return

        self.title_offset = (self.title_offset + 1) % text_width
        padded_text = self.title_full_text + "   " + self.title_full_text

        # Calculate how many characters to cut from start.
        char_width = text_width / len(self.title_full_text)
        start_char = int(self.title_offset / char_width)
        display_text = padded_text[start_char:start_char+40]
        self.book_title_label.setText(display_text)

    def update_book_info(self, book):
        """Update UI with book information."""
        if book:
            self.book_title_label.setText(book.title)
            current_chapter = self.player.get_current_chapter()
            if current_chapter:
                self.chapter_title_label.setText(current_chapter.title)
            self.fullscreen_player.update_book_info(book)
            self.update_progress()

    def update_progress(self):
        """Update progress bar and time labels."""
        if not self.player.book:
            return

        global_position = self.player.get_current_position()
        total_duration = self.player.book.duration

        # Format time strings
        position_str = self.format_time(global_position)
        duration_str = self.format_time(total_duration)

        self.total_progress.setText(f"{position_str} / {duration_str}")

        current_chapter = self.player.get_current_chapter()
        if current_chapter:
            chapter_position = global_position - current_chapter.start
            chapter_duration = current_chapter.end - current_chapter.start

            chapter_progress_percentage = (chapter_position / chapter_duration) * 100 if chapter_duration > 0 else 0
            self.progress_bar.setValue(int(chapter_progress_percentage))

            chapter_position_str = self.format_time(chapter_position)
            chapter_duration_str = self.format_time(chapter_duration)

            self.chapter_progress_left.setText(chapter_position_str)
            self.chapter_progress_right.setText(chapter_duration_str)

    def update_chapter_info(self, chapter_index):
        """Update chapter information."""
        if self.player.book and chapter_index < len(self.player.book.chapters_metadata):
            chapter = self.player.book.chapters_metadata[chapter_index]
            self.chapter_title_label.setText(chapter.title)
            self.update_progress()

    def format_time(self, seconds):
        """Format seconds into HH:MM:SS"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def update_play_button_state(self):
        """Update play/pause button based on player state"""
        if self.player.playing and not self.player.paused:
            self.play_button.setText("󰏤")
        else:
            self.play_button.setText("󰐊")

    # Callbacks
    def on_position_change(self, position, chapter_index):
        self.update_progress()
    def on_chapter_change(self, chapter_index):
        self.update_chapter_info(chapter_index)
        self.fullscreen_player.update_current_chapter(chapter_index)
    def on_playback_end(self):
        self.update_play_button_state()
    def on_file_change(self, file_index):
        pass # Don't need to do anything AFAIK
    def on_progress_bar_click(self, event):
        if not self.player.book:
            return

        current_chapter = self.player.get_current_chapter()
        if not current_chapter:
            return

        width = self.progress_bar.width()
        x = event.position().x()
        percentage = max(0, min(x / width, 1.0))

        chapter_duration = current_chapter.end - current_chapter.start
        chapter_position = percentage * chapter_duration
        global_position = current_chapter.start + chapter_position
        success = self.player.seek_to_position(global_position)
        if success:
            self.update_progress()

    def reset(self):
        self.title_timer.stop()
        self.book_title_label.setText("No book")
        self.chapter_title_label.setText("")
        self.progress_bar.setValue(0)
        self.chapter_progress_left.setText("00:00:00")
        self.chapter_progress_right.setText("00:00:00")
        self.total_progress.setText("00:00:00 / 00:00:00")

        self.fullscreen_player.reset()

class RecordCoverArt(QWidget):
    def __init__(self, cover_path = None, parent = None):
        super().__init__(parent)
        self.setFixedSize(320,320)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_rotation)
        self.timer.start(50)
        self.cover_pixmap = QPixmap(cover_path if cover_path else None)

    def update_rotation(self):
        self.angle = (self.angle + 1) % 360
        self.update()

    def set_cover_art(self, path: Optional[str] = None):
        if path:
            self.cover_pixmap = QPixmap(path)
        else:
            self.cover_pixmap = QPixmap(None)
        self.update()

    def paintEvent(self, a0):
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            painter.translate(self.width() / 2, self.height() / 2)
            painter.rotate(self.angle)
            painter.translate(-self.width()/2, -self.height()/2)

            radius = min(self.width(), self.height()) // 2
            painter.setBrush(QBrush(Qt.GlobalColor.black))
            painter.drawEllipse(0,0,self.width(), self.height())

            pen = painter.pen()
            pen.setColor(Qt.GlobalColor.darkGray)
            pen.setWidth(1)
            painter.setPen(pen)

            for r in range(radius-5, int(radius*0.7), -4):
                painter.drawEllipse(int(self.width()/2 - r), int(self.height()/2 - r), r*2, r*2)

            painter.setBrush(QBrush(Qt.GlobalColor.gray))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(self.width()/2 - 4), int(self.height()/2-4), 8,8)

            if self.cover_pixmap and not self.cover_pixmap.isNull():
                label_size = int(radius * 0.9)
                center = QPointF(self.width() / 2, self.height() / 2)
                path = QPainterPath()
                path.addEllipse(center, label_size / 2, label_size/2)
                painter.setClipPath(path)
            
                scaled = self.cover_pixmap.scaled(label_size, label_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(int(center.x() - label_size/2),
                                int(center.y() - label_size/2),
                                label_size, label_size, scaled)
                painter.setClipping(False)


class PlayerFullScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fullscreenPlayer")
        ## with open('styles/player.qss') as f:
        ##     style = f.read()
        ##     self.setStyleSheet(style)
        with importlib.resources.path('styles', 'player.qss') as style_path:
            f = open(style_path, 'r')
            style = f.read()
            self.setStyleSheet(style)
            f.close()        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(24,24,24,24)
        
        left_column = QVBoxLayout()
        left_column.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.cover_frame = QFrame()
        self.cover_frame.setObjectName("coverFrame")
        self.cover_frame.setFixedSize(320,320)
        cover_layout = QVBoxLayout(self.cover_frame)
        cover_layout.setContentsMargins(0,0,0,0)
        self.rotating_record = RecordCoverArt()
        cover_layout.addWidget(self.rotating_record)

        self.title_label = QLabel("No Book")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.author_label = QLabel("")
        self.author_label.setObjectName("authorLabel")
        self.author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        left_column.addStretch()
        left_column.addWidget(self.cover_frame,0,Qt.AlignmentFlag.AlignCenter)
        left_column.addWidget(self.title_label)
        left_column.addWidget(self.author_label)
        left_column.addStretch()

        right_column = QVBoxLayout()
        right_column.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chapters_header = QLabel("Chapters")
        chapters_header.setObjectName("chaptersHeader")
        chapters_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.chapters_list = QListWidget()
        self.chapters_list.setObjectName("chaptersList")
        self.chapters_list.setFixedWidth(350)
        self.chapters_list.setMinimumHeight(400)

        right_column.addStretch()
        right_column.addWidget(chapters_header)
        right_column.addWidget(self.chapters_list,0,Qt.AlignmentFlag.AlignCenter)
        right_column.addStretch()

        main_layout.addLayout(left_column,1)
        main_layout.addLayout(right_column,1)

        self.setLayout(main_layout)

        if self.parent:
            # self.parent().installEventFilter(self)
            ...

    def eventFilter(self,a0,a1) -> bool:
        if a0 == self.parent() and a1.type() == QEvent.Type.Resize:
            self.setGeometry(0,0,self.parent().width(),
                             self.parent().height() - 90)
        return super().eventFilter(a0,a1)

    def update_book_info(self, book):
        if book:
            self.title_label.setText(book.title)
            self.author_label.setText(book.author)

            self.chapters_list.clear()

            if hasattr(book, 'cover_path') and book.cover_path:
                pixmap = QPixmap(book.cover_path)
                if not pixmap.isNull():
                    # Scale to fit cover frame while maintaining aspect ratio
                    frame_size = self.cover_frame.size()
                    scaled_pixmap = pixmap.scaled(
                        frame_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    #self.cover_placeholder.setPixmap(scaled_pixmap)
                    #self.cover_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.rotating_record.set_cover_art(book.cover_path)

            for i, chapter in enumerate(book.chapters_metadata):
                if i > 0:
                    item = QListWidgetItem(chapter.title)
                    item.setData(Qt.ItemDataRole.UserRole, i)
                    self.chapters_list.addItem(item)

            current_chapter = self.parent().player.current_chapter_index
            self.update_current_chapter(current_chapter)

            self.chapters_list.itemClicked.connect(self.on_chapter_selected)

    def update_current_chapter(self, chapter_index):
        """Update the selected chapter in the list"""
        for i in range(self.chapters_list.count()):
            item = self.chapters_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == chapter_index:
                self.chapters_list.setCurrentItem(item)
                break

    def on_chapter_selected(self, item):
        """Handle chapter selection from list"""
        chapter_index = item.data(Qt.ItemDataRole.UserRole)
        if chapter_index is not None:
            self.parent().player.seek_to_chapter(chapter_index)

    def reset(self):
        self.title_label.setText("No Book")
        self.author_label.setText("")
        self.chapters_list.clear()
        self.rotating_record.set_cover_art()
            
                        
