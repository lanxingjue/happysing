import sys
import json
import os
import sys # Re-import sys to use sys.maxsize

from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QStackedWidget, QMessageBox
from PyQt6.QtCore import Qt, QUrl, QStandardPaths, pyqtSignal # Import pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices

# From widgets package
from widgets.song_selection_widget import SongSelectionWidget
from widgets.learning_widget import LearningWidget

# Define data file paths
SONGS_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'songs.json')
USER_DATA_DIR = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
if USER_DATA_DIR == "":
    USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".happysing")
    print(f"Warning: AppDataLocation not available, falling back to {USER_DATA_DIR}")

os.makedirs(USER_DATA_DIR, exist_ok=True)
USER_PROGRESS_PATH = os.path.join(USER_DATA_DIR, 'user_progress.json')

# Default initial progress if file not found
DEFAULT_USER_PROGRESS = {
  "total_stars": 0,
  "unlocked_song_ids": ["pawpatrol"]
}


class MainWindow(QMainWindow):
    # **新增信号：用于 SongSelectionWidget 通知 MainWindow 尝试解锁歌曲**
    # This signal is not strictly needed if we directly call a method on parent,
    # but using signal is a more standard PyQt way for child to talk to parent.
    try_unlock_song_signal = pyqtSignal(str) # Emits song_id


    def __init__(self):
        super().__init__()

        # Load data
        self._load_songs_data()
        if not self.all_songs_data:
             QMessageBox.critical(self, "错误", f"无法加载歌曲数据文件: {SONGS_DATA_PATH}\n请检查文件是否存在且格式正确。")
             pass

        self._load_user_progress()

        # Set window properties
        self.setWindowTitle("小歌星成长记 - Happy Sing!")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(800, 600)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # --- Create and add widgets ---

        # Song selection widget
        self.song_selection_widget = SongSelectionWidget(songs_data=self.all_songs_data, user_progress=self.user_progress)
        self.song_selection_widget.song_selected.connect(self.on_song_selected)
        # **新增：连接 SongSelectionWidget 的 try_unlock_song_signal**
        # If using the signal approach in SongSelectionWidget
        self.try_unlock_song_signal.connect(self.on_try_unlock_song) # Connect signal defined in MainWindow

        # If calling parent method directly in SongSelectionWidget
        # self.song_selection_widget.set_parent_window(self) # Pass self reference (less preferred)


        self.stacked_widget.addWidget(self.song_selection_widget) # Index 0

        # Learning widget
        self.learning_widget = LearningWidget()
        self.learning_widget.back_to_select.connect(self.on_back_to_song_select)
        self.learning_widget.stars_earned.connect(self.on_stars_earned)
        self.learning_widget.song_completed.connect(self.on_song_completed)

        self.stacked_widget.addWidget(self.learning_widget) # Index 1

        # Set initial widget
        self.stacked_widget.setCurrentWidget(self.song_selection_widget)


    def _load_songs_data(self):
        """Loads all song data from JSON file."""
        self.all_songs_data = []
        if os.path.exists(SONGS_DATA_PATH):
            try:
                with open(SONGS_DATA_PATH, 'r', encoding='utf-8') as f:
                    self.all_songs_data = json.load(f)
                print(f"Successfully loaded {len(self.all_songs_data)} songs data.")
            except Exception as e:
                print(f"Error loading songs data file: {e}")
                self.all_songs_data = []
        else:
            print(f"Songs data file not found: {SONGS_DATA_PATH}")
            self.all_songs_data = []

    def _load_user_progress(self):
        """Loads user progress from JSON file."""
        self.user_progress = DEFAULT_USER_PROGRESS.copy()
        if os.path.exists(USER_PROGRESS_PATH):
            try:
                with open(USER_PROGRESS_PATH, 'r', encoding='utf-8') as f:
                    loaded_progress = json.load(f)
                    # Validate and merge loaded data
                    if isinstance(loaded_progress, dict):
                         if "total_stars" in loaded_progress and isinstance(loaded_progress["total_stars"], (int, float)):
                              self.user_progress["total_stars"] = int(loaded_progress["total_stars"])
                         if "unlocked_song_ids" in loaded_progress and isinstance(loaded_progress["unlocked_song_ids"], list):
                              # Ensure unlocked_song_ids are valid song IDs from songs data
                              valid_song_ids = {s.get("id") for s in self.all_songs_data if s.get("id")}
                              self.user_progress["unlocked_song_ids"] = list(set(loaded_progress["unlocked_song_ids"]) & valid_song_ids) # Only keep valid and unique IDs

                    print(f"Successfully loaded user progress from {USER_PROGRESS_PATH}. Total stars: {self.user_progress.get('total_stars', 0)}")
            except Exception as e:
                print(f"Error loading user progress file: {e}")
                print("Using default user progress.")
        else:
            print(f"User progress file not found: {USER_PROGRESS_PATH}. Using default progress.")

    def _save_user_progress(self):
        """Saves current user progress to JSON file."""
        try:
            os.makedirs(os.path.dirname(USER_PROGRESS_PATH), exist_ok=True)
            # Only save the relevant fields
            progress_to_save = {
                "total_stars": self.user_progress.get("total_stars", 0),
                "unlocked_song_ids": self.user_progress.get("unlocked_song_ids", DEFAULT_USER_PROGRESS["unlocked_song_ids"])
            }
            with open(USER_PROGRESS_PATH, 'w', encoding='utf-8') as f:
                json.dump(progress_to_save, f, indent=4)
            print(f"User progress saved to {USER_PROGRESS_PATH}.")
        except Exception as e:
            print(f"Error saving user progress file: {e}")
            QMessageBox.warning(self, "保存失败", f"无法保存用户进度文件：{e}")


    # --- Slots ---

    def on_song_selected(self, song_id):
        """Slot: Handles song selection."""
        print(f"MainWindow received selected song ID: {song_id}")

        selected_song_data = None
        for song in self.all_songs_data:
            if song.get("id") == song_id:
                selected_song_data = song
                break

        if selected_song_data:
            # Before switching, set song data and current stars in learning widget
            self.learning_widget.set_song_data(selected_song_data)
            self.learning_widget.set_total_stars_display(self.user_progress.get("total_stars", 0))

            self.stacked_widget.setCurrentWidget(self.learning_widget)
            print("Switched to learning widget.")
        else:
            print(f"Error: Song data not found for ID '{song_id}'.")
            QMessageBox.warning(self, "Error", f"Song data not found: {song_id}")


    def on_back_to_song_select(self):
        """Slot: Handles returning to song selection."""
        print("MainWindow received signal to return to song selection.")
        # Stop any ongoing playback or recording in learning widget
        if self.learning_widget:
            # Use the more robust way to reference PlaybackState
            if self.learning_widget.media_player.playbackState() != self.learning_widget.media_player.playbackState().__class__.StoppedState:
                 self.learning_widget.media_player.stop()
            if self.learning_widget.is_recording:
                 self.learning_widget.stop_recording()

        # Update the song selection UI based on current progress
        self.song_selection_widget.update_ui_based_on_progress(self.user_progress)

        self.stacked_widget.setCurrentWidget(self.song_selection_widget)
        print("Switched back to song selection widget.")

    def on_stars_earned(self, stars):
        """Slot: Handles stars earned for a phrase."""
        print(f"MainWindow received stars earned: {stars}")
        self.user_progress["total_stars"] = self.user_progress.get("total_stars", 0) + stars
        self._save_user_progress()
        self.learning_widget.set_total_stars_display(self.user_progress.get("total_stars", 0))
        # Optional: Trigger visual effect for gaining stars

    # **修改槽函数：完善歌曲完成和解锁逻辑**
    def on_song_completed(self, song_id):
        """Slot: Handles a song completion event."""
        print(f"--- on_song_completed triggered for song ID: {song_id} ---")
        print(f"Current user progress before unlock check: {self.user_progress}")

        # Song completion message is now shown in learning_widget itself
        # We just handle unlocking and saving here.

        unlocked_something = False
        print("Checking songs for unlock:")
        valid_song_ids = {s.get("id") for s in self.all_songs_data if s.get("id")} # Get valid IDs once

        for song_data in self.all_songs_data:
             current_song_id = song_data.get("id")
             # Ensure song_data has a valid ID and is not already unlocked
             if current_song_id and current_song_id in valid_song_ids and current_song_id not in self.user_progress.get("unlocked_song_ids", []):
                  required_stars = song_data.get("unlock_stars_required", sys.maxsize) # Use maxsize if requirement not set
                  current_stars = self.user_progress.get("total_stars", 0)

                  print(f"  - Checking unlock for '{song_data.get('title', current_song_id)}': Current Stars = {current_stars}, Required Stars = {required_stars}")

                  if current_stars >= required_stars:
                       # Unlock this song
                       self.user_progress["unlocked_song_ids"].append(current_song_id)
                       unlocked_something = True
                       print(f"    - SUCCESSFULLY Unlocked song: {song_data.get('title', current_song_id)}")
                       # Show a message about unlocking
                       QMessageBox.information(self, "新歌曲解锁！", f"恭喜！您解锁了歌曲：{song_data.get('title', '新歌曲')}！")
                  else:
                       print(f"    - Cannot unlock '{song_data.get('title', current_song_id)}': Not enough stars.")
             # else: # Already unlocked or invalid song data, no action needed
             #    print(f"  - Song '{song_data.get('title', current_song_id)}' is already unlocked or invalid.")


        if unlocked_something:
             print("Unlocking process completed. Saving progress.")
             self._save_user_progress() # Save progress after unlocking


        print("--- on_song_completed finished ---")


    # **新增槽函数：处理来自 SongSelectionWidget 的解锁请求**
    def on_try_unlock_song(self, song_id):
        """Slot: Handles unlock request from SongSelectionWidget."""
        print(f"MainWindow received unlock request for song ID: {song_id}")
        song_data = next((s for s in self.all_songs_data if s.get("id") == song_id), None)

        if song_data and song_id not in self.user_progress.get("unlocked_song_ids", []):
            required_stars = song_data.get("unlock_stars_required", sys.maxsize)
            current_stars = self.user_progress.get("total_stars", 0)

            if current_stars >= required_stars:
                 # Perform unlock logic directly
                 self.user_progress["unlocked_song_ids"].append(song_id)
                 print(f"Attempted unlock successful for song: {song_data.get('title', song_id)}")
                 QMessageBox.information(self, "歌曲解锁！", f"恭喜！您解锁了歌曲：{song_data.get('title', '新歌曲')}！")
                 self._save_user_progress()
                 # Notify the selection widget to update its display
                 self.song_selection_widget.update_ui_based_on_progress(self.user_progress)
            else:
                print(f"Attempted unlock failed for song {song_id}: Not enough stars.")
                # Message Box is shown in SongSelectionWidget's _try_unlock_song method


        # No need to switch widgets here, user stays on song selection


    def closeEvent(self, event):
        """Saves user progress before closing."""
        print("MainWindow closing. Saving progress...")
        self._save_user_progress()
        if self.learning_widget:
             # Make sure to call the child widget's closeEvent first for its cleanup
             self.learning_widget.closeEvent(event)

        super().closeEvent(event)
        event.accept()


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    if not main_window.all_songs_data and os.path.exists(SONGS_DATA_PATH):
         pass
    elif not main_window.all_songs_data and not os.path.exists(SONGS_DATA_PATH):
         QMessageBox.critical(None, "致命错误", f"歌曲数据文件未找到：\n{SONGS_DATA_PATH}\n应用程序将退出。")
         sys.exit(1)

    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()