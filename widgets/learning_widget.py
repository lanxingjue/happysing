from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QApplication
from PyQt6.QtCore import Qt, pyqtSignal

class LearningWidget(QWidget):
    # 定义信号，例如返回主菜单的信号
    back_to_select = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # 主要布局
        main_layout = QVBoxLayout(self)
        # **修改此处：将 CenterX 改为 AlignHCenter**
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter) # 顶部居中对齐
        main_layout.setContentsMargins(20, 20, 20, 20) # 设置边距
        main_layout.setSpacing(15) # 设置部件间距

        # 1. 歌曲标题区
        self.song_title_label = QLabel("歌曲名称占位符")
        self.song_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # 这里 Center 既包括水平也包括垂直居中，没问题
        self.song_title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #333;")
        main_layout.addWidget(self.song_title_label)

        # 2. 歌词显示区 (用一个较大的QLabel表示)
        self.lyrics_label = QLabel("歌词会在这里一句一句显示...")
        self.lyrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # 这里 Center 既包括水平也包括垂直居中，没问题
        self.lyrics_label.setWordWrap(True) # 自动换行
        self.lyrics_label.setStyleSheet("font-size: 22px; color: #555; min-height: 80px; border: 1px solid #ddd; padding: 10px; background-color: #f8f8f8; border-radius: 8px;")
        # 设置SizePolicy让它能扩展
        self.lyrics_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(self.lyrics_label)

        # 3. 角色/反馈展示区 (用一个占位 QLabel 表示)
        # 这个区域可以用来显示动画、角色图片、得分、星星等反馈信息
        self.feedback_area = QLabel("角色动画和反馈会在这里显示\n(占位符)")
        self.feedback_area.setAlignment(Qt.AlignmentFlag.AlignCenter) # 这里 Center 既包括水平也包括垂直居中，没问题
        self.feedback_area.setStyleSheet("font-size: 18px; color: #888; min-height: 200px; border: 1px dashed #ccc; background-color: #eee; border-radius: 8px;")
        # 设置SizePolicy让它能扩展
        self.feedback_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.feedback_area)


        # 4. 控制按钮区
        control_layout = QHBoxLayout()
        # **修改此处：将 CenterX 改为 AlignHCenter**
        control_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter) # 按钮组居中

        self.listen_button = QPushButton("听一听 (Listen)")
        self.record_button = QPushButton("我来唱 (Record)")
        self.next_button = QPushButton("下一句 (Next)") # 或“完成本句”等

        # 按钮样式（与歌曲选择界面保持一致或稍作调整）
        button_style = """
            QPushButton {
                font-size: 16px;
                padding: 10px 20px;
                border-radius: 8px;
                background-color: #FF9800; /* 橙色 */
                color: white;
                border: none;
                min-width: 120px; /* 最小宽度 */
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:pressed {
                background-color: #e65100;
            }
        """
        self.listen_button.setStyleSheet(button_style)
        self.record_button.setStyleSheet(button_style)
        self.next_button.setStyleSheet(button_style)

        control_layout.addWidget(self.listen_button)
        control_layout.addWidget(self.record_button)
        control_layout.addWidget(self.next_button)

        main_layout.addLayout(control_layout)

        # 5. 返回按钮 (可选，但方便导航)
        self.back_button = QPushButton("返回选择歌曲")
        self.back_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                padding: 8px 15px;
                border-radius: 5px;
                background-color: #9E9E9E; /* 灰色 */
                color: white;
                border: none;
                margin-top: 20px; /* 与上面按钮组保持间距 */
            }
            QPushButton:hover {
                background-color: #757575;
            }
            QPushButton:pressed {
                background-color: #616161;
            }
        """)
        self.back_button.clicked.connect(self.back_to_select.emit) # 连接返回信号
        self.back_button.setFixedSize(150, 40) # 固定大小
        # 将返回按钮添加到主布局底部，并靠右对齐
        back_button_layout = QHBoxLayout()
        back_button_layout.addStretch() # 填充左侧空间
        back_button_layout.addWidget(self.back_button)
        main_layout.addLayout(back_button_layout)


        self.setLayout(main_layout)

    def set_song_data(self, song_id, song_title):
        """设置当前学习歌曲的信息"""
        self.current_song_id = song_id
        self.song_title_label.setText(f"歌曲：{song_title}")
        self.lyrics_label.setText("加载歌词中...") # 初始显示加载状态
        self.feedback_area.setText("角色动画和反馈会在这里显示\n(占位符)") # 重置反馈区

        # TODO: 根据 song_id 加载完整的歌曲数据（歌词、时序、音频等）
        # 这部分将在后续步骤实现

        print(f"LearningWidget 设置歌曲：{song_title} ({song_id})")

    # TODO: 添加播放、录音、下一句等功能的槽函数


# 如果单独运行此文件，用于测试
if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    learning_widget = LearningWidget()
    learning_widget.set_song_data("test_song", "测试歌曲")
    learning_widget.show()
    sys.exit(app.exec())