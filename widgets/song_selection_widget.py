import sys # Import sys for sys.maxsize
# Import QApplication for testing
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QApplication, QFrame, QMessageBox # Import QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon

class SongSelectionWidget(QWidget):
    song_selected = pyqtSignal(str)
    # **新增信号：当用户尝试解锁歌曲时发出**
    try_unlock_song_signal = pyqtSignal(str) # Emits song_id


    def __init__(self, songs_data=None, user_progress=None, parent=None):
        super().__init__(parent)

        if songs_data is None:
             print("Warning: SongSelectionWidget initialized without songs_data. Using default dummy data.")
             self.songs = [
                {"id": "pawpatrol", "title": "汪汪队立大功主题曲", "unlocked": True, "unlock_stars_required": 0},
                {"id": "rabrador", "title": "拉布拉多警长主题曲", "unlocked": False, "unlock_stars_required": 20},
                {"id": "littlestar", "title": "小星星", "unlocked": True, "unlock_stars_required": 0},
                {"id": "abc", "title": "ABC 歌", "unlocked": False, "unlock_stars_required": 5}
             ]
        else:
             self.songs = songs_data

        if user_progress is None:
             print("Warning: SongSelectionWidget initialized without user_progress. Using default dummy progress.")
             self.user_progress = {
                 "total_stars": 0,
                 "unlocked_song_ids": ["pawpatrol"]
             }
        else:
             self.user_progress = user_progress

        # Store style strings as instance attributes
        self._unlocked_button_style = """
            QPushButton {
                font-size: 18px;
                padding: 10px;
                border-radius: 8px;
                background-color: #4CAF50; /* Green */
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #397d32;
            }
        """
        # **修改：锁定按钮样式，增加可解锁时的样式**
        self._locked_button_style_base = """
            QPushButton {
                font-size: 18px;
                padding: 10px;
                border-radius: 8px;
                color: white;
                border: none;
            }
        """
        self._locked_button_style_disabled = self._locked_button_style_base + """
             QPushButton {
                 background-color: #9E9E9E; /* Gray */
             }
        """
        self._locked_button_style_unlockable = self._locked_button_style_base + """
             QPushButton {
                 background-color: #FFC107; /* Amber */
                 color: #333; /* Darker text for contrast */
             }
             QPushButton:hover {
                background-color: #FFA000;
             }
             QPushButton:pressed {
                background-color: #FF8F00;
             }
        """


        # Layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(15)

        # Title
        title_label = QLabel("请选择一首歌曲：")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title_label)

        # Display current stars
        self.stars_display_label = QLabel(f"你现在有 ⭐ {self.user_progress.get('total_stars', 0)} 颗星星！")
        self.stars_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stars_display_label.setStyleSheet("font-size: 18px; color: #FFD700;")
        layout.addWidget(self.stars_display_label)

        # Create a container widget for song buttons
        self.songs_container_widget = QWidget()
        self.songs_layout = QVBoxLayout(self.songs_container_widget)
        self.songs_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.songs_layout.setSpacing(15)
        layout.addWidget(self.songs_container_widget)

        # Populate buttons initially
        self._populate_song_buttons()

        # Add a stretch at the bottom
        layout.addStretch()

        self.setLayout(layout)

    def _populate_song_buttons(self):
        """Clears existing buttons and creates new ones based on current data."""
        while self.songs_layout.count():
            item = self.songs_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.song_buttons = {} # Reset button mapping

        if not self.songs:
             no_songs_label = QLabel("没有可用的歌曲。")
             no_songs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
             no_songs_label.setStyleSheet("font-size: 18px; color: #888;")
             self.songs_layout.addWidget(no_songs_label)
        else:
            unlocked_ids = self.user_progress.get("unlocked_song_ids", [])
            current_stars = self.user_progress.get("total_stars", 0)

            for song_data in self.songs:
                 song_id = song_data["id"]
                 song_title = song_data["title"]
                 is_unlocked = song_id in unlocked_ids
                 unlock_stars = song_data.get("unlock_stars_required", sys.maxsize) # Use sys.maxsize if requirement not set
                 can_unlock_now = current_stars >= unlock_stars

                 button_text = song_title
                 if not is_unlocked:
                     button_text = f"锁定 - 需要 ⭐ {unlock_stars}"

                 button = QPushButton(button_text)
                 button.setFixedSize(250, 60)

                 # Disconnect any existing connections first to avoid multiple signals
                 try: button.clicked.disconnect()
                 except (TypeError, RuntimeError): pass # Ignore if not connected or signal already gone


                 if is_unlocked:
                     button.setStyleSheet(self._unlocked_button_style)
                     button.setEnabled(True)
                     button.clicked.connect(self._on_song_button_clicked)

                 else: # Locked song
                     if can_unlock_now:
                         button.setStyleSheet(self._locked_button_style_unlockable) # Use unlockable style
                         button.setEnabled(True) # Enable unlockable button
                         # Connect to unlock attempt logic
                         button.clicked.connect(lambda checked, song_id=song_id: self._try_unlock_song(song_id))
                         button.setToolTip(f"点击解锁这首歌！需要 ⭐ {unlock_stars}")
                     else:
                         button.setStyleSheet(self._locked_button_style_disabled) # Use disabled style
                         button.setEnabled(False) # Stay disabled


                 button.setProperty("song_id", song_id)
                 self.songs_layout.addWidget(button)
                 self.song_buttons[song_id] = button


    def _on_song_button_clicked(self):
        """Slot: Handles click on an UNLOCKED song button."""
        sender_button = self.sender()
        song_id = sender_button.property("song_id")

        print(f"Selected unlocked song: ID='{song_id}'")
        self.song_selected.emit(song_id)

    def _try_unlock_song(self, song_id):
        """Slot: Handles click on a potentially unlockable song button."""
        # This method is now only triggered if the button is enabled (can_unlock_now is True)
        print(f"Attempting to unlock song (via button click): {song_id}")
        song_data = next((s for s in self.songs if s.get("id") == song_id), None)

        if song_data and song_id not in self.user_progress.get("unlocked_song_ids", []):
             required_stars = song_data.get("unlock_stars_required", sys.maxsize)
             current_stars = self.user_progress.get("total_stars", 0)

             if current_stars >= required_stars:
                  # Emit signal to notify MainWindow to perform the unlock and deduct stars
                  self.try_unlock_song_signal.emit(song_id)
                  # MainWindow will handle the MessageBox and progress update/save

             else:
                 # This case should ideally not happen if the button is correctly disabled/styled
                 # but as a fallback, show the message.
                 QMessageBox.information(self, "星星不足", f"解锁这首歌需要 ⭐ {required_stars} 颗星星，您还差 ⭐ {required_stars - current_stars} 颗。")
        # No need to update UI here, MainWindow will call update_ui_based_on_progress after unlocking


    def update_ui_based_on_progress(self, user_progress):
        """Updates the song selection UI based on new user progress data."""
        self.user_progress = user_progress
        self.stars_display_label.setText(f"你现在有 ⭐ {self.user_progress.get('total_stars', 0)} 颗星星！")
        # Re-populate buttons based on new progress
        self._populate_song_buttons()


# If running this file directly for testing
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication
    # No need for json, os, QPixmap, QIcon in this simple test block

    app = QApplication(sys.argv)

    test_songs_data = [
        {"id": "pawpatrol", "title": "汪汪队立大功主题曲", "unlocked": True, "unlock_stars_required": 0},
        {"id": "rabrador", "title": "拉布拉多警长主题曲", "unlocked": False, "unlock_stars_required": 20},
        {"id": "littlestar", "title": "小星星", "unlocked": True, "unlock_stars_required": 0},
        {"id": "abc", "title": "ABC 歌", "unlocked": False, "unlock_stars_required": 5}
    ]
    test_user_progress = {
        "total_stars": 10,
        "unlocked_song_ids": ["pawpatrol", "littlestar"]
    }


    song_select_widget = SongSelectionWidget(songs_data=test_songs_data, user_progress=test_user_progress)
    song_select_widget.show()
    sys.exit(app.exec())