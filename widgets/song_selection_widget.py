# 导入 QApplication 依然保留，用于单独测试此文件
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QApplication
from PyQt6.QtCore import Qt, pyqtSignal

class SongSelectionWidget(QWidget):
    # 定义一个信号，当歌曲被选中时发出，携带选中歌曲的ID
    song_selected = pyqtSignal(str)

    # 修改构造函数，接受 songs_data 参数
    def __init__(self, songs_data=None, parent=None):
        super().__init__(parent)

        # 使用传入的歌曲数据，如果未传入则使用默认的假定数据（用于单独测试）
        if songs_data is None:
             print("警告: SongSelectionWidget 在没有传入 songs_data 的情况下初始化，使用默认假定数据。")
             self.songs = [
                {"id": "pawpatrol", "title": "汪汪队立大功主题曲", "unlocked": True},
                {"id": "rabrador", "title": "拉布拉多警长主题曲", "unlocked": False, "unlock_stars_required": 50},
                {"id": "littlestar", "title": "小星星", "unlocked": True},
                {"id": "abc", "title": "ABC 歌", "unlocked": True}
             ]
        else:
             self.songs = songs_data # 使用外部传入的数据

        # 布局
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # 整体居中对齐
        layout.setSpacing(15) # 设置按钮之间的间距

        # 标题
        title_label = QLabel("请选择一首歌曲：")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title_label)

        # 创建歌曲按钮
        self.song_buttons = {} # 用于存储 id -> button 的映射
        if not self.songs: # 如果没有加载到歌曲数据
             no_songs_label = QLabel("没有可用的歌曲。")
             no_songs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
             no_songs_label.setStyleSheet("font-size: 18px; color: #888;")
             layout.addWidget(no_songs_label)
        else:
            for song_data in self.songs:
                 # 暂时只显示已解锁的歌曲 (unlocked=True)
                 if song_data.get("unlocked", False):
                     button = QPushButton(song_data["title"])
                     button.setFixedSize(250, 60) # 固定按钮大小
                     button.setStyleSheet("""
                        QPushButton {
                            font-size: 18px;
                            padding: 10px;
                            border-radius: 8px;
                            background-color: #4CAF50; /* 绿色 */
                            color: white;
                            border: none;
                        }
                        QPushButton:hover {
                            background-color: #45a049;
                        }
                        QPushButton:pressed {
                            background-color: #397d32;
                        }
                        /* 可以添加样式来区分锁定和解锁的歌曲，但目前只显示解锁的 */
                     """)
                     button.setProperty("song_id", song_data["id"])
                     button.clicked.connect(self._on_song_button_clicked)

                     layout.addWidget(button)
                     self.song_buttons[song_data["id"]] = button
                 # else:
                     # TODO: 可以添加一个灰色的、不可点击的按钮来显示未解锁的歌曲

        self.setLayout(layout)

    def _on_song_button_clicked(self):
        """槽函数：处理歌曲按钮点击事件"""
        sender_button = self.sender() # 获取是哪个按钮发出的信号
        song_id = sender_button.property("song_id") # 获取按钮存储的歌曲ID
        # song_title = sender_button.text() # 获取按钮文本（歌曲名） # 不再需要打印title

        print(f"选中了歌曲: ID='{song_id}'")

        # 发出信号，通知外部（如主窗口）有歌曲被选中了
        self.song_selected.emit(song_id)

# 如果单独运行此文件，用于测试
if __name__ == '__main__':
    import sys
    # 为了单独测试，需要创建 QApplication
    app = QApplication(sys.argv)
    # 可以在这里模拟加载数据，或者让它使用默认数据
    # with open('../data/songs.json', 'r', encoding='utf-8') as f:
    #     test_songs_data = json.load(f)
    # song_select_widget = SongSelectionWidget(songs_data=test_songs_data)
    # 或者使用默认数据：
    song_select_widget = SongSelectionWidget() # 将使用内部默认数据
    song_select_widget.show()
    sys.exit(app.exec())