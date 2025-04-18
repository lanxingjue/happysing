import os
import sys
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QSizePolicy, QMessageBox, QApplication, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QTimer, QByteArray, QBuffer, QTime
from PyQt6.QtGui import QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices, QMediaFormat

import pyaudio
import numpy as np
import librosa
import scipy.signal
# **新增导入：导入 librosa.onset 模块**
from librosa import onset # Or import librosa.onset


# Define audio parameters (保持不变)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS_MAX = 15

# Define parameters for librosa analysis (保持不变，这些也用于 Onset 检测)
LIBROSA_FRAME_LENGTH = 2048
LIBROSA_HOP_LENGTH = 512

# Define base path for assets (保持不变)
ASSETS_BASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'assets')

class LearningWidget(QWidget):
    back_to_select = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- 音频播放器 --- (保持不变)
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

        # --- 音频录制器 --- (保持不变)
        self.audio = None
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.input_device_index = None

        try:
            self.audio = pyaudio.PyAudio()
            default_input_device_info = self.audio.get_default_input_device_info()
            self.input_device_index = default_input_device_info.get('index')
            print(f"找到默认音频输入设备: {default_input_device_info.get('name')} (Index: {self.input_device_index})")
        except Exception as e:
            print(f"警告: 未找到默认音频输入设备或列举设备时发生错误: {e}")
            print("录音功能可能无法使用。请检查麦克风设置。")

        self._record_timer = QTimer(self)
        self._record_timer.timeout.connect(self._read_audio_stream)
        self._record_start_time = None

        # --- 音频分析器 --- (保持不变)
        # No specific initialization needed for librosa pitch/onset detection here


        # --- 歌曲数据和进度 --- (保持不变)
        self.current_song_data = None
        self.current_phrase_index = 0
        self.current_phrase_start_time_ms = -1
        self.current_phrase_end_time_ms = -1

        # --- 游戏化元素 --- (保持不变)
        self.total_stars = 0
        self.star_label = QLabel("⭐ 0")
        self.star_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFD700;")

        self._character_pixmaps = {}
        self._current_theme = None

        # --- UI 布局 --- (保持不变)
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        self.song_title_label = QLabel("请选择歌曲")
        self.song_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.song_title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #333;")

        # 1. 顶部区域：歌曲标题和星星
        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        top_layout.addStretch()
        top_layout.addWidget(self.song_title_label)
        top_layout.addStretch()
        top_layout.addWidget(self.star_label)
        main_layout.addLayout(top_layout)

        # 2. 歌词显示区
        self.lyrics_label = QLabel("...")
        self.lyrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyrics_label.setWordWrap(True)
        self._default_lyrics_style = "font-size: 22px; color: #555; min-height: 80px; border: 1px solid #ddd; padding: 10px; background-color: #f8f8f8; border-radius: 8px;"
        self._highlight_lyrics_style = "font-size: 24px; color: #007BFF; font-weight: bold; min-height: 80px; border: 2px solid #007BFF; padding: 10px; background-color: #e0f2ff; border-radius: 8px;"
        self.lyrics_label.setStyleSheet(self._default_lyrics_style)
        self.lyrics_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(self.lyrics_label)

        # 3. 角色/反馈展示区
        self.feedback_widget = QWidget()
        self.feedback_layout = QHBoxLayout(self.feedback_widget)
        self.feedback_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_layout.setSpacing(20)

        self.character_image_label = QLabel()
        self.character_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.character_image_label.setFixedSize(150, 150)
        self.character_image_label.setScaledContents(True)
        self.feedback_layout.addWidget(self.character_image_label)

        self.feedback_text_label = QLabel("准备开始...")
        self.feedback_text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.feedback_text_label.setWordWrap(True)
        self.feedback_text_label.setStyleSheet("font-size: 18px; color: #333;")
        self.feedback_layout.addWidget(self.feedback_text_label)

        main_layout.addWidget(self.feedback_widget)


        # 4. 控制按钮区
        control_layout = QHBoxLayout()
        control_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.listen_button = QPushButton("听一听 (Listen)")
        self.record_button = QPushButton("我来唱 (Record)")
        self.next_button = QPushButton("下一句 (Next)")

        self.button_style = """
            QPushButton {
                font-size: 16px;
                padding: 10px 20px;
                border-radius: 8px;
                background-color: #FF9800; /* Orange */
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
                background-color: #9E9E9E; /* Gray */
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
        # Check PyAudio initialization for enabling record button
        if self.input_device_index is None or self.audio is None:
             self.record_button.setEnabled(False)

        self.update_star_display()


    # --- 歌曲数据与UI更新 --- (保持不变)

    def set_song_data(self, song_data):
        """设置当前学习歌曲的完整数据"""
        self.current_song_data = song_data
        if not song_data:
            self.song_title_label.setText("加载歌曲失败")
            self.lyrics_label.setText("...")
            self.feedback_text_label.setText("请返回重新选择歌曲")
            self.character_image_label.clear()
            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False)
            return

        self.song_title_label.setText(f"歌曲：{song_data.get('title', '未知歌曲')}")
        self.feedback_text_label.setText("准备开始...")
        self.current_phrase_index = 0
        self.current_phrase_start_time_ms = -1
        self.current_phrase_end_time_ms = -1

        theme = song_data.get('theme')
        if theme and theme != self._current_theme:
             self._load_character_images(theme)
             self._current_theme = theme
        elif not theme:
             self._character_pixmaps = {}
             self._current_theme = None

        self.character_image_label.clear()


        audio_path = song_data.get('audio_full')
        if audio_path and os.path.exists(audio_path):
            media_content = QUrl.fromLocalFile(os.path.abspath(audio_path))
            self.media_player.setSource(media_content)
            print(f"尝试加载音频: {os.path.abspath(audio_path)}")
            # Check PyAudio initialization for enabling record button
            if self.input_device_index is not None and self.audio is not None:
                self._set_control_buttons_enabled(True)
                self.record_button.setEnabled(True)
            else:
                 # Can't record but can listen
                 self._set_control_buttons_enabled(True)
                 self.record_button.setEnabled(False)
                 if self.input_device_index is None:
                      self.feedback_text_label.setText("未找到麦克风，只能听歌哦！")
                 elif self.audio is None:
                      self.feedback_text_label.setText("音频系统初始化失败，只能听歌哦！")


            self.update_phrase_display()
        else:
            self.lyrics_label.setText("...")
            self.feedback_text_label.setText(f"音频文件未找到: {audio_path}\n请返回选择其他歌曲或检查文件")
            self.character_image_label.clear()
            print(f"错误: 音频文件未找到或路径无效: {audio_path}")
            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False)

    def _load_character_images(self, theme):
        self._character_pixmaps = {}
        theme_image_dir = os.path.join(ASSETS_BASE_PATH, 'images', theme)
        if os.path.isdir(theme_image_dir):
             print(f"加载主题 '{theme}' 的角色图片...")
             character_files = {
                 'pawpatrol': ['chase.png', 'marshall.png', 'skye.png'],
                 # Add other themes here: 'rabrador': ['rabrador_char1.png', ...]
             }
             characters_to_load = character_files.get(theme, [])

             for char_file in characters_to_load:
                 char_name = os.path.splitext(char_file)[0]
                 image_path = os.path.join(theme_image_dir, char_file)
                 if os.path.exists(image_path):
                     try:
                         pixmap = QPixmap(image_path)
                         if not pixmap.isNull():
                              self._character_pixmaps[char_name] = pixmap
                              print(f"  - 加载 {char_file}成功 ({char_name})")
                         else:
                              print(f"  - 加载 {char_file} 失败 (文件可能损坏)")
                     except Exception as e:
                         print(f"  - 加载 {char_file} 时发生错误: {e}")
                 else:
                     print(f"  - 角色图片文件未找到: {image_path}")
        else:
            print(f"警告: 未找到主题 '{theme}' 的图片目录: {theme_image_dir}")
            self.character_image_label.clear()


    def update_phrase_display(self):
        # ... (修改录音按钮启用逻辑)
        phrases = self.current_song_data.get('phrases', [])
        if not self.current_song_data or self.current_phrase_index >= len(phrases):
            self.lyrics_label.setText("歌曲结束或无歌词")
            self.lyrics_label.setStyleSheet(self._default_lyrics_style)
            self._set_control_buttons_enabled(False)
            self.next_button.setEnabled(False)
            self.record_button.setEnabled(False)
            self.feedback_text_label.setText("歌曲已结束！你真棒！")
            self.character_image_label.clear()
            return

        phrase_data = phrases[self.current_phrase_index]
        self.lyrics_label.setText(phrase_data.get('text', '...'))
        self.lyrics_label.setStyleSheet(self._default_lyrics_style)

        self.feedback_text_label.setText(f"当前乐句 {self.current_phrase_index + 1} / {len(phrases)}\n请听一听 或 我来唱")
        self.character_image_label.clear()

        # Check PyAudio initialization for enabling record button
        if self.input_device_index is not None and self.audio is not None:
             self.record_button.setEnabled(True)
        else:
             self.record_button.setEnabled(False)

        self.next_button.setEnabled(True)

    def update_star_display(self):
        """更新星星数量的显示"""
        self.star_label.setText(f"⭐ {self.total_stars}")


    # --- 播放相关方法 --- (保持不变)

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

            self.lyrics_label.setStyleSheet(self._highlight_lyrics_style)

            self.feedback_text_label.setText("正在播放...")
            self.character_image_label.clear()


    def goto_next_phrase(self):
        # ... (修改录音按钮启用逻辑)
        if self.is_recording:
             self.toggle_recording()
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
             self.media_player.stop()

        self.lyrics_label.setStyleSheet(self._default_lyrics_style)
        self.current_phrase_start_time_ms = -1
        self.current_phrase_end_time_ms = -1
        self.feedback_text_label.setText("...")
        self.character_image_label.clear()


        phrases = self.current_song_data.get('phrases', [])
        if self.current_song_data and self.current_phrase_index < len(phrases) - 1:
            self.current_phrase_index += 1
            self.update_phrase_display()
            self._set_control_buttons_enabled(True)
            # Check PyAudio initialization for enabling record button
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


    # --- 录音相关方法 --- (修改 start_recording, stop_recording 中的录音按钮启用逻辑)

    def toggle_recording(self):
        # Check PyAudio initialization
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

        self.lyrics_label.setStyleSheet(self._default_lyrics_style)
        self.feedback_text_label.setText("正在录音...")
        self.character_image_label.clear()

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

            self._record_start_time = None

            self._record_timer.start(int(CHUNK / RATE * 1000))
            print("开始录音...")

        except Exception as e:
            self.is_recording = False
            self.record_button.setText("我来唱 (Record)")
            self.record_button.setStyleSheet(self.button_style)
            self._set_control_buttons_enabled(True)
            # Check PyAudio initialization
            if self.input_device_index is not None and self.audio is not None:
                 self.record_button.setEnabled(True)
            else:
                 self.record_button.setEnabled(False)
            self.back_button.setEnabled(True)
            self.feedback_text_label.setText("录音失败，请检查麦克风设置。")
            self.character_image_label.clear()
            print(f"录音启动失败: {e}")
            QMessageBox.critical(self, "录音失败", f"无法启动录音设备：{e}\n请检查麦克风连接和权限设置。")
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

    def stop_recording(self):
        if not self.is_recording:
            return

        self._record_timer.stop()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        self.is_recording = False
        self.record_button.setText("我来唱 (Record)")
        self.record_button.setStyleSheet(self.button_style)

        self._set_control_buttons_enabled(True)
        # Check PyAudio initialization
        if self.input_device_index is not None and self.audio is not None:
             self.record_button.setEnabled(True)
        else:
             self.record_button.setEnabled(False)
        self.back_button.setEnabled(True)

        print(f"停止录音。共录制 {len(self.frames)} 块音频数据。")
        self.feedback_text_label.setText("录音完成！正在分析...")
        self.character_image_label.clear()

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


    # --- 修改音频分析和反馈方法 --- (新增节奏分析并更新反馈逻辑)

    def analyze_and_provide_feedback(self, audio_frames):
        """分析录制的音频帧 (能量, 音高, 节奏) 并提供反馈 (结合角色图片)"""
        if not audio_frames:
            self.feedback_text_label.setText("没有录到声音，再试一次？")
            self.character_image_label.clear()
            print("没有录到音频数据，跳过分析。")
            return

        try:
            audio_data_bytes = b''.join(audio_frames)
            audio_data_np_int16 = np.frombuffer(audio_data_bytes, dtype=np.int16)
            audio_data_np_float32 = audio_data_np_int16.astype(np.float32) / 32768.0


            # --- 音量分析 (RMS) --- (保持不变)
            rms_energy = 0
            if audio_data_np_float32.size > 0:
                rms_energy = np.sqrt(np.mean(np.square(audio_data_np_float32)))
            print(f"录音音频 RMS 能量 (float32): {rms_energy}")


            # --- 音高分析 (使用 librosa) --- (保持不变)
            try:
                 f0, voiced_flag, voiced_probabilities = librosa.pyin(
                     y=audio_data_np_float32,
                     fmin=librosa.note_to_hz('C2'),
                     fmax=librosa.note_to_hz('C6'),
                     sr=RATE,
                     frame_length=LIBROSA_FRAME_LENGTH,
                     hop_length=LIBROSA_HOP_LENGTH
                 )
                 voiced_frames_count = np.sum(voiced_flag)
                 total_frames = len(voiced_flag)
                 pitch_detected_percentage = (voiced_frames_count / total_frames) * 100 if total_frames > 0 else 0
                 has_discernible_pitch = pitch_detected_percentage > 20 # Example threshold

                 print(f"Voiced frames percentage: {pitch_detected_percentage:.2f}%")

            except Exception as e:
                print(f"Librosa pitch analysis failed: {e}")
                has_discernible_pitch = False # Assume no pitch detected on failure


            # --- 节奏分析 (使用 librosa.onset) --- (新增)
            try:
                 # Detect onsets. The onset envelope is first computed, then peak picking.
                 # hop_length should be smaller than frame_length for onset detection.
                 # We can use a standard onset detection method like 'hfc' (High Frequency Content).
                 # The result `onsets` is an array of frame indices where onsets were detected.
                 onset_frames = onset.onset_detect(y=audio_data_np_float32, sr=RATE,
                                                   hop_length=LIBROSA_HOP_LENGTH,
                                                   # Optional: increase peak_perc to detect stronger onsets
                                                   # peak_perc=50,
                                                   # Optional: adjust pre_avg/post_avg for smoothing onset strength curve
                                                   # pre_avg=3, post_avg=3
                                                   )

                 num_onsets = len(onset_frames)
                 print(f"检测到 {num_onsets} 个声音起始点 (Onsets)")

                 # Simple check: is a reasonable number of onsets detected for the phrase duration?
                 # The expected number of onsets depends on the song's rhythm and child's singing speed.
                 # For a rough check, let's say more than N onsets indicates some attempt at rhythm.
                 # N could be 2 or 3 for a short phrase.
                 rhythm_onset_threshold = 2 # Example threshold: need at least 2 onsets
                 has_discernible_rhythm = num_onsets >= rhythm_onset_threshold


            except Exception as e:
                print(f"Librosa onset analysis failed: {e}")
                has_discernible_rhythm = False # Assume no rhythm detected on failure


            # --- 综合反馈逻辑 --- (结合能量, 音高, 和节奏)
            feedback_message = "分析完成。"
            selected_character_name = None

            # RMS thresholds for float32 data (adjust based on testing)
            rms_quiet_threshold = 0.001
            rms_medium_threshold = 0.01
            rms_loud_threshold = 0.1

            # Determine overall performance category
            is_loud_enough = rms_energy > rms_medium_threshold
            is_pitched = has_discernible_pitch
            is_rhythmic = has_discernible_rhythm # Based on simple onset count

            if rms_energy < rms_quiet_threshold * 0.5: # Very quiet, likely no sound
                 feedback_message = "没有听到你的声音哦，再靠近麦克风一点试试？"
                 selected_character_name = 'chase' # Needs encouragement
            elif not is_loud_enough: # Some sound, but quiet
                if is_pitched and is_rhythmic:
                     feedback_message = "你唱得很棒！声音小小的也很动听呢！"
                     selected_character_name = 'skye' # Gentle singer
                elif is_pitched:
                     feedback_message = "声音小小的，但是有音调哦！再大声一点试试看？"
                     selected_character_name = 'chase' # Encourage volume
                elif is_rhythmic:
                     feedback_message = "声音小小的，但跟着节奏点发声啦！很棒！"
                     selected_character_name = 'marshall' # Acknowledge rhythm attempt
                else: # Quiet, no clear pitch or rhythm
                     feedback_message = "你发声啦！很棒的尝试！声音再大一点就更清楚了！"
                     selected_character_name = 'chase' # General encouragement
            elif is_loud_enough: # Good volume
                 if is_pitched and is_rhythmic:
                      feedback_message = "太棒了！你唱得又响亮、又有音调、还有节奏感！真是一位小歌星！"
                      selected_character_name = 'marshall' # Full marks!
                 elif is_pitched:
                      feedback_message = "声音响亮，旋律也很棒！再试试跟着歌曲的节奏一起唱？"
                      selected_character_name = 'skye' # Good pitch/volume, encourage rhythm
                 elif is_rhythmic:
                      feedback_message = "声音响亮，而且发声很有节奏感！再试试唱出歌曲的旋律？"
                      selected_character_name = 'marshall' # Good rhythm/volume, encourage pitch
                 else: # Loud, but no clear pitch or rhythm (maybe shouting, talking, sustained note without pitch detection)
                      feedback_message = "声音好洪亮！很棒的尝试！唱歌的时候，试着发出有长短、有高低的声音哦！"
                      selected_character_name = 'marshall' # Acknowledge volume, guide towards singing

            # Display character image
            if selected_character_name and selected_character_name in self._character_pixmaps:
                 self.character_image_label.setPixmap(self._character_pixmaps[selected_character_name].scaled(self.character_image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                 self.character_image_label.clear()

            # Display feedback message
            self.feedback_text_label.setText(feedback_message)

        except Exception as e:
            print(f"音频分析失败: {e}")
            self.feedback_text_label.setText("分析声音时遇到问题...")
            self.character_image_label.clear()
            # Fallback to just volume analysis if anything goes wrong in the main analysis block
            self._analyze_volume_only_feedback(audio_frames)


    def _analyze_volume_only_feedback(self, audio_frames):
        """Fallback analysis if pitch or rhythm detection fails"""
        print("Using fallback volume analysis.")
        if not audio_frames:
             self.feedback_text_label.setText("没有录到声音，再试一次？")
             self.character_image_label.clear()
             print("No audio data for fallback analysis.")
             return

        try:
            audio_data_bytes = b''.join(audio_frames)
            audio_data_np_int16 = np.frombuffer(audio_data_bytes, dtype=np.int16)

            rms_energy = 0
            if audio_data_np_int16.size > 0:
                 rms_energy = np.sqrt(np.mean(np.square(audio_data_np_int16)))

            print(f"录音音频 RMS 能量 (int16, fallback): {rms_energy}")

            # Original volume feedback thresholds from Step 7 (adjust as needed)
            if rms_energy < 50:
                feedback_message = "声音有点小哦，要不要再大声一点试试呀？"
                selected_character_name = 'chase'
            elif rms_energy < 500:
                 feedback_message = "你唱歌啦！声音再洪亮一点会更好听哦！"
                 selected_character_name = 'chase'
            elif rms_energy < 5000:
                 feedback_message = "你的声音很好听！唱得很棒！"
                 selected_character_name = 'skye'
            else:
                 feedback_message = "哇！你的声音真洪亮！太有活力了！"
                 selected_character_name = 'marshall'

            if selected_character_name and selected_character_name in self._character_pixmaps:
                 self.character_image_label.setPixmap(self._character_pixmaps[selected_character_name].scaled(self.character_image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                 self.character_image_label.clear()

            self.feedback_text_label.setText(feedback_message)

        except Exception as e:
            print(f"fallback volume analysis failed: {e}")
            self.feedback_text_label.setText("分析声音时遇到问题...")
            self.character_image_label.clear()


    # --- 播放相关槽函数 --- (保持不变)

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
         self.feedback_text_label.setText(f"音频播放错误: {error_string}")
         self.character_image_label.clear()
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
    from PIL import Image # Import PIL for creating dummy images

    app = QApplication(sys.argv)

    # Simulate song data (ensure the audio file and images exist)
    test_audio_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'audio', 'pawpatrol_full.wav')
    test_song_data = {
        "id": "test_song_rhythm",
        "title": "测试节奏分析歌曲",
        "theme": "pawpatrol", # Specify theme
        "audio_full": test_audio_path,
        "audio_karaoke": None,
        "lyrics": "测试节奏分析功能",
        "phrases": [
          {"text": "测试节奏分析功能", "start_time": 0.0, "end_time": 5.0} # Use a longer time for testing
        ],
        "unlocked": True
    }

    if not os.path.exists(test_song_data["audio_full"]):
         print(f"Test audio {test_song_data['audio_full']} not found. Playback will not work.")
         test_song_data["audio_full"] = None

    # Ensure test character images exist for the theme
    test_theme_image_dir = os.path.join(ASSETS_BASE_PATH, 'images', test_song_data['theme'])
    required_images = ['chase.png', 'marshall.png', 'skye.png']
    images_found = all(os.path.isfile(os.path.join(test_theme_image_dir, f)) for f in required_images)

    if not os.path.isdir(test_theme_image_dir) or not images_found:
         print(f"Warning: Required test character images for theme '{test_song_data['theme']}' not found in {test_theme_image_dir}. Character images won't display correctly.")
         # Create dummy files if missing to avoid QPixmap errors
         if not os.path.isdir(test_theme_image_dir):
             os.makedirs(test_theme_image_dir, exist_ok=True)
         for img_name in required_images:
             dummy_path = os.path.join(test_theme_image_dir, img_name)
             if not os.path.exists(dummy_path):
                 try:
                    dummy_img = Image.new('RGB', (100, 100), color = 'red') # Create slightly larger dummy
                    dummy_img.save(dummy_path)
                    print(f"Created dummy image: {dummy_path}")
                 except ImportError:
                    print(f"Pillow not installed, cannot create dummy image {dummy_path}. QPixmap might fail.")
                    with open(dummy_path, 'w') as f:
                         pass


    learning_widget = LearningWidget()
    learning_widget.set_song_data(test_song_data)
    learning_widget.show()

    sys.exit(app.exec())