# 添加这一行导入 QApplication
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QApplication # 在原有导入基础上加上 QApplication
from PyQt6.QtCore import Qt, pyqtSignal

class SongSelectionWidget(QWidget):
    # 定义一个信号，当歌曲被选中时发出，携带选中歌曲的ID
    song_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 布局
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # 整体居中对齐
        layout.setSpacing(15) # 设置按钮之间的间距

        # 标题
        title_label = QLabel("请选择一首歌曲：")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title_label)

        # 假定的歌曲数据
        self.songs = [
            {"id": "pawpatrol", "title": "汪汪队立大功主题曲"},
            {"id": "rabrador", "title": "拉布拉多警长主题曲"},
            {"id": "littlestar", "title": "小星星"},
            {"id": "abc", "title": "ABC 歌"}
        ]

        # 创建歌曲按钮
        self.song_buttons = {} # 用于存储 id -> button 的映射
        for song_data in self.songs:
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
            """)
            # 将歌曲ID作为按钮的属性存储，方便后续查找
            button.setProperty("song_id", song_data["id"])
            # 连接按钮点击信号到槽函数
            button.clicked.connect(self._on_song_button_clicked)

            layout.addWidget(button)
            self.song_buttons[song_data["id"]] = button

        self.setLayout(layout)

    def _on_song_button_clicked(self):
        """槽函数：处理歌曲按钮点击事件"""
        sender_button = self.sender() # 获取是哪个按钮发出的信号
        song_id = sender_button.property("song_id") # 获取按钮存储的歌曲ID
        song_title = sender_button.text() # 获取按钮文本（歌曲名）

        print(f"选中了歌曲: ID='{song_id}', Title='{song_title}'") # 打印到控制台，作为初步验证

        # 发出信号，通知外部（如主窗口）有歌曲被选中了
        self.song_selected.emit(song_id)

# 如果单独运行此文件，用于测试
if __name__ == '__main__':
    import sys
    # 这段代码需要 QApplication 才能运行
    app = QApplication(sys.argv)
    song_select_widget = SongSelectionWidget()
    song_select_widget.show()
    sys.exit(app.exec())