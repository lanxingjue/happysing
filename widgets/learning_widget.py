# -*- coding: utf-8 -*-

import os
import sys
import json
# 导入 PyQt6 相关的模块
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QSizePolicy, QMessageBox, QApplication, QFrame, QGraphicsOpacityEffect) # 导入 QGraphicsOpacityEffect 用于动画

from PyQt6.QtCore import (Qt, pyqtSignal, QUrl, QTimer, QByteArray, QBuffer, QTime,
                          QPropertyAnimation, QPoint, QSequentialAnimationGroup, QParallelAnimationGroup,
                          QEasingCurve) # <-- 在这里或者在其他导入 QtCore 的地方确保 QEasingCurve 被导入
from PyQt6.QtGui import QPixmap, QMovie # 导入 QPixmap 用于静态图片, QMovie 用于 GIF 动画
# 导入音频播放和设备相关的模块
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices # <--- 确保这一行存在且正确
# 导入音频处理相关的库
import pyaudio
import numpy as np
import librosa # 用于音频特征分析
import scipy.signal # 可能在一些音频处理中用到，librosa 也依赖它
from librosa import onset # 用于节奏（发声起始点）检测

# 定义音频参数 (保持不变)
FORMAT = pyaudio.paInt16 # 录音格式 (16-bit integer)
CHANNELS = 1 # 声道数 (单声道)
RATE = 16000 # 采样率 (Hz)
CHUNK = 1024 # 每次读取的音频帧数
RECORD_SECONDS_MAX = 15 # 最大录音时长 (秒)

# 定义 librosa 分析参数 (保持不变)
LIBROSA_FRAME_LENGTH = 2048 # 分析窗口长度
LIBROSA_HOP_LENGTH = 512 # 窗口之间的跳跃长度

# 定义资源文件基础路径 (相对于当前脚本文件)
ASSETS_BASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'assets')

# 定义视觉指示器图标路径
ICONS_PATH = os.path.join(ASSETS_BASE_PATH, 'images', 'icons')
STAR_ICON_PATH = os.path.join(ICONS_PATH, 'star.png') # 星星图标路径

# 定义星星奖励数量 (根据表现计算)
STAR_REWARDS = {
    "excellent": 3, # 表现优秀 (响亮、有音高、有节奏)
    "good": 2,      # 表现良好 (至少满足两项指标)
    "ok": 1,        # 表现一般 (至少满足一项可听见的指标)
    "poor": 0       # 表现不佳 (非常安静或没有可听见的指标)
}

class LearningWidget(QWidget):
    """
    学习歌曲界面的主控件

    负责显示歌曲信息、歌词、音频播放、录音、音频分析、反馈展示和星星动画。
    """
    # 定义信号，用于与主窗口通信
    back_to_select = pyqtSignal() # 返回歌曲选择界面的信号
    stars_earned = pyqtSignal(int) # 获得星星时发出的信号 (参数为本次获得的星星数量)
    song_completed = pyqtSignal(str) # 歌曲完成时发出的信号 (参数为歌曲 ID)

    def __init__(self, parent=None):
        """
        构造函数，初始化学习界面的 UI 和各种组件。
        """
        super().__init__(parent)

        # 设置对象名称，用于 QSS 样式表
        self.setObjectName("LearningWidget")

        # --- 音频播放器 ---
        self.media_player = QMediaPlayer() # 创建媒体播放器
        output_device = QMediaDevices.defaultAudioOutput() # 获取默认音频输出设备
        if not output_device:
             print("警告: 未找到默认音频输出设备!")
             self.audio_output = None
        else:
             self.audio_output = QAudioOutput(output_device) # 创建音频输出
             self.media_player.setAudioOutput(self.audio_output) # 将音频输出连接到播放器

        # 连接播放器信号到槽函数
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed) # 播放状态变化信号
        self.media_player.errorOccurred.connect(self._on_media_error) # 播放错误信号
        self.media_player.positionChanged.connect(self._on_position_changed) # 播放位置变化信号

        # --- 音频录制器 ---
        self.audio = None # PyAudio 实例
        self.stream = None # 录音流
        self.frames = [] # 存储录制的音频帧
        self.is_recording = False # 录音状态标志
        self.input_device_index = None # 默认输入设备索引

        try:
            self.audio = pyaudio.PyAudio() # 初始化 PyAudio
            default_input_device_info = self.audio.get_default_input_device_info() # 获取默认输入设备信息
            self.input_device_index = default_input_device_info.get('index') # 获取设备索引
            print(f"找到默认音频输入设备: {default_input_device_info.get('name')} (Index: {self.input_device_index})")
        except Exception as e:
            print(f"警告: 未找到默认音频输入设备或列举设备时发生错误: {e}")
            print("录音功能可能无法使用。请检查麦克风设置。")

        # 录音定时器，用于周期性读取音频流
        self._record_timer = QTimer(self)
        self._record_timer.timeout.connect(self._read_audio_stream)
        self._record_start_time = None # 录音开始时间戳


        # --- 歌曲数据和进度 ---
        self.current_song_data = None # 当前歌曲数据字典
        self.current_phrase_index = 0 # 当前乐句索引
        self.current_phrase_start_time_ms = -1 # 当前乐句开始时间 (毫秒)
        self.current_phrase_end_time_ms = -1 # 当前乐句结束时间 (毫秒)
        self._phrase_stars = [] # 列表，存储当前歌曲中每个乐句获得的星星


        # --- 游戏化元素 ---
        self.total_stars = 0 # 用户总星星数 (由主窗口更新并显示)
        self.star_label = QLabel("⭐ 0") # 显示总星星数的标签
        self.star_label.setObjectName("starLabel") # 设置对象名称用于 QSS
        # 标签样式由 QSS 控制

        # 角色动画相关
        self._character_movies = {} # 字典，存储加载的角色 QMovie 对象 (键为角色名)
        self._current_character_movie = None # 当前正在播放的 QMovie
        self._current_theme = None # 当前歌曲的主题

        # 用于星星动画的列表
        self._animated_star_labels = [] # 存储正在动画中的星星标签


        # --- UI 布局 ---
        # 创建主布局 (垂直布局)
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter) # 顶部居中对齐
        self._main_layout.setContentsMargins(20, 20, 20, 20) # 外边距
        self._main_layout.setSpacing(15) # 控件间距


        # 1. 顶部区域：歌曲标题和星星 (水平布局)
        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop) # 顶部水平居中对齐
        top_layout.addStretch() # 添加弹性空间，将标题和星星推向两边
        # 歌曲标题标签
        self.song_title_label = QLabel("请选择歌曲")
        self.song_title_label.setObjectName("songTitleLabel") # 设置对象名称用于 QSS
        self.song_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # 文本居中对齐
        # 标题样式由 QSS 控制
        top_layout.addWidget(self.song_title_label)
        top_layout.addStretch() # 添加弹性空间
        top_layout.addWidget(self.star_label) # 添加星星标签
        self._main_layout.addLayout(top_layout) # 将顶部布局添加到主布局


        # 2. 歌词显示区 (标签)
        self.lyrics_label = QLabel("...")
        self.lyrics_label.setObjectName("lyricsLabel") # 设置对象名称用于 QSS
        self.lyrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # 文本居中对齐
        self.lyrics_label.setWordWrap(True) # 启用自动换行
        # 歌词样式由 QSS 控制，高亮状态通过动态属性控制
        self.lyrics_label.setProperty("highlight", False) # 动态属性，用于 QSS 识别是否高亮
        self.lyrics_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed) # 宽度扩展，高度固定
        self._main_layout.addWidget(self.lyrics_label) # 将歌词标签添加到主布局


        # 3. 角色/反馈展示区 (容器控件，内部使用水平布局)
        self.feedback_widget = QWidget()
        self.feedback_widget.setObjectName("feedbackWidget") # 设置对象名称用于 QSS
        # 使用水平布局来放置角色图片和反馈文字/指示器
        feedback_main_layout = QHBoxLayout(self.feedback_widget)
        feedback_main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # 水平居中对齐
        feedback_main_layout.setContentsMargins(0, 0, 0, 0) # 移除容器的默认边距
        feedback_main_layout.setSpacing(20) # 控件间距


        # 左侧：角色图片标签
        self.character_image_label = QLabel()
        self.character_image_label.setObjectName("characterImageLabel") # 设置对象名称用于 QSS
        self.character_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # 图片居中对齐
        self.character_image_label.setFixedSize(180, 180) # 固定角色图片显示区域大小
        self.character_image_label.setScaledContents(True) # 允许图片/动画缩放填充标签
        feedback_main_layout.addWidget(self.character_image_label) # 将角色图片标签添加到反馈主布局


        # 右侧：反馈文字和指示器 (使用垂直布局)
        feedback_text_indicators_layout = QVBoxLayout()
        feedback_text_indicators_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft) # 垂直居中，水平靠左对齐
        feedback_text_indicators_layout.setContentsMargins(0, 0, 0, 0) # 移除布局边距
        feedback_text_indicators_layout.setSpacing(10) # 文字与指示器之间的间距


        # 反馈文字标签
        self.feedback_text_label = QLabel("准备开始...")
        self.feedback_text_label.setObjectName("feedbackTextLabel") # 设置对象名称用于 QSS
        self.feedback_text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) # 文本靠左垂直居中对齐
        self.feedback_text_label.setWordWrap(True) # 启用自动换行
        # 标签样式由 QSS 控制
        feedback_text_indicators_layout.addWidget(self.feedback_text_label) # 将反馈文字标签添加到右侧布局


        # 视觉指示器区域 (水平布局)
        self.indicators_layout = QHBoxLayout()
        self.indicators_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) # 靠左垂直居中对齐
        self.indicators_layout.setSpacing(15) # 指示器之间的间距

        # 创建指示器标签并设置对象名称、固定大小和缩放
        indicator_size = 40 # 指示器图标大小
        self.volume_indicator = QLabel()
        self.volume_indicator.setObjectName("volumeIndicator")
        self.volume_indicator.setFixedSize(indicator_size, indicator_size)
        self.volume_indicator.setScaledContents(True) # 允许缩放图标

        self.pitch_indicator = QLabel()
        self.pitch_indicator.setObjectName("pitchIndicator")
        self.pitch_indicator.setFixedSize(indicator_size, indicator_size)
        self.pitch_indicator.setScaledContents(True)

        self.rhythm_indicator = QLabel()
        self.rhythm_indicator.setObjectName("rhythmIndicator")
        self.rhythm_indicator.setFixedSize(indicator_size, indicator_size)
        self.rhythm_indicator.setScaledContents(True)

        # 将指示器标签添加到指示器布局
        self.indicators_layout.addWidget(self.volume_indicator)
        self.indicators_layout.addWidget(self.pitch_indicator)
        self.indicators_layout.addWidget(self.rhythm_indicator)
        self.indicators_layout.addStretch() # 添加弹性空间，将指示器推向左边

        feedback_text_indicators_layout.addLayout(self.indicators_layout) # 将指示器布局添加到右侧垂直布局


        feedback_main_layout.addLayout(feedback_text_indicators_layout) # 将右侧布局添加到反馈主水平布局

        self._main_layout.addWidget(self.feedback_widget) # 将反馈容器控件添加到主布局


        # 4. 控制按钮区 (水平布局)
        control_layout = QHBoxLayout()
        control_layout.setAlignment(Qt.AlignmentFlag.AlignCenter) # 水平居中对齐

        # 创建控制按钮并设置对象名称
        self.listen_button = QPushButton("听一听 (Listen)")
        self.listen_button.setObjectName("listenButton")

        self.record_button = QPushButton("我来唱 (Record)")
        self.record_button.setObjectName("recordButton")
        # 设置录音状态的动态属性，用于 QSS 识别
        self.record_button.setProperty("recording", False)

        self.next_button = QPushButton("下一句 (Next)")
        self.next_button.setObjectName("nextButton")

        # 按钮样式由 QSS 控制

        # 将按钮添加到控制布局
        control_layout.addWidget(self.listen_button)
        control_layout.addWidget(self.record_button)
        control_layout.addWidget(self.next_button)

        self._main_layout.addLayout(control_layout) # 将控制布局添加到主布局


        # 5. 返回按钮 (水平布局，靠右对齐)
        self.back_button = QPushButton("返回选择歌曲")
        self.back_button.setObjectName("backButton") # 设置对象名称
        # 按钮样式由 QSS 控制
        self.back_button.clicked.connect(self.back_to_select.emit) # 连接信号
        self.back_button.setFixedSize(150, 40) # 固定大小
        back_button_layout = QHBoxLayout()
        back_button_layout.addStretch() # 添加弹性空间，将按钮推向右边
        back_button_layout.addWidget(self.back_button) # 添加返回按钮
        self._main_layout.addLayout(back_button_layout) # 将返回按钮布局添加到主布局


        # self.setLayout(main_layout) # 这行不需要，因为在初始化 _main_layout 时已经设置了父对象 self

        # --- 连接按钮信号到槽函数 --- (保持不变)
        self.listen_button.clicked.connect(self.play_current_phrase)
        self.record_button.clicked.connect(self.toggle_recording)
        self.next_button.clicked.connect(self.goto_next_phrase)

        # 初始化状态
        self._set_control_buttons_enabled(False) # 默认禁用控制按钮
        # 如果没有麦克风设备，禁用录音按钮
        if self.input_device_index is None or self.audio is None:
             self.record_button.setEnabled(False)

        # 加载指示器图标
        self._load_indicator_icons() # 在 UI 元素创建后加载图标

        self.update_star_display() # 更新星星显示
        self._update_indicator_ui(False, False, False) # 确保指示器初始状态为关闭


    # --- 新增方法：加载指示器图标 ---
    def _load_indicator_icons(self):
        """从文件加载视觉指示器图标和星星图标。"""
        self._indicator_icons = {
            "volume_on": QPixmap(os.path.join(ICONS_PATH, 'volume_on.png')),
            "volume_off": QPixmap(os.path.join(ICONS_PATH, 'volume_off.png')),
            "pitch_on": QPixmap(os.path.join(ICONS_PATH, 'pitch_on.png')),
            "pitch_off": QPixmap(os.path.join(ICONS_PATH, 'pitch_off.png')),
            "rhythm_on": QPixmap(os.path.join(ICONS_PATH, 'rhythm_on.png')),
            "rhythm_off": QPixmap(os.path.join(ICONS_PATH, 'rhythm_off.png')),
            "star": QPixmap(STAR_ICON_PATH) # 加载星星图标
        }
        # 检查图标是否成功加载，如果失败则打印警告
        for name, pixmap in self._indicator_icons.items():
             if pixmap.isNull():
                  # 构造可能的原始文件名以提供更清晰的警告
                  filename = name.replace('_on', '').replace('_off', '') + ('.png' if 'star' not in name else '.png') # 假设都是 png
                  print(f"警告: 指示器图标 '{name}' 未找到或加载失败。请检查路径: {os.path.join(ICONS_PATH, filename)}")


    # --- 新增方法：更新指示器 UI ---
    def _update_indicator_ui(self, vol_on, pitch_on, rhythm_on):
        """根据传入的布尔值更新音量、音高、节奏指示器的显示状态（图标）。"""
        # 获取当前指示器标签的大小，用于缩放图标
        icon_size = self.volume_indicator.size()

        # 检查图标是否已加载且有效，然后设置相应的图标并缩放
        if self._indicator_icons.get("volume_on") and self._indicator_icons.get("volume_off") and not self._indicator_icons["volume_on"].isNull():
             icon = self._indicator_icons["volume_on"] if vol_on else self._indicator_icons["volume_off"]
             self.volume_indicator.setPixmap(icon.scaled(icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
             self.volume_indicator.clear() # 如果图标未加载或无效，则清空标签

        if self._indicator_icons.get("pitch_on") and self._indicator_icons.get("pitch_off") and not self._indicator_icons["pitch_on"].isNull():
             icon = self._indicator_icons["pitch_on"] if pitch_on else self._indicator_icons["pitch_off"]
             self.pitch_indicator.setPixmap(icon.scaled(icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
             self.pitch_indicator.clear() # 如果图标未加载或无效，则清空标签

        if self._indicator_icons.get("rhythm_on") and self._indicator_icons.get("rhythm_off") and not self._indicator_icons["rhythm_on"].isNull():
             icon = self._indicator_icons["rhythm_on"] if rhythm_on else self._indicator_icons["rhythm_off"]
             self.rhythm_indicator.setPixmap(icon.scaled(icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
             self.rhythm_indicator.clear() # 如果图标未加载或无效，则清空标签


    # --- 歌曲数据与UI更新 ---
    def set_song_data(self, song_data):
        """
        设置当前学习歌曲的完整数据，并初始化界面。

        参数:
            song_data (dict): 包含歌曲信息的字典。
        """
        self.current_song_data = song_data
        if not song_data:
            # 处理歌曲数据无效的情况
            self.song_title_label.setText("加载歌曲失败")
            self.lyrics_label.setText("...")
            self.feedback_text_label.setText("请返回重新选择歌曲")
            self.character_image_label.clear()
            # 停止并清除当前角色动画
            self._stop_current_movie()

            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False)
            # 清除背景图片样式，恢复默认或全局样式
            self.setStyleSheet("")
            self.setObjectName("LearningWidget") # 恢复对象名称用于 QSS
            self._update_indicator_ui(False, False, False) # 重置指示器
            return

        # 设置歌曲标题
        self.song_title_label.setText(f"歌曲：{song_data.get('title', '未知歌曲')}")
        # 初始化反馈文本和乐句索引
        self.feedback_text_label.setText("准备开始...")
        self.current_phrase_index = 0
        self.current_phrase_start_time_ms = -1
        self.current_phrase_end_time_ms = -1
        # 初始化乐句星星列表，每个乐句的星星数设为 0
        self._phrase_stars = [0] * len(song_data.get('phrases', []))

        # --- 加载背景图片样式 ---
        background_image_path = song_data.get('background_image')
        if background_image_path:
            full_bg_path = os.path.abspath(background_image_path)
            # 使用 QUrl.fromLocalFile 将本地文件路径转换为 URL 格式，确保在 QSS 中正确引用
            bg_url = QUrl.fromLocalFile(full_bg_path).toString()
            # 构建 QSS 样式字符串
            stylesheet_string = f"""
                #LearningWidget {{
                    background-image: url("{bg_url}");
                    background-position: center;
                    background-repeat: no-repeat;
                    background-size: cover; /* 尝试覆盖整个控件区域 */
                }}
                /* 这里只设置背景样式，其他控件样式依赖全局 QSS */
            """
            # 设置控件的样式表
            self.setStyleSheet(stylesheet_string)

            if not os.path.exists(full_bg_path):
                 print(f"警告: 背景图片文件未找到: {full_bg_path}")
                 # 如果背景图未找到，QSS 会忽略 background-image，显示默认背景色。
                 pass
            else:
                 print(f"设置背景图片: {full_bg_path}")

        else:
            # 如果歌曲未指定背景图，则清空背景样式，恢复默认或全局样式
            self.setStyleSheet("")
            self.setObjectName("LearningWidget") # 恢复对象名称

        # --- 加载角色 QMovie (GIF 动画) ---
        theme = song_data.get('theme')
        character_image_map = song_data.get('character_images', {}) # 从歌曲数据中获取角色图片映射
        if theme and character_image_map:
             self._load_character_movies(theme, character_image_map) # 加载角色动画
             self._current_theme = theme
        else:
             self._character_movies = {} # 清空角色动画字典
             self._current_theme = None
             print(f"警告: 歌曲 '{song_data.get('title', '未知')}' 没有指定主题或角色图片映射。")

        # 停止并清除当前可能显示的角色动画
        self._stop_current_movie()

        # 加载歌曲音频文件
        audio_path = song_data.get('audio_full')
        if audio_path and os.path.exists(audio_path):
            # 设置媒体播放器的音频源
            media_content = QUrl.fromLocalFile(os.path.abspath(audio_path))
            self.media_player.setSource(media_content)
            print(f"尝试加载音频: {os.path.abspath(audio_path)}")
            # 如果找到麦克风和音频系统正常，启用控制按钮，否则禁用录音
            if self.input_device_index is not None and self.audio is not None:
                self._set_control_buttons_enabled(True)
                self.record_button.setEnabled(True)
            else:
                 self._set_control_buttons_enabled(True)
                 self.record_button.setEnabled(False)
                 # 提供不能录音的反馈
                 if self.input_device_index is None:
                      self.feedback_text_label.setText("未找到麦克风，只能听歌哦！")
                 elif self.audio is None:
                      self.feedback_text_label.setText("音频系统初始化失败，只能听歌哦！")

            # 更新显示第一个乐句
            self.update_phrase_display()
        else:
            # 处理音频文件未找到的情况
            self.lyrics_label.setText("...")
            self.feedback_text_label.setText(f"音频文件未找到: {audio_path}\n请返回选择其他歌曲或检查文件")
            self._stop_current_movie() # 停止并清除角色动画
            print(f"错误: 音频文件未找到或路径无效: {audio_path}")
            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False)

        # 重置指示器状态
        self._update_indicator_ui(False, False, False)


    # --- 新增方法：加载角色 QMovie ---
    def _load_character_movies(self, theme, character_image_map):
        """
        根据主题和映射加载角色 GIF/图片文件为 QMovie 对象。

        参数:
            theme (str): 歌曲主题名称。
            character_image_map (dict): 角色名到文件名的映射字典。
                                        例如: {"chase": "chase.gif", "marshall": "marshall.gif"}
        """
        self._character_movies = {} # 清空之前的角色动画
        # 构造主题图片目录的完整路径
        theme_image_dir = os.path.join(ASSETS_BASE_PATH, 'images', theme)

        if not os.path.isdir(theme_image_dir):
             print(f"警告: 未找到主题 '{theme}' 的图片目录: {theme_image_dir}")
             return

        print(f"加载主题 '{theme}' 的角色图片...")

        # 遍历映射字典，加载每个角色的动画
        for char_name, char_file in character_image_map.items():
            # 构造角色文件的完整路径
            image_path = os.path.join(theme_image_dir, char_file)

            if os.path.exists(image_path):
                try:
                    movie = QMovie(image_path) # 创建 QMovie 对象
                    # 设置动画的缩放尺寸，使其与标签大小匹配
                    movie.setScaledSize(self.character_image_label.size())
                    if movie.isValid(): # 检查 QMovie 是否有效
                         self._character_movies[char_name] = movie # 存储到字典
                         print(f"  - 加载 {char_file}成功 ({char_name})")
                    else:
                         print(f"  - 加载 {char_file} 失败 (文件可能损坏或格式不支持)")
                except Exception as e:
                    print(f"  - 加载 {char_file} 时发生错误: {e}")
            else:
                print(f"  - 角色图片文件未找到: {image_path}")


    # --- 新增方法：停止当前角色动画并清空 ---
    def _stop_current_movie(self):
        """停止当前播放的角色动画并从标签中移除。"""
        if self._current_character_movie:
             self._current_character_movie.stop()
             self.character_image_label.setMovie(None)
             self._current_character_movie = None
             # print("已停止并清空当前角色动画。")


    def update_phrase_display(self):
        """更新歌词和界面状态以显示当前乐句。"""
        phrases = self.current_song_data.get('phrases', [])
        # 检查是否还有乐句需要显示
        if not self.current_song_data or self.current_phrase_index >= len(phrases):
            # 如果没有更多乐句，表示歌曲结束
            self.lyrics_label.setText("歌曲结束或无歌词")
            # 移除歌词高亮动态属性
            self.lyrics_label.setProperty("highlight", False)
            self.lyrics_label.style().polish(self.lyrics_label) # 刷新样式

            # 禁用控制按钮，只保留返回按钮可用（由 _set_control_buttons_enabled 控制）
            self._set_control_buttons_enabled(False)
            self.next_button.setEnabled(False)
            self.record_button.setEnabled(False)

            # 设置歌曲结束反馈文本
            self.feedback_text_label.setText("歌曲已结束！你真棒！")
            # 停止并清除角色动画和指示器
            self._stop_current_movie()
            self._update_indicator_ui(False, False, False)

            # 检查歌曲完成情况并触发信号
            self._check_song_completion()

            return

        # 如果还有乐句，显示当前乐句的文本
        phrase_data = phrases[self.current_phrase_index]
        self.lyrics_label.setText(phrase_data.get('text', '...'))
        # 移除歌词高亮动态属性 (在播放或录音开始时再设置)
        self.lyrics_label.setProperty("highlight", False)
        self.lyrics_label.style().polish(self.lyrics_label) # 刷新样式

        # 更新反馈文本提示用户操作
        self.feedback_text_label.setText(f"当前乐句 {self.current_phrase_index + 1} / {len(phrases)}\n请听一听 或 我来唱")
        # 停止并清除角色动画和指示器
        self._stop_current_movie()
        self._update_indicator_ui(False, False, False)

        # 根据麦克风可用性启用或禁用录音按钮
        if self.input_device_index is not None and self.audio is not None:
             self.record_button.setEnabled(True)
        else:
             self.record_button.setEnabled(False)

        # 启用下一句按钮
        self.next_button.setEnabled(True)


    # --- 新增方法：检查歌曲是否完成并触发信号 ---
    def _check_song_completion(self):
        """检查是否所有乐句都已完成，如果是，则触发歌曲完成逻辑和信号。"""
        phrases = self.current_song_data.get('phrases', [])
        # 当当前乐句索引达到或超过总乐句数时，认为歌曲完成
        if self.current_phrase_index >= len(phrases) and self.current_song_data:
             print(f"歌曲 '{self.current_song_data.get('title', '未知歌曲')}' 完成！")

             # 计算本轮歌曲尝试获得的星星总数
             stars_earned_in_song = sum(self._phrase_stars)
             print(f"本轮歌曲共获得星星：{stars_earned_in_song}")

             # 触发 song_completed 信号，通知主窗口处理歌曲完成逻辑（例如解锁新歌）
             self.song_completed.emit(self.current_song_data.get('id'))

             # 更新反馈文本显示歌曲完成和本轮获得的星星总数
             # 注意：这里显示的是整首歌的星星总数，而不是乐句星星
             self.feedback_text_label.setText(f"歌曲'{self.current_song_data.get('title', '未知歌曲')}'完成！\n你真棒，本轮共获得 ⭐ {stars_earned_in_song} 颗星星！")
             # TODO: 可以在这里添加一个歌曲完成的特别动画或图片

             # 确保在歌曲完成时，指示器重置
             self._update_indicator_ui(False, False, False)

             # 停止并清除当前可能显示的角色动画
             self._stop_current_movie()


    # 这个方法由主窗口调用，用于更新界面上显示的总星星数
    def set_total_stars_display(self, total_stars):
         """更新界面上显示的用户总星星数。"""
         self.total_stars = total_stars
         self.update_star_display() # 调用方法更新标签文本


    def update_star_display(self):
        """更新显示总星星数量的标签文本。"""
        self.star_label.setText(f"⭐ {self.total_stars}")


    # --- 播放相关方法 ---
    def play_current_phrase(self):
        """播放当前乐句的音频片段。"""
        # 如果正在录音，先停止录音
        if self.is_recording:
             self.toggle_recording()

        # 检查媒体播放器是否已加载有效的音频源
        if not self.media_player.source() or self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.InvalidMedia:
             print("音频未加载或无效，无法播放")
             QMessageBox.warning(self, "播放失败", "歌曲音频加载失败，请检查文件。")
             return

        phrases = self.current_song_data.get('phrases', [])
        # 检查当前乐句索引是否有效
        if self.current_song_data and self.current_phrase_index < len(phrases):
            phrase_data = phrases[self.current_phrase_index]
            # 获取乐句的开始和结束时间 (转换为毫秒)
            self.current_phrase_start_time_ms = int(phrase_data.get('start_time', 0) * 1000)
            duration_ms = self.media_player.duration() # 获取整个音频的总时长
            default_end_time_ms = duration_ms if duration_ms > 0 else 10000 # 如果总时长未知，设一个默认值
            self.current_phrase_end_time_ms = int(phrase_data.get('end_time', default_end_time_ms / 1000.0) * 1000)

            # 确保结束时间不早于开始时间，并至少有一定时长
            if self.current_phrase_end_time_ms < self.current_phrase_start_time_ms:
                 self.current_phrase_end_time_ms = self.current_phrase_start_time_ms + 2000 # 确保至少 2 秒时长

            # 确保乐句时间在整个音频时长范围内 (如果总时长已知)
            if duration_ms > 0:
                 self.current_phrase_start_time_ms = min(self.current_phrase_start_time_ms, duration_ms)
                 self.current_phrase_end_time_ms = min(self.current_phrase_end_time_ms, duration_ms)


            # 如果播放器当前不是停止状态，先停止播放
            if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
                self.media_player.stop()

            # 设置播放位置到乐句开始时间，并开始播放
            self.media_player.setPosition(self.current_phrase_start_time_ms)
            self.media_player.play()
            print(f"开始播放乐句 {self.current_phrase_index + 1} 从 {self.current_phrase_start_time_ms}ms 到 {self.current_phrase_end_time_ms}ms")

            # 播放期间禁用控制按钮和返回按钮，防止干扰
            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(False) # 录音按钮在播放期间也不能按
            self.back_button.setEnabled(False)

            # 设置歌词高亮的动态属性，触发 QSS 样式变化
            self.lyrics_label.setProperty("highlight", True)
            self.lyrics_label.style().polish(self.lyrics_label) # 刷新样式以立即应用变化

            # 更新反馈文本和清空角色动画/指示器
            self.feedback_text_label.setText("正在播放...")
            self._stop_current_movie()
            self._update_indicator_ui(False, False, False)


    def goto_next_phrase(self):
        """前进到下一乐句。"""
        # 当点击下一句按钮时，如果当前正在录音，则停止录音并触发分析反馈
        if self.is_recording:
             self.toggle_recording() # 这会停止录音并触发分析反馈

        # 如果播放器当前不是停止状态，先停止播放
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
             self.media_player.stop()

        # 移除歌词高亮的动态属性，恢复默认样式
        self.lyrics_label.setProperty("highlight", False)
        self.lyrics_label.style().polish(self.lyrics_label) # 刷新样式

        # 重置乐句时间
        self.current_phrase_start_time_ms = -1
        self.current_phrase_end_time_ms = -1
        # 清空反馈文本和角色动画/指示器
        self.feedback_text_label.setText("...")
        self._stop_current_movie()
        self._update_indicator_ui(False, False, False)


        phrases = self.current_song_data.get('phrases', [])
        # 检查是否还有下一乐句
        if self.current_song_data and self.current_phrase_index < len(phrases):
             self.current_phrase_index += 1 # 乐句索引加一
             self.update_phrase_display() # 更新界面显示下一乐句
             # 按钮状态在 update_phrase_display 和 _on_playback_state_changed 中处理
             print(f"前进到下一句乐句，索引：{self.current_phrase_index}")


    # --- 录音相关方法 ---
    def toggle_recording(self):
        """切换录音状态 (开始/停止)。"""
        # 检查麦克风是否可用
        if self.input_device_index is None or self.audio is None:
            QMessageBox.warning(self, "录音失败", "未找到可用的麦克风设备或音频系统未初始化。")
            return

        if self.is_recording:
            self.stop_recording() # 如果正在录音，则停止录音
        else:
            # 如果当前乐句已经获得过星星，提示用户重新录音会覆盖得分 (可选)
            if self.current_song_data and self.current_phrase_index < len(self.current_song_data.get('phrases', [])):
                 if self._phrase_stars[self.current_phrase_index] > 0:
                      print(f"当前乐句 {self.current_phrase_index + 1} 已获得星星 ({self._phrase_stars[self.current_phrase_index]})，再次录音将覆盖得分。")
                      # TODO: 可在此处添加一个确认对话框，询问用户是否确定重新录音
                      pass # 暂时跳过确认，直接开始录音

            self.start_recording() # 如果没有录音，则开始录音

    def start_recording(self):
        """开始音频录制。"""
        if self.is_recording: # 防止重复开始
            return

        # 如果媒体播放器正在播放，先停止
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()

        # 移除歌词高亮动态属性
        self.lyrics_label.setProperty("highlight", False)
        self.lyrics_label.style().polish(self.lyrics_label) # 刷新样式

        # 更新反馈文本提示录音状态
        self.feedback_text_label.setText("正在录音...")
        # 停止并清除角色动画和指示器
        self._stop_current_movie()
        self._update_indicator_ui(False, False, False)

        self.frames = [] # 清空之前录制的音频帧
        try:
            # 打开音频输入流
            self.stream = self.audio.open(format=FORMAT,
                                         channels=CHANNELS,
                                         rate=RATE,
                                         input=True,
                                         frames_per_buffer=CHUNK,
                                         input_device_index=self.input_device_index)

            self.is_recording = True # 设置录音状态标志
            self.record_button.setText("停止录音 (Stop)") # 更新按钮文本
            # 设置录音中的动态属性，触发 QSS 样式变化
            self.record_button.setProperty("recording", True)
            self.record_button.style().polish(self.record_button) # 刷新样式

            # 禁用除录音按钮以外的控制按钮和返回按钮
            self._set_control_buttons_enabled(False)
            self.record_button.setEnabled(True) # 录音按钮本身是启用的，用于停止
            self.back_button.setEnabled(False)

            self._record_start_time = None # 重置录音开始时间

            # 启动定时器，定期读取音频流
            self._record_timer.start(int(CHUNK / RATE * 1000))
            print("开始录音...")

        except Exception as e:
            # 处理录音启动失败的情况
            self.is_recording = False
            self.record_button.setText("我来唱 (Record)")
            # 移除录音状态的动态属性
            self.record_button.setProperty("recording", False)
            self.record_button.style().polish(self.record_button) # 刷新样式

            # 恢复控制按钮和返回按钮状态
            self._set_control_buttons_enabled(True)
            if self.input_device_index is not None and self.audio is not None:
                 self.record_button.setEnabled(True)
            else:
                 self.record_button.setEnabled(False)
            self.back_button.setEnabled(True)
            # 更新反馈文本提示错误
            self.feedback_text_label.setText("录音失败，请检查麦克风设置。")
            # 停止并清除角色动画和指示器
            self._stop_current_movie()
            self._update_indicator_ui(False, False, False)

            print(f"录音启动失败: {e}")
            QMessageBox.critical(self, "录音失败", f"无法启动录音设备：{e}\n请检查麦克风连接和权限设置。")
            # 清理音频流资源
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

    def stop_recording(self):
        """停止音频录制并触发分析。"""
        if not self.is_recording: # 防止重复停止
            return

        self._record_timer.stop() # 停止定时器
        # 清理音频流资源
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        self.is_recording = False # 更新录音状态标志
        self.record_button.setText("我来唱 (Record)") # 恢复按钮文本
        # 移除录音状态的动态属性
        self.record_button.setProperty("recording", False)
        self.record_button.style().polish(self.record_button) # 刷新样式

        # 恢复控制按钮和返回按钮状态
        self._set_control_buttons_enabled(True)
        if self.input_device_index is not None and self.audio is not None:
             self.record_button.setEnabled(True)
        else:
             self.record_button.setEnabled(False)
        self.back_button.setEnabled(True)

        print(f"停止录音。共录制 {len(self.frames)} 块音频数据。")
        # 更新反馈文本提示正在分析
        self.feedback_text_label.setText("录音完成！正在分析...")
        # 停止并清除角色动画和指示器 (分析后 _display_feedback 会更新)
        self._stop_current_movie()
        self._update_indicator_ui(False, False, False)


        # 重置当前乐句获得的星星，准备重新评分
        if self.current_song_data and self.current_phrase_index < len(self.current_song_data.get('phrases', [])):
             self._phrase_stars[self.current_phrase_index] = 0


        # 触发音频分析和反馈流程
        self.analyze_and_provide_feedback(self.frames)

    def _read_audio_stream(self):
        """定时器调用的槽函数，读取音频流数据。"""
        if not self.is_recording or self.stream is None:
            return

        try:
            # 从流中读取音频数据
            data = self.stream.read(CHUNK, exception_on_overflow=False) # exception_on_overflow=False 防止溢出时抛异常
            self.frames.append(data) # 将读取的数据块添加到帧列表

            # 检查是否达到最大录音时长
            recorded_duration = len(self.frames) * CHUNK / RATE
            if recorded_duration >= RECORD_SECONDS_MAX:
                 print(f"达到最大录音时长 ({RECORD_SECONDS_MAX}s)，自动停止录音。")
                 self.stop_recording() # 达到最大时长则自动停止录音

        except IOError as e:
             # 忽略一些常见的 IOError，尤其在流结束时
             pass
        except Exception as e:
            print(f"读取音频流时发生未知错误: {e}")
            self.stop_recording() # 发生未知错误则停止录音


    def _set_control_buttons_enabled(self, enabled):
        """启用或禁用听一听和下一句按钮。"""
        self.listen_button.setEnabled(enabled)
        self.next_button.setEnabled(enabled)


    # --- 音频分析和反馈方法 ---
    def analyze_and_provide_feedback(self, audio_frames):
        """
        分析录制的音频帧（能量、音高、节奏）并提供反馈。

        根据分析结果计算星星数量，选择角色动画，更新指示器，并显示反馈文本。
        """
        if not audio_frames:
            # 如果没有录到音频数据
            feedback_message = "哎呀，好像没有听到声音，再靠近麦克风一点试试，或者大声一点唱？你发出声音就很棒！"
            selected_character_name = 'chase' # 鼓励尝试的角色
            stars_earned_for_phrase = STAR_REWARDS["poor"] # 0 星

            # 调用 _display_feedback 更新界面
            self._display_feedback(feedback_message, selected_character_name, stars_earned_for_phrase, False, False, False)
            print("没有录到音频数据，跳过分析。")
            # 触发 0 星信号，以便主窗口保存这次尝试
            if self.current_song_data and self.current_phrase_index < len(self.current_song_data.get('phrases', [])):
                 self._phrase_stars[self.current_phrase_index] = stars_earned_for_phrase
                 self.stars_earned.emit(stars_earned_for_phrase)
            return

        try:
            # 将音频帧合并并转换为 numpy 数组 (int16 -> float32)
            audio_data_bytes = b''.join(audio_frames)
            audio_data_np_int16 = np.frombuffer(audio_data_bytes, dtype=np.int16)
            audio_data_np_float32 = audio_data_np_int16.astype(np.float32) / 32768.0 # 归一化到 [-1.0, 1.0]


            # --- 音量分析 (RMS 能量) ---
            rms_energy = 0
            if audio_data_np_float32.size > 0:
                rms_energy = np.sqrt(np.mean(np.square(audio_data_np_float32)))
            print(f"录音音频 RMS 能量 (float32): {rms_energy}")

            # 音量阈值 (根据 float32 数据调整)
            rms_quiet_threshold = 0.005 # 能听见的声音阈值
            rms_medium_threshold = 0.03 # 足够响亮的声音阈值
            rms_loud_threshold = 0.15   # 非常响亮的声音阈值

            is_audible = rms_energy > rms_quiet_threshold # 是否能听见
            is_loud_enough = rms_energy > rms_medium_threshold # 是否足够响亮
            is_very_loud = rms_energy > rms_loud_threshold # 是否非常响亮


            # --- 音高分析 (使用 librosa) ---
            has_discernible_pitch = False # 是否检测到明显的音高
            pitch_detected_percentage = 0 # 检测到音高的帧数百分比
            if is_audible: # 只在声音可听见时尝试检测音高
                 try:
                      f0, voiced_flag, voiced_probabilities = librosa.pyin(
                          y=audio_data_np_float32,
                          fmin=librosa.note_to_hz('C2'), # 最小检测频率 (低音 C)
                          fmax=librosa.note_to_hz('C6'), # 最大检测频率 (高音 C)
                          sr=RATE, # 采样率
                          frame_length=LIBROSA_FRAME_LENGTH, # 分析窗口长度
                          hop_length=LIBROSA_HOP_LENGTH # 窗口跳跃长度
                      )
                      voiced_frames_count = np.sum(voiced_flag) # 统计检测到音高的帧数
                      total_frames = len(voiced_flag) # 总帧数
                      pitch_detected_percentage = (voiced_frames_count / total_frames) * 100 if total_frames > 0 else 0 # 计算百分比
                      # 设定阈值：例如，需要在至少 30% 的帧中检测到音高才算有明显的音高
                      has_discernible_pitch = pitch_detected_percentage > 30

                      print(f"Voiced frames percentage: {pitch_detected_percentage:.2f}%")

                 except Exception as e:
                     print(f"Librosa pitch analysis failed (after audible check): {e}")
                     has_discernible_pitch = False # 分析失败则认为没有音高


            # --- 节奏分析 (使用 librosa.onset) ---
            has_discernible_rhythm = False # 是否检测到明显的节奏
            num_onsets = 0 # 检测到的发声起始点数量
            if is_audible: # 只在声音可听见时尝试检测节奏
                 try:
                      # 检测声音起始点 (onset)，单位为帧
                      onset_frames = onset.onset_detect(y=audio_data_np_float32, sr=RATE,
                                                        hop_length=LIBROSA_HOP_LENGTH,
                                                        units='frames') # 获取帧索引

                      num_onsets = len(onset_frames) # 统计发声起始点数量
                      print(f"检测到 {num_onsets} 个声音起始点 (Onsets)")

                      # 简单检查：对于录音时长，是否检测到合理数量的发声点？
                      # 根据录音时长和典型发声速率（例如每秒 0.8 个发声点）估算所需最小发声点数量
                      recorded_duration_sec = len(audio_frames) * CHUNK / RATE # 录音时长（秒）
                      min_onsets_required = max(1, int(recorded_duration_sec * 0.8)) # 至少需要 1 个发声点（如果时长 > ~1.25s）

                      # 如果检测到的发声点数量达到或超过最小需求，认为有节奏感
                      has_discernible_rhythm = num_onsets >= min_onsets_required
                      print(f"Recorded duration: {recorded_duration_sec:.2f}s, Min onsets required: {min_onsets_required}, Detected onsets: {num_onsets}, Has rhythm: {has_discernible_rhythm}")

                 except Exception as e:
                     print(f"Librosa onset analysis failed (after audible check): {e}")
                     has_discernible_rhythm = False # 分析失败则认为没有节奏


            # --- 综合反馈逻辑和星星奖励 --- (优化反馈文字和角色选择)
            feedback_message = "你尝试啦！" # 默认基础反馈
            selected_character_name = 'chase' # 默认角色
            stars_earned_for_phrase = 0 # 本乐句获得的星星数初始化为 0

            # 根据分析结果确定表现类别
            if not is_audible:
                 category = "silent"
                 stars_earned_for_phrase = STAR_REWARDS["poor"] # 不可听见 -> 0 星
            elif is_loud_enough and has_discernible_pitch and has_discernible_rhythm:
                 category = "excellent"
                 stars_earned_for_phrase = STAR_REWARDS["excellent"] # 优秀 -> 3 星
            elif (is_loud_enough and has_discernible_pitch) or \
                 (is_loud_enough and has_discernible_rhythm) or \
                 (has_discernible_pitch and has_discernible_rhythm and not is_very_loud): # 良好 (至少满足两项指标，且不非常响亮，避免与 Excellent 重叠)
                 category = "good"
                 stars_earned_for_phrase = STAR_REWARDS["good"] # 良好 -> 2 星
            elif is_audible: # 可听见，但未达到良好的标准 (可能只满足一项或没有满足，但至少能听到声音)
                 category = "ok"
                 stars_earned_for_phrase = STAR_REWARDS["ok"] # 一般 -> 1 星
            else: # 兜底情况 (理论上应被 is_audible 检查覆盖)
                 category = "poor"
                 stars_earned_for_phrase = STAR_REWARDS["poor"] # 0 星


            # 根据表现类别和具体指标选择反馈信息和角色
            if category == "silent":
                 feedback_message = "哎呀，好像没有听到声音，再大声一点试试？我很期待听到你的歌声！"
                 selected_character_name = 'chase' # 鼓励尝试的角色
            elif category == "excellent":
                 feedback_message = "哇！太棒了！你唱得又响亮、又有音调、还有节奏感！你真是一位小歌星！"
                 selected_character_name = 'marshall' # 自信/有活力的角色
            elif category == "good":
                 if is_loud_enough and has_discernible_pitch:
                      feedback_message = "声音响亮，旋律也很棒！你唱得真好听！"
                      selected_character_name = 'skye' # 有音乐感/甜美的角色
                 elif is_loud_enough and has_discernible_rhythm:
                      feedback_message = "声音响亮，而且发声很有节奏感！跟着拍子唱太酷啦！"
                      selected_character_name = 'marshall' # 有活力的角色
                 elif has_discernible_pitch and has_discernible_rhythm: # 可听见，有音高有节奏，但不非常响亮
                      feedback_message = "声音小小的，但唱得很有音调和节奏呢！轻轻地唱也很棒！"
                      selected_character_name = 'skye' # 有音乐感/甜美的角色
                 else: # 兜底情况，理论上不会发生
                      feedback_message = "你唱得很棒！"
                      selected_character_name = 'chase'
            elif category == "ok":
                 # 对于一般表现，提供更具体的鼓励
                 parts = [] # 记录满足了哪些指标
                 if is_very_loud: # 如果声音非常响亮
                      feedback_message = "哇！你的声音真洪亮！太有活力了！"
                      selected_character_name = 'marshall' # 有活力的角色
                 else: # 不非常响亮，检查其他指标
                     if is_loud_enough: # 足够响亮 (但未达到非常响亮)
                          parts.append("声音很响亮")
                     if has_discernible_pitch: # 有音高
                          parts.append("声音很有音调")
                     if has_discernible_rhythm: # 有节奏
                          parts.append("发声很有节奏感")

                     if len(parts) > 0:
                          # 组合反馈，或者使用更简单友好的语句
                          feedback_message = f"你发出声音啦！很棒！我们听到你唱了！" # 基础尝试的反馈
                          # 可选：反馈具体做到的部分：f"你发出声音啦！很棒！{', '.join(parts)}！下次再试试把它们都唱出来？"
                     else: # 可听见，但没有满足响亮/音高/节奏的阈值
                          feedback_message = "你尝试啦，很棒！我听到你发出声音了！再大声、再有音调一点点试试看？"

                     selected_character_name = 'chase' # 鼓励尝试的角色

            else: # category == "poor" (兜底，包括不可听见的情况，不可听见已在开头处理)
                 feedback_message = "你尝试啦，很棒！我们再来一次？"
                 selected_character_name = 'chase' # 鼓励尝试的角色
                 stars_earned_for_phrase = STAR_REWARDS["poor"] # 确保是 0 星

            # 检查选择的角色是否存在对应的 QMovie，如果不存在则使用第一个加载的角色或清空
            if selected_character_name not in self._character_movies:
                 print(f"警告: 角色 '{selected_character_name}' 的 QMovie 未加载，尝试使用第一个可用的角色。")
                 selected_character_name = next(iter(self._character_movies), None) # 获取字典中的第一个键（角色名）
                 if selected_character_name:
                      print(f"  - 使用备选角色: '{selected_character_name}'")
                 else:
                      print("  - 没有可用的角色动画加载。")

            # 调用 _display_feedback 方法更新界面显示反馈、角色动画和指示器，并触发星星动画
            self._display_feedback(feedback_message, selected_character_name, stars_earned_for_phrase, is_audible, has_discernible_pitch, has_discernible_rhythm)


        except Exception as e:
            # 处理音频分析过程中发生的错误
            print(f"音频分析失败: {e}")
            self.feedback_text_label.setText("分析声音时遇到问题...")
            # 停止并清除角色动画和指示器
            self._stop_current_movie()
            self._update_indicator_ui(False, False, False)
            # 触发 0 星信号，表示本次分析失败
            if self.current_song_data and self.current_phrase_index < len(self.current_song_data.get('phrases', [])):
                 self._phrase_stars[self.current_phrase_index] = 0
                 self.stars_earned.emit(0)


    # --- 新增方法：显示反馈 (包含角色动画、指示器和星星动画触发) ---
    def _display_feedback(self, message, character_name, stars_earned, vol_on, pitch_on, rhythm_on):
         """
         更新界面显示反馈信息、角色动画，并更新视觉指示器。

         参数:
             message (str): 要显示的反馈文本。
             character_name (str): 要显示的角色名称。
             stars_earned (int): 本乐句获得的星星数量。
             vol_on (bool): 音量指示器是否点亮。
             pitch_on (bool): 音高指示器是否点亮。
             rhythm_on (bool): 节奏指示器是否点亮。
         """
         # 停止任何之前的角色动画
         self._stop_current_movie()

         # 显示角色动画
         if character_name and character_name in self._character_movies:
              movie = self._character_movies[character_name]
              if movie.isValid(): # 检查动画是否有效
                   self.character_image_label.setMovie(movie) # 将动画设置到标签上
                   movie.start() # 开始播放动画
                   self._current_character_movie = movie # 更新当前播放的动画引用
              else:
                   self.character_image_label.clear() # 如果动画无效，清空标签
                   self._current_character_movie = None

         else:
              self.character_image_label.clear() # 如果没有角色名或角色动画未加载，清空标签
              self._current_character_movie = None


         # 显示反馈文本
         # 根据获得的星星数量构建反馈文本
         # **修改：优化反馈文本，星星数量用文字描述+图标**
         if stars_earned > 0:
              # 显示反馈信息和获得的星星数量
              feedback_with_stars = f"{message}\n\n获得 ⭐ {stars_earned} 颗星星！"
         else:
              # 如果获得 0 星，只显示反馈信息，不显示星星数量
              feedback_with_stars = message

         self.feedback_text_label.setText(feedback_with_stars)

         # 更新视觉指示器状态
         self._update_indicator_ui(vol_on, pitch_on, rhythm_on)

         # **更新当前乐句获得的星星数量**
         # 这个逻辑已经在 analyze_and_provide_feedback 中处理，这里不再重复，但保留注释提醒
         # if self.current_song_data and self.current_phrase_index < len(self.current_song_data.get('phrases', [])):
         #      self._phrase_stars[self.current_phrase_index] = stars_earned
         #      print(f"乐句 {self.current_phrase_index + 1} 获得星星：{stars_earned}")

         # **触发 stars_earned 信号**
         # 信号已经在 analyze_and_provide_feedback 或其错误处理中发出，确保星星数量被传递
         # self.stars_earned.emit(stars_earned) # 确保只发出一次信号

         # **触发星星动画**
         # 确保星星图标已加载且有效
         if stars_earned > 0 and self._indicator_icons.get("star") and not self._indicator_icons["star"].isNull():
              # 添加一个短暂的延迟，让用户先看到反馈和角色，再开始星星动画
              QTimer.singleShot(500, lambda: self._animate_stars(stars_earned))
         elif stars_earned > 0:
              # 如果星星图标未加载但获得了星星，打印警告
              print("警告: 获得了星星但星星图标未加载，无法播放星星动画。")


    # --- 新增方法：星星动画 ---
    def _animate_stars(self, num_stars):
        """
        创建并动画化指定数量的星星图标，使其飞向总星星数标签。

        参数:
            num_stars (int): 要动画化的星星数量。
        """
        # 检查是否需要动画以及星星图标是否可用
        if num_stars <= 0 or self._indicator_icons.get("star") is None or self._indicator_icons["star"].isNull():
             print("跳过星星动画：没有星星或星星图标未加载/无效。")
             return

        star_pixmap = self._indicator_icons["star"] # 获取星星图标
        icon_size = 30 # 动画星星的大小

        # 计算动画的起始位置和结束位置
        try:
             # 起始位置：角色图片标签的中心（相对于 LearningWidget）
             char_label_pos = self.character_image_label.pos()
             char_label_size = self.character_image_label.size()
             # 计算中心点的坐标，并减去图标大小的一半，使图标中心对齐
             start_x = char_label_pos.x() + char_label_size.width() // 2 - icon_size // 2
             start_y = char_label_pos.y() + char_label_size.height() // 2 - icon_size // 2
             start_pos = QPoint(start_x, start_y)

             # 结束位置：总星星数标签的中心（转换为 LearningWidget 的本地坐标）
             # 先获取总星星标签的全局屏幕坐标
             star_label_global_pos = self.star_label.mapToGlobal(QPoint(self.star_label.width() // 2, self.star_label.height() // 2))
             # 将全局坐标转换回 LearningWidget 的本地坐标，并调整图标中心
             end_pos = self.mapFromGlobal(star_label_global_pos) - QPoint(icon_size // 2, icon_size // 2)

             print(f"星星动画: 起始位置 = {start_pos}, 结束位置 = {end_pos}")

        except Exception as e:
             print(f"计算星星动画位置失败: {e}")
             return # 如果位置计算失败，则不执行动画

        animation_duration_ms = 1000 # 每个星星动画持续时间 (毫秒)
        stagger_delay_ms = 150 # 每个星星动画开始的延迟间隔 (毫秒)

        # 使用 QSequentialAnimationGroup 来按顺序播放每个星星的动画
        animation_group = QSequentialAnimationGroup(self)

        for i in range(num_stars):
             # 创建一个临时的 QLabel 来显示动画星星，并作为 LearningWidget 的子控件
             star_label = QLabel(self)
             # 设置窗口标志和属性，使其浮动在顶部并支持透明背景
             star_label.setWindowFlags(Qt.WindowType.SubWindow) # 让它独立绘制，可能在其他控件上方
             star_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) # 如果图标有透明通道，保持透明
             # 设置星星图标并缩放
             star_label.setPixmap(star_pixmap.scaled(icon_size, icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
             star_label.setFixedSize(icon_size, icon_size) # 设置固定大小
             star_label.move(start_pos) # 设置初始位置
             star_label.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose) # 窗口关闭时自动删除标签
             star_label.show() # 显示标签

             # 创建位置动画 (从起始位置到结束位置)
             pos_animation = QPropertyAnimation(star_label, b"pos") # 动画化 'pos' 属性
             pos_animation.setStartValue(start_pos)
             pos_animation.setEndValue(end_pos)
             pos_animation.setDuration(animation_duration_ms) # 设置动画时长
            #  pos_animation.setEasingCurve(Qt.EasingCurve.OutQuad) # 设置缓动函数，让动画结束时慢一些
             pos_animation.setEasingCurve(QEasingCurve.Type.OutQuad) # 设置缓动函数，让动画结束时慢一些
             # 创建透明度动画 (可选，用于淡出效果)
             # 需要先给标签设置 QGraphicsOpacityEffect
             opacity_effect = QGraphicsOpacityEffect(star_label)
             star_label.setGraphicsEffect(opacity_effect) # 设置效果
             opacity_animation = QPropertyAnimation(opacity_effect, b"opacity") # 动画化效果的 'opacity' 属性
             opacity_animation.setStartValue(1.0) # 从完全不透明开始
             opacity_animation.setEndValue(0.0) # 到完全透明结束 (淡出)
             opacity_animation.setDuration(animation_duration_ms // 3) # 动画时长（例如总时长的后三分之一）
             opacity_animation.setStartValue(animation_duration_ms * 2 // 3) # 从总时长的三分之二处开始淡出


             # 将位置动画和透明度动画组合到一个并行动画组，让他们同时播放
             parallel_group = QParallelAnimationGroup()
             parallel_group.addAnimation(pos_animation) # 添加位置动画
             parallel_group.addAnimation(opacity_animation) # 添加透明度动画

             # 将并行动画组添加到顺序动画组
             # 如果不是第一个星星，添加一个延迟
             animation_group.addPause(stagger_delay_ms if i > 0 else 0)
             animation_group.addAnimation(parallel_group) # 添加当前星星的动画组

             # 连接并行动画组的 finished 信号到标签的 deleteLater 槽函数
             # 确保动画播放完毕后标签被删除，释放内存
             parallel_group.finished.connect(star_label.deleteLater)


        # 启动顺序动画组，开始整个星星动画序列
        animation_group.start()

        # 更新 self._animated_star_labels 列表，存储当前正在动画中的星星标签引用，用于窗口关闭时的清理
        # 查找所有 QLabel 子控件，并且应用了 QGraphicsOpacityEffect 的，认为是动画星星
        self._animated_star_labels = [child for child in self.children() if isinstance(child, QLabel) and child.graphicsEffect()]


    # --- 播放相关槽函数 --- (保持不变)
    def _on_playback_state_changed(self, state):
        """媒体播放状态变化时的槽函数。"""
        print(f"播放状态变化: {state}")
        if state == QMediaPlayer.PlaybackState.StoppedState:
             print("播放已停止")
             # 移除歌词高亮动态属性
             self.lyrics_label.setProperty("highlight", False)
             self.lyrics_label.style().polish(self.lyrics_label) # 刷新样式

             self.current_phrase_start_time_ms = -1
             self.current_phrase_end_time_ms = -1

             # 如果不是正在录音，恢复控制按钮和返回按钮状态
             if not self.is_recording:
                self._set_control_buttons_enabled(True)
                # 录音按钮状态取决于麦克风可用性
                if self.input_device_index is not None and self.audio is not None:
                     self.record_button.setEnabled(True)
                else:
                     self.record_button.setEnabled(False)
                self.back_button.setEnabled(True)


    def _on_position_changed(self, position):
        """媒体播放位置变化时的槽函数，用于在乐句结束时停止播放。"""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and self.current_phrase_end_time_ms != -1:
             # 添加一个小的缓冲（例如 50ms），确保播放器在乐句结束前一点点停止，避免突然中断感
             if position >= self.current_phrase_end_time_ms - 50:
                 self.media_player.stop()
                 print(f"在 {position}ms 停止播放，接近乐句结束时间 {self.current_phrase_end_time_ms}ms")


    def _on_media_error(self, error, error_string):
         """媒体播放发生错误时的槽函数。"""
         print(f"媒体播放错误: {error} - {error_string}")
         self.feedback_text_label.setText(f"音频播放错误: {error_string}")
         # 停止并清除角色动画和指示器
         self._stop_current_movie()
         self._update_indicator_ui(False, False, False)

         QMessageBox.critical(self, "音频错误", f"播放音频时发生错误：{error_string}")
         # 禁用控制按钮
         self._set_control_buttons_enabled(False)
         self.record_button.setEnabled(False) # 录音也可能受影响


    def closeEvent(self, event):
        """
        窗口关闭事件处理函数。

        在窗口关闭前停止所有进行中的动画、音频播放和录音，并释放 PyAudio 资源。
        """
        print("LearningWidget 正在关闭...")
        # 在停止音频/录音前，先尝试停止并清理所有动画中的星星标签
        # 避免在清理过程中动画还在运行导致崩溃
        for star_label in self._animated_star_labels:
             if star_label:
                  star_label.deleteLater() # 安排删除
        self._animated_star_labels = [] # 清空列表引用


        # 停止媒体播放器
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.media_player.stop()
        # 停止录音
        if self.is_recording:
            self.stop_recording()

        # 停止并清除当前角色动画
        self._stop_current_movie()


        # 终止 PyAudio 实例，释放音频设备资源
        if hasattr(self, 'audio') and self.audio:
             try:
                self.audio.terminate()
                print("PyAudio 资源已释放")
             except Exception as e:
                print(f"释放 PyAudio 资源时发生错误: {e}")

        # 调用父类的 closeEvent 处理函数
        super().closeEvent(event)
        event.accept() # 接受关闭事件


# If running this file directly for testing
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication
    import os
    # 导入用于创建虚拟资源的库
    from PIL import Image # Pillow 库
    import numpy as np
    import wave # 用于创建虚拟 WAV 文件

    app = QApplication(sys.argv)

    # --- 为测试创建虚拟资源文件（如果不存在）---
    dummy_assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
    dummy_audio_dir = os.path.join(dummy_assets_dir, 'audio')
    dummy_images_dir = os.path.join(dummy_assets_dir, 'images')
    dummy_icons_dir = os.path.join(dummy_images_dir, 'icons')
    dummy_bg_dir = os.path.join(dummy_images_dir, 'backgrounds')
    dummy_pawpatrol_dir = os.path.join(dummy_images_dir, 'pawpatrol')

    # 创建所需的目录
    os.makedirs(dummy_audio_dir, exist_ok=True)
    os.makedirs(dummy_icons_dir, exist_ok=True)
    os.makedirs(dummy_bg_dir, exist_ok=True)
    os.makedirs(dummy_pawpatrol_dir, exist_ok=True)

    # 创建虚拟音频文件 (简单的正弦波 WAV)
    dummy_wav_path = os.path.join(dummy_audio_dir, 'test_song_score_full.wav')
    if not os.path.exists(dummy_wav_path):
         try:
              sample_rate = 16000
              duration = 10 # 秒
              frequency = 440 # Hz (A4 音高)
              t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
              amplitude = np.iinfo(np.int16).max * 0.5 # 最大振幅的一半
              data = amplitude * np.sin(2 * np.pi * frequency * t)
              data_int16 = data.astype(np.int16) # 转换为 16-bit 整数格式

              with wave.open(dummy_wav_path, 'wb') as wf:
                  wf.setnchannels(1) # 单声道
                  wf.setsampwidth(2) # 2 bytes = 16 bits
                  wf.setframerate(sample_rate) # 采样率
                  wf.writeframes(data_int16.tobytes()) # 写入数据
              print(f"已创建虚拟音频文件: {dummy_wav_path}")
         except Exception as e:
              print(f"创建虚拟音频文件失败: {e}")


    # 创建虚拟图片文件 (使用 Pillow 库)
    try:
        # 导入 Pillow 绘图和字体模块
        from PIL import ImageDraw, ImageFont

        def create_dummy_image(path, color, text="", size=(100, 100)):
            """创建一个指定颜色、文本和大小的虚拟 PNG 图片。"""
            if not os.path.exists(path):
                try:
                    img = Image.new('RGB', size, color = color) # 创建 RGB 图像
                    if text:
                         draw = ImageDraw.Draw(img) # 创建绘图对象
                         # 尝试加载字体，如果失败则使用默认字体
                         try:
                              # 尝试加载一个常见的 TrueType 字体，这里假设系统有 arial.ttf
                              font_size = int(size[1] * 0.4) # 根据图片高度计算字体大小
                              font = ImageFont.truetype("arial.ttf", font_size)
                         except IOError:
                              # 如果找不到 arial.ttf，使用 Pillow 的默认字体
                              font = ImageFont.load_default()
                              print("警告: arial.ttf 字体未找到，使用默认字体绘制虚拟图片文本。")
                         except Exception as font_e:
                               print(f"警告: 加载字体失败: {font_e}, 使用默认字体。")
                               font = ImageFont.load_default()


                         # 计算文本绘制位置，使其居中
                         # 使用 textbbox 获取文本边界框，更准确地计算大小
                         try:
                             text_bbox = draw.textbbox((0,0), text, font=font)
                             text_width = text_bbox[2] - text_bbox[0]
                             text_height = text_bbox[3] - text_bbox[1]
                             x = (size[0] - text_width) // 2 - text_bbox[0] # 考虑 textbbox 可能有偏移
                             y = (size[1] - text_height) // 2 - text_bbox[1]
                             draw.text((x, y), text, fill="black", font=font) # 绘制黑色文本
                         except Exception as draw_e:
                             print(f"警告: 绘制虚拟图片文本失败: {draw_e}")
                             # 尝试使用旧的 textsize 方法作为备用 (在较新版本 Pillow 中可能移除)
                             try:
                                text_width, text_height = draw.textsize(text, font=font)
                                x = (size[0] - text_width) // 2
                                y = (size[1] - text_height) // 2
                                draw.text((x, y), text, fill="black", font=font)
                             except Exception as fallback_e:
                                print(f"警告: 备用绘制文本方法失败: {fallback_e}")


                    img.save(path, 'PNG') # 保存为 PNG 格式
                    print(f"已创建虚拟图片文件: {path}")
                except Exception as e:
                    print(f"创建虚拟图片文件 {path} 失败: {e}")
    except ImportError:
         # 如果未安装 Pillow，禁用创建虚拟图片功能并提示
         print("Pillow 库未安装。无法创建虚拟图片。部分 UI 功能可能不完整。")
         create_dummy_image = None


    # 如果 Pillow 可用，创建所需的虚拟图片和图标
    if create_dummy_image:
         # 指示器图标
         create_dummy_image(os.path.join(dummy_icons_dir, 'star.png'), 'yellow', '⭐', size=(64, 64)) # 星星图标
         create_dummy_image(os.path.join(dummy_icons_dir, 'volume_on.png'), 'green', '🔊', size=(64, 64)) # 音量开
         create_dummy_image(os.path.join(dummy_icons_dir, 'volume_off.png'), 'gray', '🔇', size=(64, 64)) # 音量关
         create_dummy_image(os.path.join(dummy_icons_dir, 'pitch_on.png'), 'green', '🎵', size=(64, 64)) # 音高开
         create_dummy_image(os.path.join(dummy_icons_dir, 'pitch_off.png'), 'gray', '♩', size=(64, 64)) # 音高关
         create_dummy_image(os.path.join(dummy_icons_dir, 'rhythm_on.png'), 'green', '🥁', size=(64, 64)) # 节奏开
         create_dummy_image(os.path.join(dummy_icons_dir, 'rhythm_off.png'), 'gray', '.', size=(64, 64)) # 节奏关 (一个点表示无节奏)

         # 虚拟 Paw Patrol 角色图片 (用 PNG 代替 GIF 以简化测试环境)
         create_dummy_image(os.path.join(dummy_pawpatrol_dir, 'chase.png'), (100, 140, 237), 'Chase', size=(150, 150)) # 蓝色
         create_dummy_image(os.path.join(dummy_pawpatrol_dir, 'marshall.png'), (255, 99, 71), 'Marshall', size=(150, 150)) # 红色
         create_dummy_image(os.path.join(dummy_pawpatrol_dir, 'skye.png'), (255, 182, 193), 'Skye', size=(150, 150)) # 粉色

         # 虚拟背景图片
         create_dummy_image(os.path.join(dummy_bg_dir, 'pawpatrol_bg.png'), (135, 206, 235), 'Paw BG', size=(800, 600)) # 天蓝色背景


    # 为直接测试 LearningWidget 模拟歌曲数据
    test_song_data = {
        "id": "test_song_score",
        "title": "测试得分歌曲",
        "theme": "pawpatrol", # 指定主题，用于加载图片
        "audio_full": dummy_wav_path, # 使用虚拟音频文件路径
        "audio_karaoke": None,
        "lyrics": "测试第一句歌词，稍微长一点用来看看换行效果。\n测试第二句歌词。\n测试第三句乐句。\n测试第四句乐句。\n测试第五句乐句。\n测试第六句乐句。", # 添加更多乐句
        "phrases": [ # 定义乐句的时间和文本
          {"text": "这是测试的第一句歌词，有点长用来看看换行。", "start_time": 0.0, "end_time": 2.0},
          {"text": "这是测试的第二句歌词。", "start_time": 2.5, "end_time": 4.5},
          {"text": "这是测试的第三句乐句。", "start_time": 5.0, "end_time": 7.0},
          {"text": "这是测试的第四句乐句。", "start_time": 7.5, "end_time": 9.5},
          {"text": "这是测试的第五句乐句。", "start_time": 10.0, "end_time": 12.0}, # 注意虚拟音频只有 10s，这里时间超出了
          {"text": "这是测试的第六句乐句。", "start_time": 12.5, "end_time": 14.5}
        ],
        "unlocked": True,
        "unlock_stars_required": 0,
        "background_image": os.path.join(dummy_bg_dir, 'pawpatrol_bg.png'), # 指定背景图片路径
        "character_images": { # 指定主题内角色图片的文件名和路径 (相对于 images/theme/ 目录)
            "chase": 'pawpatrol/chase.png',
            "marshall": 'pawpatrol/marshall.png',
            "skye": 'pawpatrol/skye.png'
            # TODO: 如果有 GIF，修改这里的文件名为 .gif，例如 'pawpatrol/chase.gif'
        }
    }

    # 创建 LearningWidget 实例并设置测试数据
    learning_widget = LearningWidget()
    learning_widget.set_song_data(test_song_data)
    learning_widget.set_total_stars_display(15) # 模拟一些初始星星数量
    learning_widget.show() # 显示窗口

    sys.exit(app.exec()) # 运行应用事件循环