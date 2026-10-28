"""
FocusTime - Main Fullscreen Focus Window
Features:
- Windows Taskbar covering True Fullscreen
- Eye-comforting Forest Green ~ Dark Teal breathing ambient gradient animation
- Realtime digital clock (Current time)
- Focus duration stopwatch (Elapsed focus time) with pause/reset
- Direct YouTube audio streaming player (yt-dlp powered, zero ads) with presets
- In-App YouTube Search Dialog with Endless Related-Tracks Autoplay
- Escape interceptor with ExitGuardDialog
- 'Peek / Minimize' option for safe temporary desktop access
"""

import math
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSlider, QFrame, QApplication, QInputDialog
)
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QRadialGradient, QColor, QFont

from audio_streamer import AudioPlayer
from exit_modal import ExitGuardDialog
from search_modal import YouTubeSearchDialog


class FocusWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Fullscreen & Taskbar covering flags
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

        # Breathing background state
        self.phase = 0.0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._update_breathing)
        self.anim_timer.start(33)  # ~30 FPS

        # Time & Focus state
        self.focus_seconds = 0
        self.is_focus_active = True

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock_and_timer)
        self.clock_timer.start(1000)

        # Audio Streamer
        self.audio_player = AudioPlayer(self)
        self.audio_player.status_updated.connect(self._on_audio_status)
        self.audio_player.title_updated.connect(self._on_audio_title)
        self.audio_player.state_changed.connect(self._on_audio_state)
        self.audio_player.autoplay_changed.connect(self._on_autoplay_changed)

        # Initialize UI Layouts
        self.init_ui()

    def _update_breathing(self):
        # 5 second breathing cycle
        self.phase += 0.04
        if self.phase > 2 * math.pi:
            self.phase -= 2 * math.pi
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Sine wave breathing factor normalized to 0.0 ~ 1.0
        breath = (math.sin(self.phase) + 1.0) / 2.0

        # Dynamic gradient center and radius
        center = QPointF(w * 0.5, h * 0.45)
        radius = w * (0.55 + 0.15 * breath)

        gradient = QRadialGradient(center, radius)

        # Center pulse: #0A2E27 -> #154F43
        r_c = int(10 + 11 * breath)
        g_c = int(46 + 33 * breath)
        b_c = int(39 + 28 * breath)
        center_color = QColor(r_c, g_c, b_c)

        mid_color = QColor(6, 26, 22, 240)
        outer_color = QColor(3, 13, 11)

        gradient.setColorAt(0.0, center_color)
        gradient.setColorAt(0.55, mid_color)
        gradient.setColorAt(1.0, outer_color)

        painter.fillRect(self.rect(), gradient)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 40, 60, 40)
        main_layout.setSpacing(0)

        # 1. Top Header Bar
        top_bar = QHBoxLayout()
        logo_label = QLabel("FocusTime")
        logo_label.setFont(QFont("Malgun Gothic", 12, QFont.Bold))
        logo_label.setStyleSheet("color: #4ECCA3; letter-spacing: 2px;")

        hint_label = QLabel("ESC : 이탈 경고 및 종료 | F10 : 잠시 외출")
        hint_label.setFont(QFont("Malgun Gothic", 10))
        hint_label.setStyleSheet("color: #6C8E86;")

        btn_minimize = QPushButton("🗕 잠시 외출")
        btn_minimize.setCursor(Qt.PointingHandCursor)
        btn_minimize.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: #A3C9C2;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
                padding: 6px 14px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(78, 204, 163, 0.2);
                color: #FFFFFF;
                border-color: #4ECCA3;
            }
        """)
        btn_minimize.clicked.connect(self.showMinimized)

        btn_exit_corner = QPushButton("✕")
        btn_exit_corner.setFixedSize(36, 36)
        btn_exit_corner.setCursor(Qt.PointingHandCursor)
        btn_exit_corner.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: #A3C9C2;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 18px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #FF5A5F;
                color: white;
            }
        """)
        btn_exit_corner.clicked.connect(self.request_exit)

        top_bar.addWidget(logo_label)
        top_bar.addSpacing(16)
        top_bar.addWidget(hint_label)
        top_bar.addStretch()
        top_bar.addWidget(btn_minimize)
        top_bar.addSpacing(12)
        top_bar.addWidget(btn_exit_corner)
        main_layout.addLayout(top_bar)

        main_layout.addStretch(1)

        # 2. Center Focus Section (Hero)
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(14)

        # Date Label
        self.date_label = QLabel()
        self.date_label.setFont(QFont("Malgun Gothic", 14))
        self.date_label.setStyleSheet("color: #8EAEA7; letter-spacing: 1px;")
        self.date_label.setAlignment(Qt.AlignCenter)

        # Realtime Digital Clock (Large)
        self.clock_label = QLabel()
        self.clock_label.setFont(QFont("Segoe UI", 76, QFont.Bold))
        self.clock_label.setStyleSheet("color: #F5FAF8; letter-spacing: 4px;")
        self.clock_label.setAlignment(Qt.AlignCenter)

        # Focus Stopwatch Card
        focus_card = QFrame()
        focus_card.setStyleSheet("""
            QFrame {
                background: rgba(7, 28, 24, 0.65);
                border: 1px solid #1E5046;
                border-radius: 24px;
                padding: 16px 40px;
            }
        """)
        card_layout = QVBoxLayout(focus_card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(6)

        focus_title = QLabel("🔥 집중 몰입 시간")
        focus_title.setFont(QFont("Malgun Gothic", 11, QFont.Bold))
        focus_title.setStyleSheet("color: #4ECCA3; border: none; background: transparent;")
        focus_title.setAlignment(Qt.AlignCenter)

        self.timer_label = QLabel("00 : 00 : 00")
        self.timer_label.setFont(QFont("Segoe UI", 44, QFont.DemiBold))
        self.timer_label.setStyleSheet("color: #FFFFFF; border: none; background: transparent; letter-spacing: 3px;")
        self.timer_label.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(focus_title)
        card_layout.addWidget(self.timer_label)

        # Focus Control Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(14)
        btn_box.setAlignment(Qt.AlignCenter)

        self.btn_pause = QPushButton("❚❚ 일시정지")
        self.btn_pause.setFont(QFont("Malgun Gothic", 10, QFont.Bold))
        self.btn_pause.setCursor(Qt.PointingHandCursor)
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background: #15453C;
                color: #E0F2EE;
                border: 1px solid #236B5E;
                border-radius: 10px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background: #1B584D;
                border-color: #4ECCA3;
            }
        """)
        self.btn_pause.clicked.connect(self.toggle_focus)

        self.btn_reset = QPushButton("■ 리셋")
        self.btn_reset.setFont(QFont("Malgun Gothic", 10))
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background: rgba(20, 20, 20, 0.4);
                color: #A3C9C2;
                border: 1px solid #1B453D;
                border-radius: 10px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background: rgba(255, 90, 95, 0.2);
                color: #FFA5A8;
                border-color: #FF5A5F;
            }
        """)
        self.btn_reset.clicked.connect(self.reset_focus)

        btn_box.addWidget(self.btn_pause)
        btn_box.addWidget(self.btn_reset)

        center_layout.addWidget(self.date_label)
        center_layout.addWidget(self.clock_label)
        center_layout.addSpacing(10)
        center_layout.addWidget(focus_card, 0, Qt.AlignCenter)
        center_layout.addSpacing(10)
        center_layout.addLayout(btn_box)

        main_layout.addLayout(center_layout)

        main_layout.addStretch(1)

        # 3. Bottom Clean YouTube BGM Player
        player_card = QFrame()
        player_card.setStyleSheet("""
            QFrame {
                background: rgba(7, 24, 20, 0.85);
                border: 1px solid #1A473E;
                border-radius: 20px;
                padding: 16px 28px;
            }
        """)
        player_layout = QVBoxLayout(player_card)
        player_layout.setSpacing(12)

        # Track Info Row
        track_row = QHBoxLayout()
        self.music_icon = QLabel("🎵")
        self.music_icon.setStyleSheet("border:none; font-size: 16px; background: transparent;")

        self.track_title = QLabel("재생 대기 중 ([🔍 음악 검색]으로 원하는 플레이리스트를 찾아보세요)")
        self.track_title.setFont(QFont("Malgun Gothic", 11, QFont.Bold))
        self.track_title.setStyleSheet("color: #E2F3F0; border: none; background: transparent;")

        self.btn_copy_current = QPushButton("📋 링크 복사")
        self.btn_copy_current.setCursor(Qt.PointingHandCursor)
        self.btn_copy_current.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: #A3D1C8;
                border: 1px solid #1C4D42;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #1C5447;
                color: #FFFFFF;
                border-color: #4ECCA3;
            }
        """)
        self.btn_copy_current.clicked.connect(self._copy_current_track_url)

        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Malgun Gothic", 10))
        self.status_label.setStyleSheet("color: #4ECCA3; border: none; background: transparent;")

        track_row.addWidget(self.music_icon)
        track_row.addWidget(self.track_title)
        track_row.addSpacing(12)
        track_row.addWidget(self.btn_copy_current)
        track_row.addStretch()
        track_row.addWidget(self.status_label)

        # Controls & Search Row
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(12)

        # In-App Search Button (Primary)
        self.btn_search_dialog = QPushButton("🔍 음악 검색")
        self.btn_search_dialog.setFont(QFont("Malgun Gothic", 10, QFont.Bold))
        self.btn_search_dialog.setCursor(Qt.PointingHandCursor)
        self.btn_search_dialog.setStyleSheet("""
            QPushButton {
                background: #1F6E5B;
                color: #FFFFFF;
                border: 1px solid #36A588;
                border-radius: 8px;
                padding: 7px 18px;
            }
            QPushButton:hover {
                background: #278871;
                border-color: #4ECCA3;
            }
        """)
        self.btn_search_dialog.clicked.connect(self._open_search_dialog)

        # Prev Track
        self.btn_prev = QPushButton("◀◀")
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.setStyleSheet(self._playback_ctrl_style())
        self.btn_prev.clicked.connect(self.audio_player.prev_track)

        # Play/Pause
        self.btn_play = QPushButton("▶ 재생")
        self.btn_play.setFont(QFont("Malgun Gothic", 10, QFont.Bold))
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background: #174E43;
                color: #FFFFFF;
                border: 1px solid #287D6C;
                border-radius: 8px;
                padding: 7px 18px;
            }
            QPushButton:hover {
                background: #1F6456;
                border-color: #4ECCA3;
            }
        """)
        self.btn_play.clicked.connect(self.audio_player.toggle_play)

        # Next Track
        self.btn_next = QPushButton("▶▶")
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setStyleSheet(self._playback_ctrl_style())
        self.btn_next.clicked.connect(self.audio_player.next_track)

        # Autoplay Indicator / Toggle Button
        self.btn_autoplay = QPushButton("📻 연관곡 자동재생: ON")
        self.btn_autoplay.setCursor(Qt.PointingHandCursor)
        self.btn_autoplay.setStyleSheet("""
            QPushButton {
                background: rgba(78, 204, 163, 0.15);
                color: #4ECCA3;
                border: 1px solid #2A6E5F;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(78, 204, 163, 0.25);
            }
        """)
        self.btn_autoplay.clicked.connect(self.audio_player.toggle_autoplay)

        # Presets
        presets_label = QLabel("추천:")
        presets_label.setStyleSheet("color: #7DA69E; border: none; font-size: 11px; background: transparent;")

        btn_lofi = self._create_preset_btn("☕ Lofi", "https://www.youtube.com/watch?v=jfKfPfyJRdk", "Lofi Beats Radio")
        btn_rain = self._create_preset_btn("🌧️ 빗소리", "https://www.youtube.com/watch?v=mPZkdNFkNps", "빗소리 백색소음")
        btn_jazz = self._create_preset_btn("🎷 재즈", "https://www.youtube.com/watch?v=Dx5qFachd3A", "카페 재즈")

        # Custom URL Button
        btn_custom = QPushButton("🔗 URL")
        btn_custom.setCursor(Qt.PointingHandCursor)
        btn_custom.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: #BBE3DC;
                border: 1px solid #1E4E45;
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(78, 204, 163, 0.2);
                border-color: #4ECCA3;
                color: white;
            }
        """)
        btn_custom.clicked.connect(self._prompt_custom_url)

        # Volume Slider
        vol_label = QLabel("🔊")
        vol_label.setStyleSheet("border:none; color:#8CA8A2; background: transparent;")

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.setFixedWidth(110)
        self.vol_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #14362F;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #4ECCA3;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
        """)
        self.vol_slider.valueChanged.connect(self.audio_player.set_volume)

        ctrl_row.addWidget(self.btn_search_dialog)
        ctrl_row.addSpacing(4)
        ctrl_row.addWidget(self.btn_prev)
        ctrl_row.addWidget(self.btn_play)
        ctrl_row.addWidget(self.btn_next)
        ctrl_row.addWidget(self.btn_autoplay)
        ctrl_row.addSpacing(10)
        ctrl_row.addWidget(presets_label)
        ctrl_row.addWidget(btn_lofi)
        ctrl_row.addWidget(btn_rain)
        ctrl_row.addWidget(btn_jazz)
        ctrl_row.addWidget(btn_custom)
        ctrl_row.addStretch()
        ctrl_row.addWidget(vol_label)
        ctrl_row.addWidget(self.vol_slider)

        player_layout.addLayout(track_row)
        player_layout.addLayout(ctrl_row)

        main_layout.addWidget(player_card)

        # Initial clock update
        self._update_clock_and_timer()

    def _playback_ctrl_style(self) -> str:
        return """
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: #A3D1C8;
                border: 1px solid #1A473E;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #1C5447;
                color: #FFFFFF;
                border-color: #4ECCA3;
            }
        """

    def _create_preset_btn(self, name: str, url: str, title: str) -> QPushButton:
        btn = QPushButton(name)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: rgba(18, 56, 48, 0.5);
                color: #A3D1C8;
                border: 1px solid #1E5045;
                border-radius: 8px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #1D6354;
                border-color: #4ECCA3;
                color: #FFFFFF;
            }
        """)
        btn.clicked.connect(lambda: self.audio_player.play_url(url, title))
        return btn

    def _open_search_dialog(self):
        dialog = YouTubeSearchDialog(self.audio_player, self)
        dialog.track_selected.connect(self._on_search_track_selected)
        dialog.exec_()

    def _on_search_track_selected(self, results: list, selected_index: int):
        self.audio_player.set_queue_and_play(results, selected_index)

    def _prompt_custom_url(self):
        text, ok = QInputDialog.getText(
            self, "YouTube URL 입력",
            "재생할 YouTube 영상 주소를 붙여넣으세요:",
            QLineEdit.Normal, ""
        )
        if ok and text.strip():
            self.audio_player.play_url(text.strip())

    def _update_clock_and_timer(self):
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H : %M : %S"))

        weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        day_str = weekdays[now.weekday()]
        self.date_label.setText(now.strftime(f"%Y년 %m월 %d일 {day_str}"))

        if self.is_focus_active:
            self.focus_seconds += 1
            h = self.focus_seconds // 3600
            m = (self.focus_seconds % 3600) // 60
            s = self.focus_seconds % 60
            self.timer_label.setText(f"{h:02d} : {m:02d} : {s:02d}")

    def toggle_focus(self):
        self.is_focus_active = not self.is_focus_active
        if self.is_focus_active:
            self.btn_pause.setText("❚❚ 일시정지")
            self.btn_pause.setStyleSheet("""
                QPushButton {
                    background: #15453C;
                    color: #E0F2EE;
                    border: 1px solid #236B5E;
                    border-radius: 10px;
                    padding: 8px 20px;
                }
                QPushButton:hover { background: #1B584D; border-color: #4ECCA3; }
            """)
        else:
            self.btn_pause.setText("▶ 재개하기")
            self.btn_pause.setStyleSheet("""
                QPushButton {
                    background: #2A6E5F;
                    color: #FFFFFF;
                    border: 1px solid #4ECCA3;
                    border-radius: 10px;
                    padding: 8px 20px;
                }
                QPushButton:hover { background: #338573; }
            """)

    def reset_focus(self):
        self.focus_seconds = 0
        self.timer_label.setText("00 : 00 : 00")

    def _copy_current_track_url(self):
        url = self.audio_player.get_current_url()
        if url:
            QApplication.clipboard().setText(url)
            self.btn_copy_current.setText("✓ 복사됨")
            self.status_label.setText("✓ 현재 곡 URL이 클립보드에 복사되었습니다!")
            QTimer.singleShot(1800, lambda: self.btn_copy_current.setText("📋 링크 복사"))
        else:
            self.status_label.setText("재생 중인 곡이 없습니다.")

    def _on_audio_status(self, msg: str):
        self.status_label.setText(msg)

    def _on_audio_title(self, title: str, uploader: str):
        if uploader:
            self.track_title.setText(f"{title}  —  {uploader}")
        else:
            self.track_title.setText(title)

    def _on_audio_state(self, is_playing: bool):
        if is_playing:
            self.btn_play.setText("❚❚ 정지")
        else:
            self.btn_play.setText("▶ 재생")

    def _on_autoplay_changed(self, active: bool):
        if active:
            self.btn_autoplay.setText("📻 연관곡 자동재생: ON")
            self.btn_autoplay.setStyleSheet("""
                QPushButton {
                    background: rgba(78, 204, 163, 0.15);
                    color: #4ECCA3;
                    border: 1px solid #2A6E5F;
                    border-radius: 8px;
                    padding: 6px 12px;
                    font-size: 11px;
                }
                QPushButton:hover { background: rgba(78, 204, 163, 0.25); }
            """)
        else:
            self.btn_autoplay.setText("📻 연관곡 자동재생: OFF")
            self.btn_autoplay.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    color: #7E9E96;
                    border: 1px solid #1B453D;
                    border-radius: 8px;
                    padding: 6px 12px;
                    font-size: 11px;
                }
                QPushButton:hover { background: rgba(255, 255, 255, 0.1); }
            """)

    def request_exit(self):
        dialog = ExitGuardDialog(self.focus_seconds, self)
        if dialog.exec_() == ExitGuardDialog.Accepted:
            self.audio_player.stop()
            QApplication.quit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.request_exit()
        elif event.key() == Qt.Key_F10:
            self.showMinimized()
        else:
            super().keyPressEvent(event)
