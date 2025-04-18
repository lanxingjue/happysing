# -*- coding: utf-8 -*-
import sys
# Import QApplication for testing
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QApplication, QFrame, QMessageBox
# Import QIcon if you are using icons for buttons (not in current style, but good practice)
# Import QUrl, QStandardPaths if needed, but seems not used in this widget directly
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QStandardPaths # Keep QUrl, QStandardPaths just in case


class SongSelectionWidget(QWidget):
    """
    歌曲选择界面的主控件。

    显示可选择歌曲列表，处理歌曲解锁逻辑和用户交互。
    """
    # 定义信号
    song_selected = pyqtSignal(str) # 选中歌曲时发出信号 (参数为歌曲 ID)
    try_unlock_song_signal = pyqtSignal(str) # 用户尝试解锁歌曲时发出信号 (参数为歌曲 ID)


    def __init__(self, songs_data=None, user_progress=None, parent=None):
        """
        构造函数，初始化歌曲选择界面的 UI。

        参数:
            songs_data (list, optional): 歌曲数据列表. Defaults to None.
            user_progress (dict, optional): 用户进度数据字典. Defaults to None.
            parent (QWidget, optional): 父控件. Defaults to None.
        """
        super().__init__(parent)

        # 设置对象名称，用于 QSS 样式表
        self.setObjectName("SongSelectionWidget")

        # 初始化歌曲数据和用户进度
        if songs_data is None:
             print("Warning: SongSelectionWidget initialized without songs_data. Using default dummy data.")
             # 默认的虚拟歌曲数据
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
             # 默认虚拟用户进度
             self.user_progress = {
                 "total_stars": 0,
                 "unlocked_song_ids": ["pawpatrol"] # 默认解锁汪汪队
             }
        else:
             self.user_progress = user_progress

        # 移除硬编码的按钮样式字符串，样式由 QSS 文件控制

        # --- UI 布局 ---
        layout = QVBoxLayout(self) # 创建垂直布局
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # 布局居中对齐
        layout.setSpacing(15) # 控件间距

        # 标题标签
        title_label = QLabel("请选择一首歌曲：")
        title_label.setObjectName("selectionTitleLabel") # 设置对象名称用于 QSS
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # 文本居中对齐
        # 样式由 QSS 控制
        layout.addWidget(title_label)

        # 显示当前星星数量的标签
        self.stars_display_label = QLabel(f"你现在有 ⭐ {self.user_progress.get('total_stars', 0)} 颗星星！")
        self.stars_display_label.setObjectName("selectionStarsLabel") # 设置对象名称用于 QSS
        self.stars_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # 文本居中对齐
        # 样式由 QSS 控制
        layout.addWidget(self.stars_display_label)

        # 创建一个容器控件来存放歌曲按钮
        self.songs_container_widget = QWidget()
        self.songs_layout = QVBoxLayout(self.songs_container_widget) # 容器内使用垂直布局
        self.songs_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # 容器内的按钮居中对齐
        self.songs_layout.setContentsMargins(0,0,0,0) # 移除容器的默认边距
        self.songs_layout.setSpacing(15) # 按钮之间的间距
        layout.addWidget(self.songs_container_widget) # 将容器添加到主布局

        # 初次填充歌曲按钮
        self._populate_song_buttons()

        # 在底部添加弹性空间，将内容推向中心或顶部
        layout.addStretch()

        self.setLayout(layout) # 设置主布局


    def _populate_song_buttons(self):
        """清除现有按钮，并根据当前歌曲数据和用户进度重新创建按钮。"""
        # 移除所有旧的歌曲按钮
        while self.songs_layout.count():
            item = self.songs_layout.takeAt(0) # 取出布局中的第一个项目
            widget = item.widget() # 获取项目中的控件 (按钮)
            if widget:
                widget.deleteLater() # 安排删除控件

        self.song_buttons = {} # 重置歌曲 ID 到按钮对象的映射字典

        # 如果没有歌曲数据，显示提示信息
        if not self.songs:
             no_songs_label = QLabel("没有可用的歌曲。")
             no_songs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
             no_songs_label.setStyleSheet("font-size: 18px; color: #888;") # 保留一点基础样式
             self.songs_layout.addWidget(no_songs_label)
        else:
            # 获取用户已解锁的歌曲 ID 列表和当前总星星数
            unlocked_ids = self.user_progress.get("unlocked_song_ids", [])
            current_stars = self.user_progress.get("total_stars", 0)

            # 遍历歌曲数据，为每首歌曲创建按钮
            for song_data in self.songs:
                 song_id = song_data.get("id") # 安全获取歌曲 ID
                 if not song_id: # 如果歌曲数据无效（没有 ID），跳过
                      print(f"Warning: Skipping song data with missing ID: {song_data}")
                      continue

                 song_title = song_data.get("title", song_id) # 获取歌曲标题，如果没有则使用 ID
                 is_unlocked = song_id in unlocked_ids # 判断歌曲是否已解锁
                 # 获取解锁所需的星星数量，如果没有指定则设为最大整数（表示不可解锁）
                 unlock_stars = song_data.get("unlock_stars_required", sys.maxsize)
                 can_unlock_now = current_stars >= unlock_stars # 判断用户星星是否足够解锁

                 # 构建按钮显示的文本
                 button_text = song_title
                 if not is_unlocked and unlock_stars != sys.maxsize: # 如果锁定且需要星星解锁
                     button_text = f"{song_title} (需要 ⭐ {unlock_stars})"
                 elif not is_unlocked and unlock_stars == sys.maxsize: # 如果锁定且不可用（不需要星星）
                     button_text = f"{song_title} (锁定)" # 指示锁定但没有星星要求

                 button = QPushButton(button_text) # 创建按钮
                 button.setObjectName("songButton") # 设置对象名称用于 QSS
                 button.setFixedSize(250, 60) # 固定按钮大小

                 # 断开按钮之前可能连接的所有信号，防止重复连接
                 try: button.clicked.disconnect()
                 except (TypeError, RuntimeError): pass # 如果没有连接或信号已断开则忽略异常

                 # 设置动态属性，用于 QSS 根据状态改变样式
                 button.setProperty("unlocked", is_unlocked)
                 button.setProperty("unlockable", can_unlock_now)
                 button.style().polish(button) # 刷新样式以立即应用动态属性变化


                 if is_unlocked:
                     button.setEnabled(True) # 解锁歌曲按钮启用
                     button.clicked.connect(self._on_song_button_clicked) # 连接点击信号到选择歌曲槽函数
                     button.setToolTip(f"点击开始 {song_title}") # 设置鼠标悬停提示

                 else: # 锁定歌曲
                     if can_unlock_now: # 如果星星足够解锁
                         button.setEnabled(True) # 启用按钮
                         # 连接点击信号到尝试解锁槽函数
                         button.clicked.connect(lambda checked, song_id=song_id: self._try_unlock_song(song_id))
                         button.setToolTip(f"点击解锁这首歌！需要 ⭐ {unlock_stars}")
                     else: # 如果星星不足或不可解锁
                         button.setEnabled(False) # 禁用按钮
                         # 设置鼠标悬停提示
                         if unlock_stars != sys.maxsize:
                              button.setToolTip(f"需要 ⭐ {unlock_stars} 颗星星解锁。您还差 ⭐ {max(0, unlock_stars - current_stars)} 颗。")
                         else:
                              button.setToolTip("这首歌暂时无法解锁。")


                 button.setProperty("song_id", song_id) # 使用属性存储歌曲 ID
                 self.songs_layout.addWidget(button) # 将按钮添加到容器布局
                 self.song_buttons[song_id] = button # 存储按钮引用


    def _on_song_button_clicked(self):
        """槽函数：处理点击已解锁歌曲按钮的事件。"""
        sender_button = self.sender() # 获取发送信号的按钮对象
        song_id = sender_button.property("song_id") # 获取按钮存储的歌曲 ID

        print(f"选中已解锁歌曲: ID='{song_id}'")
        self.song_selected.emit(song_id) # 触发 song_selected 信号，传递歌曲 ID


    def _try_unlock_song(self, song_id):
        """槽函数：处理点击锁定但可解锁歌曲按钮的事件。"""
        # 这个方法只会在按钮被启用（即 can_unlock_now 为 True）时触发
        print(f"尝试解锁歌曲 (通过按钮点击): {song_id}")
        # 在歌曲数据中查找对应的歌曲
        song_data = next((s for s in self.songs if s.get("id") == song_id), None)

        # 再次检查歌曲是否存在且当前是否锁定 (双重保险)
        if song_data and song_id not in self.user_progress.get("unlocked_song_ids", []):
             required_stars = song_data.get("unlock_stars_required", sys.maxsize)
             current_stars = self.user_progress.get("total_stars", 0)

             if current_stars >= required_stars:
                  # 触发 try_unlock_song_signal 信号，通知主窗口执行解锁和扣星（如果需要）逻辑
                  self.try_unlock_song_signal.emit(song_id)
                  # 主窗口会处理显示解锁成功的消息框和更新进度/保存。

             else:
                 # 理论上按钮在这种情况下不应该被启用，作为备用处理
                 QMessageBox.information(self, "星星不足", f"解锁这首歌需要 ⭐ {required_stars} 颗星星，您还差 ⭐ {required_stars - current_stars} 颗。")
        # 这里不需要更新 UI，主窗口在解锁成功后会调用 update_ui_based_on_progress


    def update_ui_based_on_progress(self, user_progress):
        """
        根据新的用户进度数据更新歌曲选择界面的显示。

        这个方法由主窗口调用，例如在用户星星数变化或歌曲解锁后。
        """
        self.user_progress = user_progress # 更新用户进度数据
        # 更新星星显示标签
        self.stars_display_label.setText(f"你现在有 ⭐ {self.user_progress.get('total_stars', 0)} 颗星星！")
        # 根据新的进度重新填充和更新歌曲按钮状态
        self._populate_song_buttons()


# 如果直接运行此文件进行测试
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication
    import os

    app = QApplication(sys.argv)

    # --- 为测试创建虚拟 QSS 文件 ---
    test_qss_content = """
    QWidget#SongSelectionWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 #87CEFA, stop:1 #ADD8E6); /* Light blue gradient */
    }
    QLabel#selectionTitleLabel {
        font-size: 20px; font-weight: bold; margin-bottom: 20px; color: #333;
    }
    QLabel#selectionStarsLabel {
        font-size: 18px; color: #FFD700;
    }
    QPushButton#songButton {
        font-size: 18px; padding: 10px; border-radius: 8px; border: none; min-width: 200px; font-weight: bold;
    }
    QPushButton#songButton[unlocked="true"] {
        background-color: #4CAF50; color: white;
    }
    QPushButton#songButton[unlocked="true"]:hover { background-color: #45a049; }
    QPushButton#songButton[unlocked="true"]:pressed { background-color: #397d32; }
    QPushButton#songButton[unlocked="false"] {
         color: #333;
    }
    QPushButton#songButton[unlocked="false"][unlockable="true"] {
        background-color: #FFC107;
    }
    QPushButton#songButton[unlocked="false"][unlockable="true"]:hover { background-color: #FFA000; }
    QPushButton#songButton[unlocked="false"][unlockable="true"]:pressed { background-color: #FF8F00; }
    QPushButton#songButton[unlocked="false"][unlockable="false"] {
        background-color: #9E9E9E; color: #666;
    }
    """
    # 创建一个临时的 qss 文件用于测试
    test_qss_path = "temp_test_style.qss"
    with open(test_qss_path, "w", encoding="utf-8") as f:
        f.write(test_qss_content)
    # 应用测试 qss
    try:
        with open(test_qss_path, "r", encoding="utf-8") as f:
            _style = f.read()
            app.setStyleSheet(_style)
            print(f"已加载测试样式表: {test_qss_path}")
    except Exception as e:
        print(f"加载测试样式表失败: {e}")


    # 模拟测试歌曲数据
    test_songs_data = [
        {"id": "pawpatrol", "title": "汪汪队立大功主题曲", "unlocked": True, "unlock_stars_required": 0},
        {"id": "rabrador", "title": "拉布拉多警长主题曲", "unlocked": False, "unlock_stars_required": 20},
        {"id": "littlestar", "title": "小星星", "unlocked": True, "unlock_stars_required": 0},
        {"id": "abc", "title": "ABC 歌", "unlocked": False, "unlock_stars_required": 5}
    ]
    # 模拟测试用户进度
    test_user_progress = {
        "total_stars": 10, # 10 颗星，可以解锁 ABC 歌，但不够解锁拉布拉多警长
        "unlocked_song_ids": ["pawpatrol", "littlestar"]
    }

    # 创建 SongSelectionWidget 实例并显示
    song_select_widget = SongSelectionWidget(songs_data=test_songs_data, user_progress=test_user_progress)
    song_select_widget.show()

    # 运行应用事件循环
    exit_code = app.exec()

    # 清理临时测试文件
    if os.path.exists(test_qss_path):
         os.remove(test_qss_path)
         print(f"已删除测试样式表文件: {test_qss_path}")

    sys.exit(exit_code)