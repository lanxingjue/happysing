import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QStackedWidget
from PyQt6.QtCore import Qt

# 从 widgets 包导入所需的部件
from widgets.song_selection_widget import SongSelectionWidget
from widgets.learning_widget import LearningWidget # 导入新的学习界面

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 设置窗口属性
        self.setWindowTitle("小歌星成长记 - Happy Sing!")
        self.setGeometry(100, 100, 800, 600) # x, y, width, height
        self.setMinimumSize(800, 600) # 设置最小窗口大小

        # 使用 QStackedWidget 来管理不同的界面（如歌曲选择、学习界面等）
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # --- 创建并添加各个界面 ---

        # 歌曲选择界面
        self.song_selection_widget = SongSelectionWidget()
        # 连接 SongSelectionWidget 发出的信号到 MainWindow 的槽函数
        self.song_selection_widget.song_selected.connect(self.on_song_selected)
        self.stacked_widget.addWidget(self.song_selection_widget) # 索引 0

        # 学习界面 (Placeholder for next steps)
        self.learning_widget = LearningWidget()
        # 连接 LearningWidget 发出的返回信号
        self.learning_widget.back_to_select.connect(self.on_back_to_song_select)
        self.stacked_widget.addWidget(self.learning_widget) # 索引 1

        # --- 设置初始界面 ---
        self.stacked_widget.setCurrentWidget(self.song_selection_widget)

    # --- 槽函数 ---

    def on_song_selected(self, song_id):
        """槽函数：处理歌曲被选中事件"""
        print(f"MainWindow 接收到选中的歌曲 ID: {song_id}")

        # 根据选中的歌曲ID，设置学习界面的歌曲信息
        # 在这个阶段，我们只是简单传递ID和查找对应的歌曲标题（使用 SongSelectionWidget 的数据）
        selected_song_title = "未知歌曲"
        for song in self.song_selection_widget.songs:
            if song["id"] == song_id:
                selected_song_title = song["title"]
                break

        self.learning_widget.set_song_data(song_id, selected_song_title)

        # 切换到学习界面
        self.stacked_widget.setCurrentWidget(self.learning_widget)
        print("切换到学习界面")


    def on_back_to_song_select(self):
        """槽函数：处理从学习界面返回歌曲选择"""
        print("MainWindow 接收到返回歌曲选择信号")
        self.stacked_widget.setCurrentWidget(self.song_selection_widget)
        print("切换回歌曲选择界面")


def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()