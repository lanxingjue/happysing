import os # 导入 os 模块用于路径拼接
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
# 导入 QtMultimedia 相关的类
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices

class LearningWidget(QWidget):
    # 定义信号，例如返回主菜单的信号
    back_to_select = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # 音频播放器相关
        self.media_player = QMediaPlayer()
        # 需要一个 QAudioOutput 来控制音频输出
        # QAudioOutput 需要指定一个音频设备，QMediaDevices.defaultAudioOutput() 获取默认输出设备
        output_device = QMediaDevices.defaultAudioOutput()
        if not output_device:
             print("警告: 未找到默认音频输出设备!") # 实际应用中应给用户提示
             self.audio_output = None
        else:
             self.audio_output = QAudioOutput(output_device)
             self.media_player.setAudioOutput(self.audio_output)

        # 连接播放状态变化的信号 (可选，但有助于调试和控制按钮状态)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.errorOccurred.connect(self._on_media_error) # 处理媒体错误
        self.media_player.positionChanged.connect(self._on_position_changed) # 监听播放位置变化

        # 歌曲数据和进度
        self.current_song_data = None
        self.current_phrase_index = 0

        # --- UI 布局 ---
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter) # 顶部居中对齐
        main_layout.setContentsMargins(20, 20, 20, 20) # 设置边距
        main_layout.setSpacing(15) # 设置部件间距

        # 1. 歌曲标题区
        self.song_title_label = QLabel("请选择歌曲") # 初始显示提示
        self.song_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.song_title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #333;")
        main_layout.addWidget(self.song_title_label)

        # 2. 歌词显示区
        self.lyrics_label = QLabel("...") # 初始显示省略号
        self.lyrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyrics_label.setWordWrap(True)
        self.lyrics_label.setStyleSheet("font-size: 22px; color: #555; min-height: 80px; border: 1px solid #ddd; padding: 10px; background-color: #f8f8f8; border-radius: 8px;")
        self.lyrics_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(self.lyrics_label)

        # 3. 角色/反馈展示区
        self.feedback_area = QLabel("等待歌曲数据...") # 初始显示提示
        self.feedback_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_area.setStyleSheet("font-size: 18px; color: #888; min-height: 200px; border: 1px dashed #ccc; background-color: #eee; border-radius: 8px;")
        self.feedback_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout.addWidget(self.feedback_area)

        # 4. 控制按钮区
        control_layout = QHBoxLayout()
        control_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.listen_button = QPushButton("听一听 (Listen)")
        self.record_button = QPushButton("我来唱 (Record)")
        self.next_button = QPushButton("下一句 (Next)")

        button_style = """
            QPushButton {
                font-size: 16px;
                padding: 10px 20px;
                border-radius: 8px;
                background-color: #FF9800; /* 橙色 */
                color: white;
                border: none;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:pressed {
                background-color: #e65100;
            }
            QPushButton:disabled { /* 按钮禁用时的样式 */
                background-color: #cccccc;
                color: #666666;
            }
        """
        self.listen_button.setStyleSheet(button_style)
        self.record_button.setStyleSheet(button_style)
        self.next_button.setStyleSheet(button_style)

        control_layout.addWidget(self.listen_button)
        control_layout.addWidget(self.record_button)
        control_layout.addWidget(self.next_button)

        main_layout.addLayout(control_layout)

        # 5. 返回按钮
        self.back_button = QPushButton("返回选择歌曲")
        self.back_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                padding: 8px 15px;
                border-radius: 5px;
                background-color: #9E9E9E; /* 灰色 */
                color: white;
                border: none;
                margin-top: 20px;
            }
            QPushButton:hover {
                background-color: #757575;
            }
            QPushButton:pressed {
                background-color: #616161;
            }
        """)
        self.back_button.clicked.connect(self.back_to_select.emit)
        self.back_button.setFixedSize(150, 40)
        back_button_layout = QHBoxLayout()
        back_button_layout.addStretch()
        back_button_layout.addWidget(self.back_button)
        main_layout.addLayout(back_button_layout)

        self.setLayout(main_layout)

        # --- 连接按钮信号到槽函数 ---
        self.listen_button.clicked.connect(self.play_current_phrase)
        # self.record_button.clicked.connect(self.start_recording) # 录音功能待实现
        self.next_button.clicked.connect(self.goto_next_phrase) # 下一句功能待实现

        # 初始禁用控制按钮，直到歌曲加载完成
        self._set_control_buttons_enabled(False)


    def set_song_data(self, song_data):
        """设置当前学习歌曲的完整数据"""
        self.current_song_data = song_data
        if not song_data:
            self.song_title_label.setText("加载歌曲失败")
            self.lyrics_label.setText("...")
            self.feedback_area.setText("请返回重新选择歌曲")
            self._set_control_buttons_enabled(False)
            return

        self.song_title_label.setText(f"歌曲：{song_data.get('title', '未知歌曲')}")
        self.feedback_area.setText("准备开始...")
        self.current_phrase_index = 0 # 从第一句开始

        # 尝试加载音频文件
        audio_path = song_data.get('audio_full')
        if audio_path and os.path.exists(audio_path): # 检查文件是否存在
            # 使用 QUrl.fromLocalFile 加载本地文件
            media_content = QUrl.fromLocalFile(os.path.abspath(audio_path))
            self.media_player.setSource(media_content)
            print(f"尝试加载音频: {os.path.abspath(audio_path)}")
            # 音频加载是异步的，不能立即播放，需要等待状态就绪
            # 我们可以连接 mediaStatusChanged 信号，但在简单场景下先假设加载会成功
            self._set_control_buttons_enabled(True) # 假设加载成功，启用按钮
            self.update_phrase_display() # 更新歌词显示到第一句
        else:
            self.lyrics_label.setText("...")
            self.feedback_area.setText(f"音频文件未找到: {audio_path}\n请返回选择其他歌曲或检查文件")
            print(f"错误: 音频文件未找到或路径无效: {audio_path}")
            self._set_control_buttons_enabled(False)
            # 可以提示用户音频文件丢失


    def update_phrase_display(self):
        """根据当前的乐句索引更新歌词显示"""
        if not self.current_song_data or self.current_phrase_index >= len(self.current_song_data.get('phrases', [])):
            self.lyrics_label.setText("歌曲结束或无歌词")
            self._set_control_buttons_enabled(False)
            self.next_button.setEnabled(False) # 歌曲结束，禁用下一句按钮
            self.feedback_area.setText("歌曲已结束！你真棒！")
            return

        phrase_data = self.current_song_data['phrases'][self.current_phrase_index]
        self.lyrics_label.setText(phrase_data.get('text', '...'))
        self.feedback_area.setText(f"当前乐句 {self.current_phrase_index + 1} / {len(self.current_song_data['phrases'])}\n请听一听...")
        # 确保“下一句”按钮可用（除非是最后一句话，下一句按钮功能应是完成歌曲）
        self.next_button.setEnabled(True) # 暂时总是启用，后续根据闯关逻辑调整

    def play_current_phrase(self):
        """播放当前乐句对应的音频片段"""
        if not self.media_player.source() or self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.InvalidMedia:
             print("音频未加载或无效，无法播放")
             QMessageBox.warning(self, "播放失败", "歌曲音频加载失败，请检查文件。")
             return

        if self.current_song_data and self.current_phrase_index < len(self.current_song_data.get('phrases', [])):
            phrase_data = self.current_song_data['phrases'][self.current_phrase_index]
            start_time_ms = int(phrase_data.get('start_time', 0) * 1000)
            end_time_ms = int(phrase_data.get('end_time', self.media_player.duration()) * 1000) # 如果没有结束时间，就播到媒体结束

            # 设置播放位置并播放
            self.media_player.setPosition(start_time_ms)
            self.media_player.play()
            print(f"开始播放乐句 {self.current_phrase_index + 1} 从 {start_time_ms}ms 到 {end_time_ms}ms")

            # 在播放时禁用按钮，避免重复点击
            self._set_control_buttons_enabled(False)
            # 播放结束后会通过信号重新启用按钮


    def goto_next_phrase(self):
        """前进到下一句乐句"""
        if self.current_song_data and self.current_phrase_index < len(self.current_song_data.get('phrases', [])) - 1:
            self.current_phrase_index += 1
            self.update_phrase_display()
            self._set_control_buttons_enabled(True) # 切换到下一句后重新启用按钮
            print(f"前进到下一句乐句，索引：{self.current_phrase_index}")
        elif self.current_song_data and self.current_phrase_index == len(self.current_song_data.get('phrases', [])) - 1:
            # TODO: 这是最后一句话，完成歌曲的逻辑
            print("已是最后一句话，歌曲完成！")
            self.current_phrase_index += 1 # 标记为已完成所有乐句
            self.update_phrase_display() # 更新为歌曲结束状态
            self._set_control_buttons_enabled(False) # 歌曲结束，禁用控制按钮
            self.next_button.setEnabled(False) # 特别禁用下一句按钮


    def _on_playback_state_changed(self, state):
        """处理媒体播放状态变化"""
        # Qt6 的 PlaybackState 有 PlayingState, PausedState, StoppedState
        print(f"播放状态变化: {state}")
        if state == QMediaPlayer.PlaybackState.StoppedState:
            # 播放停止时，重新启用控制按钮 (除非是用户手动停止，这里简单处理为播放结束)
            # 更精细的控制需要在 play_current_phrase 中设置一个定时器来判断是否是自然结束
            # 或者监听 QMediaPlayer.positionChanged 并判断是否超过了短语的结束时间
            # 简单的处理：当状态变为停止，并且不是因为用户手动停止（手动停止会立即触发）
            # 我们可以在 play_current_phrase 中设置一个定时器来在预定的结束时间停止播放，这样停止状态就可靠了
            # 或者监听 positionChanged
             print("播放已停止")
             # 只有当不是用户自己停止的时候才启用按钮。这里先总是启用，后续优化
             self._set_control_buttons_enabled(True) # 播放停止后重新启用按钮


    def _on_position_changed(self, position):
        """监听播放位置变化，用于在乐句结束时停止播放"""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and self.current_song_data:
             phrase_data = self.current_song_data['phrases'][self.current_phrase_index]
             end_time_ms = int(phrase_data.get('end_time', self.media_player.duration()) * 1000)
             # 如果当前播放位置超过了乐句的结束时间，就停止播放
             if position >= end_time_ms:
                 self.media_player.stop()
                 print(f"在 {position}ms 停止播放，超过乐句结束时间 {end_time_ms}ms")
                 # stop() 会触发 playbackStateChanged 信号，在那里处理按钮启用


    def _on_media_error(self, error, error_string):
         """处理媒体播放器发生的错误"""
         print(f"媒体播放错误: {error} - {error_string}")
         self.feedback_area.setText(f"音频播放错误: {error_string}")
         QMessageBox.critical(self, "音频错误", f"播放音频时发生错误：{error_string}")
         self._set_control_buttons_enabled(False)


    def _set_control_buttons_enabled(self, enabled):
        """统一设置控制按钮的可用状态"""
        self.listen_button.setEnabled(enabled)
        # self.record_button.setEnabled(enabled) # 录音按钮暂时不可用
        self.next_button.setEnabled(enabled)


    def closeEvent(self, event):
        """窗口关闭时停止音频播放"""
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()
        event.accept()


# 如果单独运行此文件，用于测试
if __name__ == '__main__':
    import sys
    import json # 导入 json 模块

    app = QApplication(sys.argv)

    # 为了测试，模拟加载一个歌曲数据
    test_song_data = {
        "id": "test_song_play",
        "title": "测试播放歌曲",
        "audio_full": "assets/audio/pawpatrol_full.wav", # 请确保这个文件存在且路径正确
        "audio_karaoke": null,
        "lyrics": "这是第一句测试歌词\n这是第二句测试歌词",
        "phrases": [
          {"text": "这是第一句测试歌词", "start_time": 0.0, "end_time": 3.0}, # 假设音频前3秒是第一句
          {"text": "这是第二句测试歌词", "start_time": 3.5, "end_time": 6.5} # 假设音频3.5到6.5秒是第二句
        ],
        "unlocked": true
    }

    learning_widget = LearningWidget()
    learning_widget.set_song_data(test_song_data) # 使用模拟数据设置歌曲
    learning_widget.show()

    # 如果 test_song_data["audio_full"] 文件不存在，这里会报错或警告，并且按钮会禁用
    if not os.path.exists(test_song_data["audio_full"]) and test_song_data["audio_full"] is not None:
         print(f"注意：测试音频文件 {test_song_data['audio_full']} 不存在，播放功能将无法使用。")


    sys.exit(app.exec())