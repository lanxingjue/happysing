import sys
import json
import os
import sys # Re-import sys to use sys.maxsize

from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QStackedWidget, QMessageBox
from PyQt6.QtCore import Qt, QUrl, QStandardPaths # Import pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices

# From widgets package
from widgets.song_selection_widget import SongSelectionWidget
from widgets.learning_widget import LearningWidget

# Define data file paths
SONGS_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'songs.json')
USER_DATA_DIR = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
if USER_DATA_DIR == "" or not os.access(os.path.dirname(USER_DATA_DIR) if os.path.dirname(USER_DATA_DIR) else ".", os.W_OK):
    # Fallback if standard location is not available or not writable
    USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".happysing_appdata") # Use a less common name to avoid conflict
    print(f"Warning: Standard AppDataLocation not available or writable, falling back to {USER_DATA_DIR}")


os.makedirs(USER_DATA_DIR, exist_ok=True)
USER_PROGRESS_PATH = os.path.join(USER_DATA_DIR, 'user_progress.json')

# Default initial progress if file not found
DEFAULT_USER_PROGRESS = {
  "total_stars": 0,
  "unlocked_song_ids": ["pawpatrol"] # Default first unlocked song
}

# **新增：QSS 文件路径**
QSS_PATH = os.path.join(os.path.dirname(__file__), 'style.qss')

class MainWindow(QMainWindow):
    # Signal for SongSelectionWidget to notify MainWindow to attempt unlock
    # try_unlock_song_signal = pyqtSignal(str) # Emits song_id


    def __init__(self):
        super().__init__()

        # Load data
        self._load_songs_data()
        if not self.all_songs_data:
             # Only show critical error if file exists but is invalid/empty
             if os.path.exists(SONGS_DATA_PATH):
                 QMessageBox.critical(self, "错误", f"无法加载歌曲数据文件: {SONGS_DATA_PATH}\n请检查文件是否存在且格式正确。应用程序将退出。")
                 sys.exit(1)
             else:
                 QMessageBox.critical(self, "致命错误", f"歌曲数据文件未找到：\n{SONGS_DATA_PATH}\n应用程序将退出。")
                 sys.exit(1)


        self._load_user_progress()

        # Set window properties
        self.setWindowTitle("小歌星成长记 - Happy Sing!")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(800, 600)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # --- Create and add widgets ---
        # --- 创建和添加控件 ---

        # 歌曲选择控件
        # **确保这里没有传递 try_unlock_signal 参数**
        self.song_selection_widget = SongSelectionWidget(songs_data=self.all_songs_data, user_progress=self.user_progress)
        self.song_selection_widget.song_selected.connect(self.on_song_selected)

        # **确保连接的是 song_selection_widget 实例的 try_unlock_song_signal 信号**
        self.song_selection_widget.try_unlock_song_signal.connect(self.on_try_unlock_song)

        self.stacked_widget.addWidget(self.song_selection_widget) # 索引 0

        # 学习控件
        self.learning_widget = LearningWidget()
        self.learning_widget.back_to_select.connect(self.on_back_to_song_select)
        self.learning_widget.stars_earned.connect(self.on_stars_earned)
        self.learning_widget.song_completed.connect(self.on_song_completed)

        self.stacked_widget.addWidget(self.learning_widget) # 索引 1

        # 设置初始控件
        self.stacked_widget.setCurrentWidget(self.song_selection_widget)



    def _load_songs_data(self):
        """Loads all song data from JSON file."""
        self.all_songs_data = []
        if os.path.exists(SONGS_DATA_PATH):
            try:
                with open(SONGS_DATA_PATH, 'r', encoding='utf-8') as f:
                    self.all_songs_data = json.load(f)
                print(f"Successfully loaded {len(self.all_songs_data)} songs data.")
                # Validate minimum required fields for each song
                self.all_songs_data = [s for s in self.all_songs_data if s.get("id") and s.get("title") and isinstance(s.get("phrases"), list)]
                print(f"After validation, {len(self.all_songs_data)} valid songs remain.")
            except Exception as e:
                print(f"Error loading or parsing songs data file: {e}")
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
                         # Validate total_stars
                         if "total_stars" in loaded_progress and isinstance(loaded_progress["total_stars"], (int, float)):
                              self.user_progress["total_stars"] = max(0, int(loaded_progress["total_stars"])) # Ensure non-negative

                         # Validate unlocked_song_ids
                         if "unlocked_song_ids" in loaded_progress and isinstance(loaded_progress["unlocked_song_ids"], list):
                              # Ensure unlocked_song_ids are valid song IDs from songs data and are unique
                              valid_song_ids_from_data = {s.get("id") for s in self.all_songs_data if s.get("id")}
                              # Start with default unlocked IDs and add valid IDs from loaded data
                              initial_unlocked = set(DEFAULT_USER_PROGRESS["unlocked_song_ids"])
                              loaded_unlocked = set(loaded_progress["unlocked_song_ids"])
                              # Only keep IDs that are in the loaded data AND exist in songs.json
                              self.user_progress["unlocked_song_ids"] = list(initial_unlocked | (loaded_unlocked & valid_song_ids_from_data))
                              # Ensure the first default song is always unlocked if it exists in data
                              if "pawpatrol" in valid_song_ids_from_data and "pawpatrol" not in self.user_progress["unlocked_song_ids"]:
                                   self.user_progress["unlocked_song_ids"].append("pawpatrol")


                    print(f"Successfully loaded user progress from {USER_PROGRESS_PATH}. Total stars: {self.user_progress.get('total_stars', 0)}")
            except Exception as e:
                print(f"Error loading user progress file: {e}")
                print("Using default user progress.")
                # If load failed, ensure default unlocked song is present if it exists in song data
                valid_song_ids_from_data = {s.get("id") for s in self.all_songs_data if s.get("id")}
                if "pawpatrol" in valid_song_ids_from_data and "pawpatrol" not in self.user_progress["unlocked_song_ids"]:
                      self.user_progress["unlocked_song_ids"].append("pawpatrol")


        else:
            print(f"User progress file not found: {USER_PROGRESS_PATH}. Using default progress.")
            # Ensure the first default song is always unlocked if it exists in data
            valid_song_ids_from_data = {s.get("id") for s in self.all_songs_data if s.get("id")}
            if "pawpatrol" in valid_song_ids_from_data and "pawpatrol" not in self.user_progress["unlocked_song_ids"]:
                 self.user_progress["unlocked_song_ids"].append("pawpatrol")


    def _save_user_progress(self):
        """Saves current user progress to JSON file."""
        try:
            os.makedirs(os.path.dirname(USER_PROGRESS_PATH), exist_ok=True)
            # Only save the relevant fields
            progress_to_save = {
                "total_stars": self.user_progress.get("total_stars", 0),
                # Ensure unlocked_song_ids are unique before saving
                "unlocked_song_ids": list(set(self.user_progress.get("unlocked_song_ids", DEFAULT_USER_PROGRESS["unlocked_song_ids"])))
            }
            with open(USER_PROGRESS_PATH, 'w', encoding='utf-8') as f:
                json.dump(progress_to_save, f, indent=4)
            print(f"User progress saved to {USER_PROGRESS_PATH}.")
        except Exception as e:
            print(f"Error saving user progress file: {e}")
            # QMessageBox.warning(self, "保存失败", f"无法保存用户进度文件：{e}") # Avoid showing too many popups

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
            QMessageBox.warning(self, "错误", f"未找到歌曲数据：{song_id}")


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
        print(f"MainWindow received stars earned for a phrase: {stars}")
        self.user_progress["total_stars"] = self.user_progress.get("total_stars", 0) + stars
        self._save_user_progress()
        # Update the display on the learning widget immediately
        self.learning_widget.set_total_stars_display(self.user_progress.get("total_stars", 0))
        # Optional: Trigger visual effect for gaining stars in LearningWidget if needed


    def on_song_completed(self, song_id):
        """Slot: Handles a song completion event."""
        print(f"--- on_song_completed triggered for song ID: {song_id} ---")
        print(f"Current user progress before unlock check: {self.user_progress}")

        # Check for new songs unlocked based on the NEW total stars
        unlocked_something = False
        print("Checking songs for unlock:")
        valid_song_ids = {s.get("id") for s in self.all_songs_data if s.get("id")} # Get valid IDs once

        # Iterate through songs to find newly unlockable ones
        newly_unlocked_titles = []
        for song_data in self.all_songs_data:
             current_song_id = song_data.get("id")
             # Ensure song_data has a valid ID and is not already unlocked
             if current_song_id and current_song_id in valid_song_ids and current_song_id not in self.user_progress.get("unlocked_song_ids", []):
                  required_stars = song_data.get("unlock_stars_required", sys.maxsize) # Use maxsize if requirement not set
                  current_stars = self.user_progress.get("total_stars", 0)

                  # print(f"  - Checking unlock for '{song_data.get('title', current_song_id)}': Current Stars = {current_stars}, Required Stars = {required_stars}")

                  if current_stars >= required_stars:
                       # Unlock this song
                       self.user_progress["unlocked_song_ids"].append(current_song_id)
                       unlocked_something = True
                       newly_unlocked_titles.append(song_data.get('title', '新歌曲'))
                       print(f"    - SUCCESSFULLY Unlocked song: {song_data.get('title', current_song_id)}")
                  # else:
                       # print(f"    - Cannot unlock '{song_data.get('title', current_song_id)}': Not enough stars.")
             # else: # Already unlocked or invalid song data, no action needed
             #    pass # print(f"  - Song '{song_data.get('title', current_song_id)}' is already unlocked or invalid or already unlocked.")


        if unlocked_something:
             print("Unlocking process completed. Saving progress.")
             self._save_user_progress() # Save progress after unlocking
             # Show a message about unlocking any newly unlocked songs
             if newly_unlocked_titles:
                  QMessageBox.information(self, "新歌曲解锁！", f"恭喜！您解锁了以下歌曲：\n{', '.join(newly_unlocked_titles)}")


        print("--- on_song_completed finished ---")


    def on_try_unlock_song(self, song_id):
        """Slot: Handles unlock request from SongSelectionWidget."""
        print(f"MainWindow received unlock request for song ID: {song_id}")
        song_data = next((s for s in self.all_songs_data if s.get("id") == song_id), None)

        # Check if song exists and is currently locked
        if song_data and song_id not in self.user_progress.get("unlocked_song_ids", []):
            required_stars = song_data.get("unlock_stars_required", sys.maxsize)
            current_stars = self.user_progress.get("total_stars", 0)

            if current_stars >= required_stars:
                 # Perform unlock logic directly
                 self.user_progress["unlocked_song_ids"].append(song_id)
                 # Optionally deduct stars here if unlock cost is involved (not in current spec)
                 print(f"Attempted unlock successful for song: {song_data.get('title', song_id)}")
                 QMessageBox.information(self, "歌曲解锁成功！", f"恭喜！您解锁了歌曲：{song_data.get('title', '新歌曲')}！")
                 self._save_user_progress()
                 # Notify the selection widget to update its display
                 self.song_selection_widget.update_ui_based_on_progress(self.user_progress)
            else:
                # This case should ideally be prevented by button state, but good to handle
                print(f"Attempted unlock failed for song {song_id}: Not enough stars ({current_stars} < {required_stars}).")
                QMessageBox.information(self, "星星不足", f"解锁这首歌需要 ⭐ {required_stars} 颗星星，您还差 ⭐ {required_stars - current_stars} 颗。")


    def closeEvent(self, event):
        """Saves user progress before closing."""
        print("MainWindow closing. Saving progress...")
        self._save_user_progress()
        if self.learning_widget:
             # Make sure to call the child widget's closeEvent first for its cleanup
             # The LearningWidget's closeEvent will terminate PyAudio
             self.learning_widget.closeEvent(event) # Pass the event to the child

        super().closeEvent(event) # Call parent class's closeEvent
        # event.accept() # The default behavior is usually accept if not ignored earlier


def main():
    app = QApplication(sys.argv)
    # **新增：加载并应用 QSS 样式表**
    if os.path.exists(QSS_PATH):
        try:
            with open(QSS_PATH, "r", encoding="utf-8") as f:
                _style = f.read()
                app.setStyleSheet(_style)   
                print(f"Successfully loaded stylesheet: {QSS_PATH}")
        except Exception as e:
            print(f"Error loading stylesheet: {e}")
    else:
        print(f"Warning: Stylesheet file not found: {QSS_PATH}")



    main_window = MainWindow()

    # MainWindow constructor already checks for data and exits if critical error
    # So no need for redundant check here.

    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    # Check if required libraries are installed before running
    try:
        import pyaudio
        import numpy as np
        import librosa
        import scipy.signal
        from PyQt6.QtWidgets import QMessageBox # Import here for early check
    except ImportError as e:
        msg = f"缺少必要的Python库，请安装：\n{e}\n\n运行以下命令安装:\npip install -r requirements.txt"
        QMessageBox.critical(None, "缺少依赖", msg)
        sys.exit(1)

    # Check if main audio output device exists
    # Note: This check might not be 100% reliable depending on OS/drivers,
    # but gives a basic warning if no device is found at all.
    if not QMediaDevices.defaultAudioOutput():
         print("警告: 应用程序启动时未检测到默认音频输出设备。播放音频功能可能无法正常工作。")
         # Optionally show a message box:
         # QMessageBox.warning(None, "无音频输出设备", "未检测到默认音频输出设备。\n歌曲播放功能可能无法正常使用。")

    # Check if a microphone input device exists
    try:
        p = pyaudio.PyAudio()
        if p.get_device_count() == 0:
             print("警告: 应用程序启动时未检测到任何音频输入设备 (麦克风)。录音功能将无法使用。")
             # Optionally show a message box:
             # QMessageBox.warning(None, "无音频输入设备", "未检测到麦克风设备。\n歌曲录音功能将无法使用。")
        p.terminate() # Clean up the PyAudio instance used for the check
    except Exception as e:
         print(f"警告: 列举音频输入设备时发生错误: {e}. 录音功能可能无法使用。")
         # Optionally show a message box:
         # QMessageBox.warning(None, "麦克风设备错误", f"列举麦克风设备时发生错误：{e}\n录音功能可能无法使用。")


    main()