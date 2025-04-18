import os
import sys
import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QMessageBox, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, QByteArray, QBuffer, QTime
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices, QMediaFormat

import pyaudio
import numpy as np # 导入 NumPy

# Define audio parameters (保持与 Step 5 相同)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS_MAX = 15

class LearningWidget(QWidget):
    back_to_select = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 音频播放器 --- (保持与 Step 6 相同)
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

        # --- 音频录制器 --- (保持与 Step 6 修复版 v3 相同)
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

        # --- 歌曲数据和进度 --- (保持与 Step 6 相同)
        self.current_song_data = None
        self.current_phrase_index = 0
        self.current_phrase_start_time_ms = -1
        self.current_phrase_end_time_ms = -1

        # --- UI 布局 --- (保持与 Step 6 相同)
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
        self._default_lyrics_style = "font-size: 22px; color: #555; min-height: 80px; border: 1px solid #ddd; padding: 10px; background-color: #f8f8f8; border-radius: 8px;"
        self._highlight_lyrics_style = "font-size: 24px; color: #007BFF; font-weight: bold; min-height: 80px; border: 2px solid #007BFF; padding: 10px; background-color: #e0f2ff; border-radius: 8px;"
        self.lyrics_label.setStyleSheet(self._default_lyrics_style)
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

        # **修改此处：将 button_style 存储为实例属性** (Step 5 修复)
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
        self.listen_button.setStyleSheet(self.button_style)
        self.record_button.setStyleSheet(self.button_style)
        self.next_button.setStyleSheet(self.button_style)

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


    # --- 歌曲数据与UI更新 --- (保持与 Step 6 相同)

    def set_song_data(self, song_data):
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
        self.current_phrase_start_time_ms = -1
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

            self.update_phrase_display()
        else:
            self.lyrics_label.setText("...")
            self.feedback_area.setText(f"音频文件未找到: {audio_path}\n请返回选择其他歌曲或检查文件")
            print(f"错误: 音频文件未找到或路径无效: {audio_path}")
            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False)

    def update_phrase_display(self):
        phrases = self.current_song_data.get('phrases', [])
        if not self.current_song_data or self.current_phrase_index >= len(phrases):
            self.lyrics_label.setText("歌曲结束或无歌词")
            self.lyrics_label.setStyleSheet(self._default_lyrics_style)
            self._set_control_buttons_enabled(False)
            self.next_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.feedback_area.setText("歌曲已结束！你真棒！")
            return

        phrase_data = phrases[self.current_phrase_index]
        self.lyrics_label.setText(phrase_data.get('text', '...'))
        self.lyrics_label.setStyleSheet(self._default_lyrics_style)

        self.feedback_area.setText(f"当前乐句 {self.current_phrase_index + 1} / {len(phrases)}\n请听一听 或 我来唱")

        if self.input_device_index is not None and self.audio is not None:
             self.record_button.setEnabled(True)
        else:
             self.record_button.setEnabled(False)

        self.next_button.setEnabled(True)

    # --- 播放相关方法 --- (保持与 Step 6 相同，positionChanged 用于停止和高亮)

    def play_current_phrase(self):
        if self.is_recording:
             self.toggle_recording()

        if not self.media_player.source() or self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.InvalidMedia:
             print("音频未加载或无效，无法播放")
             QMessageBox.warning(self, "播放失败", "歌曲音频加载失败，请检查文件。")
             return

        phrases = self.current_song_data.get('phrases', [])
        if self.current_song_data and self.current_phrase_index < len(phrases):
            phrase_data = phrases[self.current_phrase_index]
            self.current_phrase_start_time_ms = int(phrase_data.get('start_time', 0) * 1000)
            duration_ms = self.media_player.duration()
            default_end_time_ms = duration_ms if duration_ms > 0 else 10000
            self.current_phrase_end_time_ms = int(phrase_data.get('end_time', default_end_time_ms / 1000.0) * 1000)

            if self.current_phrase_end_time_ms < self.current_phrase_start_time_ms:
                 self.current_phrase_end_time_ms = self.current_phrase_start_time_ms + 2000

            if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                self.media_player.stop()

            self.media_player.setPosition(self.current_phrase_start_time_ms)
            self.media_player.play()
            print(f"开始播放乐句 {self.current_phrase_index + 1} 从 {self.current_phrase_start_time_ms}ms 到 {self.current_phrase_end_time_ms}ms")

            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False)
            self.back_button.setEnabled(False)

            # Playback starts, highlight lyrics
            self.lyrics_label.setStyleSheet(self._highlight_lyrics_style)


    def goto_next_phrase(self):
        if self.is_recording:
             self.toggle_recording()
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
             self.media_player.stop()

        # Stop playback/recording, unhighlight lyrics
        self.lyrics_label.setStyleSheet(self._default_lyrics_style)
        self.current_phrase_start_time_ms = -1
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
            print("已是最后一句话，歌曲完成！")
            self.current_phrase_index += 1
            self.update_phrase_display()
            self._set_control_buttons_enabled(False)
            self.next_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.back_button.setEnabled(True)
            # TODO: Trigger song completion logic

    # --- 录音相关方法 --- (保持与 Step 5 修复版 v3/v4 相同)

    def toggle_recording(self):
        if self.input_device_index is None or self.audio is None:
            QMessageBox.warning(self, "录音失败", "未找到可用的麦克风设备或音频系统未初始化。")
            return

        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.is_recording:
            return

        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()

        # Recording starts, unhighlight lyrics
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
            # Use hardcoded red style for recording button for clarity
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
            self._record_start_time = None

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
        self.feedback_area.setText("录音完成！正在分析...") # Update text for analysis

        # **新增：录音停止后，进行音频分析和反馈**
        self.analyze_and_provide_feedback(self.frames)

    def _read_audio_stream(self):
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
        self.listen_button.setEnabled(enabled)
        self.next_button.setEnabled(enabled)


    # --- 新增音频分析和反馈方法 ---

    def analyze_and_provide_feedback(self, audio_frames):
        """分析录制的音频帧并提供反馈"""
        if not audio_frames:
            self.feedback_area.setText("没有录到声音，再试一次？")
            print("没有录到音频数据，跳过分析。")
            return

        # 将音频数据帧转换为 NumPy 数组
        # audio_frames 是一个 bytes 对象的列表，需要拼接并转换为数值数组
        try:
            # Concatenate all bytes objects
            audio_data_bytes = b''.join(audio_frames)
            # Convert bytes to numpy array of int16
            # Adjust dtype based on FORMAT (pyaudio.paInt16 corresponds to np.int16)
            audio_data_np = np.frombuffer(audio_data_bytes, dtype=np.int16)

            # 计算声音能量 (RMS - Root Mean Square)
            # RMS = sqrt(mean(square(samples)))
            # Avoid division by zero if audio_data_np is empty (shouldn't happen if audio_frames is not empty, but safety check)
            if audio_data_np.size > 0:
                rms_energy = np.sqrt(np.mean(np.square(audio_data_np)))
            else:
                rms_energy = 0
            # For int16 data, max value is 32767. Normalize for easier thresholding if needed.
            # rms_energy_normalized = rms_energy / 32767.0

            print(f"录音音频 RMS 能量: {rms_energy}")

            # 根据能量值提供简单反馈 (这些阈值可能需要根据实际麦克风输入调整)
            feedback_message = "分析完成。"
            if rms_energy < 50: # 阈值1：非常安静
                feedback_message = "声音有点小哦，要不要再大声一点试试呀？"
            elif rms_energy < 500: # 阈值2：声音偏小
                 feedback_message = "你唱歌啦！声音再洪亮一点会更好听哦！"
            elif rms_energy < 5000: # 阈值3：正常音量
                 feedback_message = "你的声音很好听！唱得很棒！"
            else: # 阈值4：声音响亮
                 feedback_message = "哇！你的声音真洪亮！太有活力了！"

            # TODO: 可以在这里添加更复杂的分析，比如音高、节奏初步判断，以及结合角色的反馈

            self.feedback_area.setText(feedback_message) # 显示反馈信息

        except Exception as e:
            print(f"音频分析失败: {e}")
            self.feedback_area.setText("分析声音时遇到问题...")


    # --- 播放相关槽函数 --- (保持与 Step 6 相同，positionChanged 用于停止和高亮)

    def _on_playback_state_changed(self, state):
        print(f"播放状态变化: {state}")
        if state == QMediaPlayer.PlaybackState.StoppedState:
             print("播放已停止")
             self.lyrics_label.setStyleSheet(self._default_lyrics_style)
             self.current_phrase_start_time_ms = -1
             self.current_phrase_end_time_ms = -1

             if not self.is_recording:
                self._set_control_buttons_enabled(True)
                if self.input_device_index is not None and self.audio is not None:
                     self.record_button.setEnabled(True)
                else:
                     self.record_button.setEnabled(False)
                self.back_button.setEnabled(True)


    def _on_position_changed(self, position):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and self.current_phrase_end_time_ms != -1:
             if position >= self.current_phrase_end_time_ms:
                 self.media_player.stop()
                 print(f"在 {position}ms 停止播放，超过乐句结束时间 {self.current_phrase_end_time_ms}ms")


    def _on_media_error(self, error, error_string):
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
        "id": "test_song_analyze",
        "title": "测试音频分析歌曲",
        "audio_full": test_audio_path,
        "audio_karaoke": None,
        "lyrics": "测试分析功能",
        "phrases": [
          {"text": "测试分析功能", "start_time": 0.0, "end_time": 3.0}
        ],
        "unlocked": True
    }

    if not os.path.exists(test_song_data["audio_full"]):
         print(f"Test audio {test_song_data['audio_full']} not found. Playback will not work.")
         test_song_data["audio_full"] = None

    learning_widget = LearningWidget()
    learning_widget.set_song_data(test_song_data)
    learning_widget.show()

    sys.exit(app.exec())