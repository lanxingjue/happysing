import sys
import json # 导入 json 模块
import os # 导入 os 模块用于路径拼接

from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QStackedWidget, QMessageBox
from PyQt6.QtCore import Qt, QUrl

# 从 widgets 包导入所需的部件
from widgets.song_selection_widget import SongSelectionWidget
from widgets.learning_widget import LearningWidget

# 定义歌曲数据文件路径
SONGS_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'songs.json')

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 加载歌曲数据
        self._load_songs_data()
        if not self.all_songs_data:
             QMessageBox.critical(self, "错误", f"无法加载歌曲数据文件: {SONGS_DATA_PATH}\n请检查文件是否存在且格式正确。")
             # 如果加载失败，应用程序可能无法继续，可以选择退出或者显示错误界面
             # For now, we'll continue, but selection widget might be empty or misbehave
             pass # 继续运行，但歌曲列表可能是空的

        # 设置窗口属性
        self.setWindowTitle("小歌星成长记 - Happy Sing!")
        self.setGeometry(100, 100, 800, 600) # x, y, width, height
        self.setMinimumSize(800, 600) # 设置最小窗口大小

        # 使用 QStackedWidget 来管理不同的界面（如歌曲选择、学习界面等）
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # --- 创建并添加各个界面 ---

        # 歌曲选择界面
        # 将加载到的歌曲数据传递给 SongSelectionWidget
        self.song_selection_widget = SongSelectionWidget(songs_data=self.all_songs_data) # 传递数据
        # 连接 SongSelectionWidget 发出的信号到 MainWindow 的槽函数
        self.song_selection_widget.song_selected.connect(self.on_song_selected)
        self.stacked_widget.addWidget(self.song_selection_widget) # 索引 0

        # 学习界面
        self.learning_widget = LearningWidget()
        # 连接 LearningWidget 发出的返回信号
        self.learning_widget.back_to_select.connect(self.on_back_to_song_select)
        self.stacked_widget.addWidget(self.learning_widget) # 索引 1

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
                self.all_songs_data = [] # 加载失败则清空数据
        else:
            print(f"歌曲数据文件未找到: {SONGS_DATA_PATH}")
            self.all_songs_data = []

    # --- 槽函数 ---

    def on_song_selected(self, song_id):
        """槽函数：处理歌曲被选中事件"""
        print(f"MainWindow 接收到选中的歌曲 ID: {song_id}")

        # 从加载的所有歌曲数据中找到选中的歌曲
        selected_song_data = None
        for song in self.all_songs_data:
            if song.get("id") == song_id:
                selected_song_data = song
                break

        if selected_song_data:
            # 将找到的歌曲数据传递给学习界面
            self.learning_widget.set_song_data(selected_song_data)
            # 切换到学习界面
            self.stacked_widget.setCurrentWidget(self.learning_widget)
            print("切换到学习界面")
        else:
            print(f"错误: 未找到 ID 为 '{song_id}' 的歌曲数据")
            QMessageBox.warning(self, "错误", f"未找到歌曲数据: {song_id}")
            # 停留在歌曲选择界面


    def on_back_to_song_select(self):
        """槽函数：处理从学习界面返回歌曲选择"""
        print("MainWindow 接收到返回歌曲选择信号")
        # 停止当前可能的音频播放
        if self.learning_widget and self.learning_widget.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
             self.learning_widget.media_player.stop()
        self.stacked_widget.setCurrentWidget(self.song_selection_widget)
        print("切换回歌曲选择界面")


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    # 如果歌曲数据加载失败，且 MainWindow 中没有处理退出逻辑，可以在这里检查并退出
    if not main_window.all_songs_data and os.path.exists(SONGS_DATA_PATH):
         # 如果文件存在但加载失败，可能是格式问题，已经弹窗提示，可以继续让窗口显示以便看到错误信息
         pass
    elif not main_window.all_songs_data and not os.path.exists(SONGS_DATA_PATH):
         # 如果文件不存在，直接退出可能更合理
         # sys.exit(-1) # 或者其他错误码
         pass # 暂时不退出，让窗口显示错误提示

    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()