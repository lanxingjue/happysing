import os
import sys
import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QMessageBox, QApplication # Import QApplication for testing
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, QByteArray, QBuffer, QTime # Import QTime if needed later for timing
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices, QMediaFormat

import pyaudio

# Define audio parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS_MAX = 15

class LearningWidget(QWidget):
    back_to_select = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 音频播放器 ---
        self.media_player = QMediaPlayer()
        output_device = QMediaDevices.defaultAudioOutput()
        if not output_device:
             print("警告: 未找到默认音频输出设备!")
             self.audio_output = None
        else:
             self.audio_output = QAudioOutput(output_device)
             self.media_player.setAudioOutput(self.audio_output)

        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.errorOccurred.connect(self._on_media_error)
        self.media_player.positionChanged.connect(self._on_position_changed)

        # --- 音频录制器 ---
        self.audio = None # Initialize PyAudio later
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.input_device_index = None

        # 初始化 PyAudio 并查找设备 (放在这里可以在窗口创建时就尝试)
        try:
            self.audio = pyaudio.PyAudio()
            # 使用 get_default_input_device_info() 修复 PyAudio 方法调用错误
            default_input_device_info = self.audio.get_default_input_device_info()
            self.input_device_index = default_input_device_info.get('index')
            print(f"找到默认音频输入设备: {default_input_device_info.get('name')} (Index: {self.input_device_index})")
        except Exception as e:
            print(f"警告: 未找到默认音频输入设备或列举设备时发生错误: {e}")
            print("录音功能可能无法使用。请检查麦克风设置。")
            # self.audio 保持 None 状态，或者尝试用 try-finally 确保 terminate

        self._record_timer = QTimer(self)
        self._record_timer.timeout.connect(self._read_audio_stream)
        self._record_start_time = None # Reset start time

        # --- UI 布局 --- (保持不变)
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        self.song_title_label = QLabel("请选择歌曲")
        self.song_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.song_title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #333;")
        main_layout.addWidget(self.song_title_label)

        self.lyrics_label = QLabel("...")
        self.lyrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyrics_label.setWordWrap(True)
        self.lyrics_label.setStyleSheet("font-size: 22px; color: #555; min-height: 80px; border: 1px solid #ddd; padding: 10px; background-color: #f8f8f8; border-radius: 8px;")
        self.lyrics_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(self.lyrics_label)

        self.feedback_area = QLabel("准备开始...")
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

        # **修改此处：将 button_style 存储为实例属性**
        self.button_style = """
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
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        self.listen_button.setStyleSheet(self.button_style) # 使用 self.button_style
        self.record_button.setStyleSheet(self.button_style) # 使用 self.button_style
        self.next_button.setStyleSheet(self.button_style) # 使用 self.button_style

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
        self.record_button.clicked.connect(self.toggle_recording)
        self.next_button.clicked.connect(self.goto_next_phrase)

        # 初始禁用控制按钮，直到歌曲加载完成，并且麦克风可用
        self._set_control_buttons_enabled(False)
        # 如果没有找到输入设备，录音按钮应永久禁用
        if self.input_device_index is None or self.audio is None: # 检查 self.audio 是否成功初始化
             self.record_button.setEnabled(False)


    def set_song_data(self, song_data):
        # ... (此方法与 Step 5 相同，更新按钮启用逻辑部分)
        self.current_song_data = song_data
        if not song_data:
            self.song_title_label.setText("加载歌曲失败")
            self.lyrics_label.setText("...")
            self.feedback_area.setText("请返回重新选择歌曲")
            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False)
            return

        self.song_title_label.setText(f"歌曲：{song_data.get('title', '未知歌曲')}")
        self.feedback_area.setText("准备开始...")
        self.current_phrase_index = 0

        audio_path = song_data.get('audio_full')
        if audio_path and os.path.exists(audio_path):
            media_content = QUrl.fromLocalFile(os.path.abspath(audio_path))
            self.media_player.setSource(media_content)
            print(f"尝试加载音频: {os.path.abspath(audio_path)}")
            # 音频加载成功且有输入设备时，启用按钮
            # 同时检查 self.audio 是否成功初始化
            if self.input_device_index is not None and self.audio is not None:
                self._set_control_buttons_enabled(True)
                self.record_button.setEnabled(True) # 明确启用录音按钮
            else:
                 # 没有输入设备或 PyAudio 初始化失败，只能听不能唱
                 self._set_control_buttons_enabled(True)
                 self.record_button.setEnabled(False)
                 if self.input_device_index is None:
                      self.feedback_area.setText("未找到麦克风，只能听歌哦！")
                 elif self.audio is None:
                      self.feedback_area.setText("音频系统初始化失败，只能听歌哦！")


            self.update_phrase_display()
        else:
            self.lyrics_label.setText("...")
            self.feedback_area.setText(f"音频文件未找到: {audio_path}\n请返回选择其他歌曲或检查文件")
            print(f"错误: 音频文件未找到或路径无效: {audio_path}")
            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False)

    def update_phrase_display(self):
        # ... (与 Step 5 相同，更新按钮启用逻辑部分)
        if not self.current_song_data or self.current_phrase_index >= len(self.current_song_data.get('phrases', [])):
            self.lyrics_label.setText("歌曲结束或无歌词")
            self._set_control_buttons_enabled(False)
            self.next_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.feedback_area.setText("歌曲已结束！你真棒！")
            return

        phrase_data = self.current_song_data['phrases'][self.current_phrase_index]
        self.lyrics_label.setText(phrase_data.get('text', '...'))
        self.feedback_area.setText(f"当前乐句 {self.current_phrase_index + 1} / {len(self.current_song_data['phrases'])}\n请听一听 或 我来唱")
        # 确保按钮状态正确
        if self.input_device_index is not None and self.audio is not None: # 检查 self.audio
             self.record_button.setEnabled(True)
        else:
             self.record_button.setEnabled(False)

        self.next_button.setEnabled(True)


    def play_current_phrase(self):
        # ... (与 Step 5 相同)
        if self.is_recording:
             self.toggle_recording()

        if not self.media_player.source() or self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.InvalidMedia:
             print("音频未加载或无效，无法播放")
             QMessageBox.warning(self, "播放失败", "歌曲音频加载失败，请检查文件。")
             return

        if self.current_song_data and self.current_phrase_index < len(self.current_song_data.get('phrases', [])):
            phrase_data = self.current_song_data['phrases'][self.current_phrase_index]
            start_time_ms = int(phrase_data.get('start_time', 0) * 1000)
            end_time_ms = int(phrase_data.get('end_time', self.media_player.duration()) * 1000)

            if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                self.media_player.stop()

            self.media_player.setPosition(start_time_ms)
            self.media_player.play()
            print(f"开始播放乐句 {self.current_phrase_index + 1} 从 {start_time_ms}ms 到 {end_time_ms}ms")

            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False) # 播放时禁用录音按钮
            self.back_button.setEnabled(False)


    def goto_next_phrase(self):
        # ... (与 Step 5 相同)
        if self.is_recording:
             self.toggle_recording()
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
             self.media_player.stop()

        if self.current_song_data and self.current_phrase_index < len(self.current_song_data.get('phrases', [])) - 1:
            self.current_phrase_index += 1
            self.update_phrase_display()
            self._set_control_buttons_enabled(True)
            # 检查 self.audio 初始化状态
            if self.input_device_index is not None and self.audio is not None:
                 self.record_button.setEnabled(True)
            else:
                 self.record_button.setEnabled(False)
            self.back_button.setEnabled(True)
            print(f"前进到下一句乐句，索引：{self.current_phrase_index}")
        elif self.current_song_data and self.current_phrase_index == len(self.current_song_data.get('phrases', [])) - 1:
            print("已是最后一句话，歌曲完成！")
            self.current_phrase_index += 1
            self.update_phrase_display()
            self._set_control_buttons_enabled(False)
            self.next_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.back_button.setEnabled(True)


    def toggle_recording(self):
        """切换录音状态：开始录音或停止录音"""
        # 检查 self.audio 初始化状态
        if self.input_device_index is None or self.audio is None:
            QMessageBox.warning(self, "录音失败", "未找到可用的麦克风设备或音频系统未初始化。")
            return

        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """开始录制音频"""
        if self.is_recording:
            return

        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()

        self.frames = []
        try:
            # self.audio 是在 __init__ 中初始化的 PyAudio 实例
            self.stream = self.audio.open(format=FORMAT,
                                         channels=CHANNELS,
                                         rate=RATE,
                                         input=True,
                                         frames_per_buffer=CHUNK,
                                         input_device_index=self.input_device_index)

            self.is_recording = True
            self.record_button.setText("停止录音 (Stop)")
            self.record_button.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
                    padding: 10px 20px;
                    border-radius: 8px;
                    background-color: #E53935; /* 红色 */
                    color: white;
                    border: none;
                    min-width: 120px;
                }
                QPushButton:hover {
                    background-color: #c62828;
                }
                QPushButton:pressed {
                    background-color: #b71c1c;
                }
            """)
            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(True)
            self.back_button.setEnabled(False)

            self.feedback_area.setText("正在录音...")
            # **修改此处：注释掉或设置为 None，避免错误**
            # self._record_start_time = self.media_player.getMediaStatus() # This caused error
            self._record_start_time = None # Or QTime.currentTime() for absolute time if needed later

            self._record_timer.start(int(CHUNK / RATE * 1000))
            print("开始录音...")

        except Exception as e:
            self.is_recording = False
            self.record_button.setText("我来唱 (Record)")
            # **修改此处：使用 self.button_style 恢复样式**
            self.record_button.setStyleSheet(self.button_style) # Use the instance attribute
            self._set_control_buttons_enabled(True)
            # 检查 self.audio 初始化状态
            if self.input_device_index is not None and self.audio is not None:
                 self.record_button.setEnabled(True)
            else:
                 self.record_button.setEnabled(False)
            self.back_button.setEnabled(True)
            self.feedback_area.setText("录音失败，请检查麦克风设置。")
            print(f"录音启动失败: {e}")
            QMessageBox.critical(self, "录音失败", f"无法启动录音设备：{e}\n请检查麦克风连接和权限设置。")
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

    def stop_recording(self):
        """停止录制音频"""
        if not self.is_recording:
            return

        self._record_timer.stop()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        self.is_recording = False
        self.record_button.setText("我来唱 (Record)")
        # **修改此处：使用 self.button_style 恢复样式，并移除重复定义**
        self.record_button.setStyleSheet(self.button_style) # Use the instance attribute
        # REMOVE: Redundant button_style definition here

        self._set_control_buttons_enabled(True)
        # 检查 self.audio 初始化状态
        if self.input_device_index is not None and self.audio is not None:
             self.record_button.setEnabled(True)
        self.back_button.setEnabled(True)

        print(f"停止录音。共录制 {len(self.frames)} 块音频数据。")
        self.feedback_area.setText("录音完成！准备分析...")

        # TODO: Trigger analysis and feedback here
        # current_phrase = self.current_song_data['phrases'][self.current_phrase_index]
        # self.analyze_and_provide_feedback(self.frames, current_phrase)

    def _read_audio_stream(self):
        # ... (与 Step 5 相同)
        if not self.is_recording or self.stream is None:
            return

        try:
            data = self.stream.read(CHUNK, exception_on_overflow=False)
            self.frames.append(data)

            recorded_duration = len(self.frames) * CHUNK / RATE
            if recorded_duration >= RECORD_SECONDS_MAX:
                 print(f"达到最大录音时长 ({RECORD_SECONDS_MAX}s)，自动停止录音。")
                 self.stop_recording()

        except IOError as e:
             pass
        except Exception as e:
            print(f"读取音频流时发生未知错误: {e}")
            self.stop_recording()

    def _set_control_buttons_enabled(self, enabled):
        """统一设置控制按钮的可用状态 (不包括录音按钮本身)"""
        self.listen_button.setEnabled(enabled)
        self.next_button.setEnabled(enabled)
        # self.record_button 的 enabled 状态由 toggle_recording 和 set_song_data 管理

    # --- 保留 Step 4 的其他槽函数和关闭事件 ---

    def _on_playback_state_changed(self, state):
        # ... (与 Step 5 相同，注意在播放停止后重新启用按钮时，检查 self.audio 初始化状态)
        print(f"播放状态变化: {state}")
        if state == QMediaPlayer.PlaybackState.StoppedState:
             print("播放已停止")
             if not self.is_recording:
                self._set_control_buttons_enabled(True)
                # 检查 self.audio 初始化状态
                if self.input_device_index is not None and self.audio is not None:
                     self.record_button.setEnabled(True)
                else:
                     self.record_button.setEnabled(False)
                self.back_button.setEnabled(True)

    def _on_position_changed(self, position):
        # ... (与 Step 5 相同)
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and self.current_song_data:
             phrase_data = self.current_song_data['phrases'][self.current_phrase_index]
             end_time_ms = int(phrase_data.get('end_time', self.media_player.duration()) * 1000)
             if position >= end_time_ms and end_time_ms > 0:
                 self.media_player.stop()
                 print(f"在 {position}ms 停止播放，超过乐句结束时间 {end_time_ms}ms")

    def _on_media_error(self, error, error_string):
         # ... (与 Step 5 相同)
         print(f"媒体播放错误: {error} - {error_string}")
         self.feedback_area.setText(f"音频播放错误: {error_string}")
         QMessageBox.critical(self, "音频错误", f"播放音频时发生错误：{error_string}")
         self._set_control_buttons_enabled(False)
         self.record_button.setEnabled(False) # 播放错误也禁用录音


    def closeEvent(self, event):
        """窗口关闭时停止音频播放和录音，并释放 PyAudio 资源"""
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()
        if self.is_recording:
            self.stop_recording()

        # Release PyAudio resource
        # Check if self.audio was successfully initialized before terminating
        if hasattr(self, 'audio') and self.audio:
             try:
                self.audio.terminate()
                print("PyAudio resource terminated")
             except Exception as e:
                print(f"Error terminating PyAudio resource: {e}")

        super().closeEvent(event)
        event.accept()


# If running this file directly for testing
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication
    import os # Import os for file existence check

    app = QApplication(sys.argv)

    # Simulate song data
    test_song_data = {
        "id": "test_song_record",
        "title": "测试录音歌曲",
        # Use a dummy path if the file doesn't exist, or ensure it does
        "audio_full": os.path.join(os.path.dirname(__file__), '..', 'assets', 'audio', 'pawpatrol_full.wav'), # Use relative path for testing
        "audio_karaoke": None,
        "lyrics": "这是第一句测试歌词\n这是第二句测试歌词",
        "phrases": [
          {"text": "这是第一句测试歌词", "start_time": 0.0, "end_time": 3.0},
          {"text": "这是第二句测试歌词", "start_time": 3.5, "end_time": 6.5}
        ],
        "unlocked": True
    }

    # Check for a potentially existing audio file for better testing
    if not os.path.exists(test_song_data["audio_full"]):
         print(f"Test audio {test_song_data['audio_full']} not found. Playback will not work.")
         test_song_data["audio_full"] = None


    learning_widget = LearningWidget()
    learning_widget.set_song_data(test_song_data)
    learning_widget.show()

    sys.exit(app.exec())