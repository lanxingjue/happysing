import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QStackedWidget
from PyQt6.QtCore import Qt

# 从新创建的 widgets 目录导入 SongSelectionWidget
from widgets.song_selection_widget import SongSelectionWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 设置窗口属性
        self.setWindowTitle("小歌星成长记 - Happy Sing!")
        self.setGeometry(100, 100, 800, 600) # x, y, width, height

        # 使用 QStackedWidget 来管理不同的界面（如歌曲选择、学习界面等）
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # 创建歌曲选择界面
        self.song_selection_widget = SongSelectionWidget()
        # 连接 SongSelectionWidget 发出的信号到 MainWindow 的槽函数
        self.song_selection_widget.song_selected.connect(self.on_song_selected)

        # 将歌曲选择界面添加到堆栈窗口
        self.stacked_widget.addWidget(self.song_selection_widget) # 索引 0

        # TODO: 创建学习界面 (Placeholder for next steps)
        # self.learning_widget = LearningWidget()
        # self.stacked_widget.addWidget(self.learning_widget) # 索引 1

        # 初始显示歌曲选择界面
        self.stacked_widget.setCurrentWidget(self.song_selection_widget)

        # 可以添加一个简单的欢迎界面作为堆栈的第一个页面，然后切换到歌曲选择
        # 或者像当前这样，直接从歌曲选择开始

    def on_song_selected(self, song_id):
        """槽函数：处理歌曲被选中事件"""
        print(f"MainWindow 接收到选中的歌曲 ID: {song_id}")

        # TODO: 根据选中的歌曲ID，加载歌曲数据，并切换到学习界面
        # self.load_song_data(song_id)
        # self.stacked_widget.setCurrentWidget(self.learning_widget)

        # 为了演示效果，可以先弹出一个消息框或者只是打印信息
        # QMessageBox.information(self, "歌曲选中", f"您选择了歌曲：{song_id}")
        pass # 本阶段暂时只打印信息，不做界面切换

def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()