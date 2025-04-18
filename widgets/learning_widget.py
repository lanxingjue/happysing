import os
import sys
import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QMessageBox, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, QByteArray, QBuffer, QTime
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
        # 连接 positionChanged 信号，用于实时同步 (停止播放和可能的实时高亮)
        self.media_player.positionChanged.connect(self._on_position_changed)


        # --- 音频录制器 ---
        self.audio = None
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.input_device_index = None

        try:
            self.audio = pyaudio.PyAudio()
            default_input_device_info = self.audio.get_default_input_device_info() # Corrected method name
            self.input_device_index = default_input_device_info.get('index')
            print(f"找到默认音频输入设备: {default_input_device_info.get('name')} (Index: {self.input_device_index})")
        except Exception as e:
            print(f"警告: 未找到默认音频输入设备或列举设备时发生错误: {e}")
            print("录音功能可能无法使用。请检查麦克风设置。")

        self._record_timer = QTimer(self)
        self._record_timer.timeout.connect(self._read_audio_stream)
        self._record_start_time = None

        # --- 歌曲数据和进度 ---
        self.current_song_data = None
        self.current_phrase_index = 0
        # 存储当前播放乐句的时间信息，供 positionChanged 使用
        self.current_phrase_start_time_ms = -1
        self.current_phrase_end_time_ms = -1

        # --- UI 布局 ---
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 1. 歌曲标题区
        self.song_title_label = QLabel("请选择歌曲")
        self.song_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.song_title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #333;")
        main_layout.addWidget(self.song_title_label)

        # 2. 歌词显示区
        self.lyrics_label = QLabel("...")
        self.lyrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyrics_label.setWordWrap(True)
        # **修改此处：设置歌词默认样式和高亮样式**
        self._default_lyrics_style = "font-size: 22px; color: #555; min-height: 80px; border: 1px solid #ddd; padding: 10px; background-color: #f8f8f8; border-radius: 8px;"
        self._highlight_lyrics_style = "font-size: 24px; color: #007BFF; font-weight: bold; min-height: 80px; border: 2px solid #007BFF; padding: 10px; background-color: #e0f2ff; border-radius: 8px;" # 蓝色高亮，加粗
        self.lyrics_label.setStyleSheet(self._default_lyrics_style) # 应用默认样式
        self.lyrics_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(self.lyrics_label)

        # 3. 角色/反馈展示区
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
        if self.input_device_index is None or self.audio is None:
             self.record_button.setEnabled(False)


    def set_song_data(self, song_data):
        """设置当前学习歌曲的完整数据"""
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
        self.current_phrase_start_time_ms = -1 # Reset phrase times
        self.current_phrase_end_time_ms = -1

        audio_path = song_data.get('audio_full')
        if audio_path and os.path.exists(audio_path):
            media_content = QUrl.fromLocalFile(os.path.abspath(audio_path))
            self.media_player.setSource(media_content)
            print(f"尝试加载音频: {os.path.abspath(audio_path)}")
            if self.input_device_index is not None and self.audio is not None:
                self._set_control_buttons_enabled(True)
                self.record_button.setEnabled(True)
            else:
                 self._set_control_buttons_enabled(True)
                 self.record_button.setEnabled(False)
                 if self.input_device_index is None:
                      self.feedback_area.setText("未找到麦克风，只能听歌哦！")
                 elif self.audio is None:
                      self.feedback_area.setText("音频系统初始化失败，只能听歌哦！")

            self.update_phrase_display() # Update display to the first phrase
        else:
            self.lyrics_label.setText("...")
            self.feedback_area.setText(f"音频文件未找到: {audio_path}\n请返回选择其他歌曲或检查文件")
            print(f"错误: 音频文件未找到或路径无效: {audio_path}")
            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False)

    def update_phrase_display(self):
        """根据当前的乐句索引更新歌词显示"""
        # **修改此处：更新歌词文本和反馈区文本**
        phrases = self.current_song_data.get('phrases', [])
        if not self.current_song_data or self.current_phrase_index >= len(phrases):
            self.lyrics_label.setText("歌曲结束或无歌词")
            self.lyrics_label.setStyleSheet(self._default_lyrics_style) # 恢复默认样式
            self._set_control_buttons_enabled(False)
            self.next_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.feedback_area.setText("歌曲已结束！你真棒！")
            # TODO: Trigger song completion logic
            return

        phrase_data = phrases[self.current_phrase_index]
        self.lyrics_label.setText(phrase_data.get('text', '...'))
        self.lyrics_label.setStyleSheet(self._default_lyrics_style) # 确保显示新歌词时是默认样式

        self.feedback_area.setText(f"当前乐句 {self.current_phrase_index + 1} / {len(phrases)}\n请听一听 或 我来唱")

        # Ensure record button state is correct based on mic availability
        if self.input_device_index is not None and self.audio is not None:
             self.record_button.setEnabled(True)
        else:
             self.record_button.setEnabled(False)

        self.next_button.setEnabled(True)


    def play_current_phrase(self):
        """播放当前乐句对应的音频片段"""
        if self.is_recording:
             self.toggle_recording() # Stop recording if active

        if not self.media_player.source() or self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.InvalidMedia:
             print("音频未加载或无效，无法播放")
             QMessageBox.warning(self, "播放失败", "歌曲音频加载失败，请检查文件。")
             return

        phrases = self.current_song_data.get('phrases', [])
        if self.current_song_data and self.current_phrase_index < len(phrases):
            phrase_data = phrases[self.current_phrase_index]
            # **修改此处：存储当前乐句的时间信息**
            self.current_phrase_start_time_ms = int(phrase_data.get('start_time', 0) * 1000)
            # 使用媒体总时长作为默认结束时间，但检查 duration() 返回的有效性
            duration_ms = self.media_player.duration()
            default_end_time_ms = duration_ms if duration_ms > 0 else 10000 # 如果获取不到时长，给个默认值避免问题
            self.current_phrase_end_time_ms = int(phrase_data.get('end_time', default_end_time_ms / 1000.0) * 1000)

            # 确保结束时间不早于开始时间
            if self.current_phrase_end_time_ms < self.current_phrase_start_time_ms:
                 self.current_phrase_end_time_ms = self.current_phrase_start_time_ms + 2000 # 至少播放2秒

            # Ensure player is stopped before setting position and playing
            if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                self.media_player.stop()

            self.media_player.setPosition(self.current_phrase_start_time_ms)
            self.media_player.play()
            print(f"开始播放乐句 {self.current_phrase_index + 1} 从 {self.current_phrase_start_time_ms}ms 到 {self.current_phrase_end_time_ms}ms")

            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False)
            self.back_button.setEnabled(False)

            # **新增：播放时高亮歌词**
            self.lyrics_label.setStyleSheet(self._highlight_lyrics_style)


    def goto_next_phrase(self):
        """前进到下一句乐句"""
        if self.is_recording:
             self.toggle_recording()
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
             self.media_player.stop()

        # **新增：切换乐句时取消歌词高亮**
        self.lyrics_label.setStyleSheet(self._default_lyrics_style)
        self.current_phrase_start_time_ms = -1 # Reset phrase times
        self.current_phrase_end_time_ms = -1


        phrases = self.current_song_data.get('phrases', [])
        if self.current_song_data and self.current_phrase_index < len(phrases) - 1:
            self.current_phrase_index += 1
            self.update_phrase_display()
            self._set_control_buttons_enabled(True)
            if self.input_device_index is not None and self.audio is not None:
                 self.record_button.setEnabled(True)
            else:
                 self.record_button.setEnabled(False)
            self.back_button.setEnabled(True)
            print(f"前进到下一句乐句，索引：{self.current_phrase_index}")
        elif self.current_song_data and self.current_phrase_index == len(phrases) - 1:
            # This is the last phrase, mark song as completed
            print("已是最后一句话，歌曲完成！")
            self.current_phrase_index += 1 # Increment to indicate all phrases processed
            self.update_phrase_display() # Update display to song completion state
            self._set_control_buttons_enabled(False)
            self.next_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.back_button.setEnabled(True)
            # TODO: Trigger song completion logic, maybe show a celebration screen

    # --- 录音相关方法 --- (与 Step 5 修复版 v3 相同)

    def toggle_recording(self):
        """切换录音状态：开始录音或停止录音"""
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
            self.media_player.stop() # Stop playback if active

        # **新增：录音时取消歌词高亮**
        self.lyrics_label.setStyleSheet(self._default_lyrics_style)


        self.frames = []
        try:
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
                    background-color: #E53935; /* Red */
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
            self._record_start_time = None # Reset record start time

            self._record_timer.start(int(CHUNK / RATE * 1000))
            print("开始录音...")

        except Exception as e:
            self.is_recording = False
            self.record_button.setText("我来唱 (Record)")
            self.record_button.setStyleSheet(self.button_style) # Use instance attribute
            self._set_control_buttons_enabled(True)
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
        self.record_button.setStyleSheet(self.button_style) # Use instance attribute

        self._set_control_buttons_enabled(True)
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


    # --- 播放相关槽函数 ---

    def _on_playback_state_changed(self, state):
        """处理媒体播放状态变化"""
        # **修改此处：播放停止时取消歌词高亮**
        # Qt6 的 PlaybackState 有 PlayingState, PausedState, StoppedState
        print(f"播放状态变化: {state}")
        if state == QMediaPlayer.PlaybackState.StoppedState:
             print("播放已停止")
             # 取消歌词高亮
             self.lyrics_label.setStyleSheet(self._default_lyrics_style)
             self.current_phrase_start_time_ms = -1 # Reset phrase times
             self.current_phrase_end_time_ms = -1

             # 只有在没有录音的时候才重新启用控制按钮（录音按钮本身除外）
             if not self.is_recording:
                self._set_control_buttons_enabled(True)
                if self.input_device_index is not None and self.audio is not None:
                     self.record_button.setEnabled(True)
                else:
                     self.record_button.setEnabled(False)
                self.back_button.setEnabled(True)


    def _on_position_changed(self, position):
        """监听播放位置变化，用于在乐句结束时停止播放"""
        # **修改此处：使用存储的当前乐句结束时间来判断是否停止**
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and self.current_phrase_end_time_ms != -1:
             # 如果当前播放位置超过了当前乐句的结束时间，就停止播放
             if position >= self.current_phrase_end_time_ms:
                 self.media_player.stop()
                 print(f"在 {position}ms 停止播放，超过乐句结束时间 {self.current_phrase_end_time_ms}ms")
                 # stop() 会触发 playbackStateChanged 信号，在那里处理按钮启用和高亮重置


    def _on_media_error(self, error, error_string):
         # ... (与 Step 5 相同)
         print(f"媒体播放错误: {error} - {error_string}")
         self.feedback_area.setText(f"音频播放错误: {error_string}")
         QMessageBox.critical(self, "音频错误", f"播放音频时发生错误：{error_string}")
         self._set_control_buttons_enabled(False)
         self.record_button.setEnabled(False)


    def closeEvent(self, event):
        """窗口关闭时停止音频播放和录音，并释放 PyAudio 资源"""
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()
        if self.is_recording:
            self.stop_recording()

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
    import os

    app = QApplication(sys.argv)

    # Simulate song data (ensure the audio file exists and times match)
    test_audio_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'audio', 'pawpatrol_full.wav')
    test_song_data = {
        "id": "test_song_lyrics",
        "title": "测试歌词同步歌曲",
        "audio_full": test_audio_path,
        "audio_karaoke": None,
        "lyrics": "一句歌词在这里\n另一句在后面",
        "phrases": [
          {"text": "一句歌词在这里", "start_time": 0.0, "end_time": 2.0}, # Adjust times to match your test audio
          {"text": "另一句在后面", "start_time": 2.5, "end_time": 5.0}
        ],
        "unlocked": True
    }

    if not os.path.exists(test_song_data["audio_full"]):
         print(f"Test audio {test_song_data['audio_full']} not found. Playback will not work.")
         test_song_data["audio_full"] = None # Set to None if file missing

    learning_widget = LearningWidget()
    learning_widget.set_song_data(test_song_data)
    learning_widget.show()

    sys.exit(app.exec())