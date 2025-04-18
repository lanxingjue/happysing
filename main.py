import sys
import json
import os

from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QStackedWidget, QMessageBox
from PyQt6.QtCore import Qt, QUrl

# 从 widgets 包导入所需的部件
from widgets.song_selection_widget import SongSelectionWidget
from widgets.learning_widget import LearningWidget

# 导入 QtMultimedia 相关的类
# **撤销此处：移除直接导入 PlaybackState 的语句**
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices # 保持这个导入

# 定义歌曲数据文件路径
SONGS_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'songs.json')

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 加载歌曲数据
        self._load_songs_data()
        if not self.all_songs_data:
             QMessageBox.critical(self, "错误", f"无法加载歌曲数据文件: {SONGS_DATA_PATH}\n请检查文件是否存在且格式正确。")
             pass

        # 设置窗口属性
        self.setWindowTitle("小歌星成长记 - Happy Sing!")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(800, 600)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # --- 创建并添加各个界面 ---

        # 歌曲选择界面
        self.song_selection_widget = SongSelectionWidget(songs_data=self.all_songs_data)
        self.song_selection_widget.song_selected.connect(self.on_song_selected)
        self.stacked_widget.addWidget(self.song_selection_widget) # Index 0

        # 学习界面
        self.learning_widget = LearningWidget()
        self.learning_widget.back_to_select.connect(self.on_back_to_song_select)
        self.stacked_widget.addWidget(self.learning_widget) # Index 1

        # --- 设置初始界面 ---
        self.stacked_widget.setCurrentWidget(self.song_selection_widget)


    def _load_songs_data(self):
        """从 JSON 文件加载所有歌曲数据"""
        self.all_songs_data = []
        if os.path.exists(SONGS_DATA_PATH):
            try:
                with open(SONGS_DATA_PATH, 'r', encoding='utf-8') as f:
                    self.all_songs_data = json.load(f)
                print(f"成功加载歌曲数据: {len(self.all_songs_data)} 首")
            except Exception as e:
                print(f"加载歌曲数据文件时发生错误: {e}")
                self.all_songs_data = []
        else:
            print(f"歌曲数据文件未找到: {SONGS_DATA_PATH}")
            self.all_songs_data = []

    # --- 槽函数 ---

    def on_song_selected(self, song_id):
        # ... (与之前相同)
        print(f"MainWindow 接收到选中的歌曲 ID: {song_id}")

        selected_song_data = None
        for song in self.all_songs_data:
            if song.get("id") == song_id:
                selected_song_data = song
                break

        if selected_song_data:
            self.learning_widget.set_song_data(selected_song_data)
            self.stacked_widget.setCurrentWidget(self.learning_widget)
            print("切换到学习界面")
        else:
            print(f"错误: 未找到 ID 为 '{song_id}' 的歌曲数据")
            QMessageBox.warning(self, "错误", f"未找到歌曲数据: {song_id}")


    def on_back_to_song_select(self):
        """槽函数：处理从学习界面返回歌曲选择"""
        print("MainWindow 接收到返回歌曲选择信号")
        # 停止当前可能的音频播放和录音
        if self.learning_widget:
            # **修改此处：继续使用 QMediaPlayer.PlaybackState**
            if self.learning_widget.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                 self.learning_widget.media_player.stop()
            if self.learning_widget.is_recording:
                 self.learning_widget.stop_recording()

        self.stacked_widget.setCurrentWidget(self.song_selection_widget)
        print("切换回歌曲选择界面")


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()