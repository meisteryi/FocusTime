"""
FocusTime - Up Next Queue Preview Dialog
Displays the upcoming YouTube algorithm tracks and allows jumping to or skipping unwanted songs.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class QueueItemWidget(QWidget):
    def __init__(self, index: int, track: dict, is_current: bool, audio_player, parent=None):
        super().__init__(parent)
        self.index = index
        self.audio_player = audio_player

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Index / Status badge
        badge_text = "▶ 재생 중" if is_current else f"{index + 1}"
        badge_label = QLabel(badge_text)
        badge_label.setFixedWidth(68 if is_current else 28)
        badge_label.setAlignment(Qt.AlignCenter)
        badge_label.setFont(QFont("Malgun Gothic", 9, QFont.Bold))
        if is_current:
            badge_label.setStyleSheet("""
                background: #1B6655; color: #FFFFFF;
                border-radius: 6px; padding: 3px 6px; border: none;
            """)
        else:
            badge_label.setStyleSheet("color: #6C938B; border: none; background: transparent;")

        # Track Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title_lbl = QLabel(track.get('title', 'Unknown Track'))
        title_lbl.setFont(QFont("Malgun Gothic", 10, QFont.Bold if is_current else QFont.Normal))
        title_lbl.setStyleSheet(f"color: {'#4ECCA3' if is_current else '#E2F3F0'}; border: none; background: transparent;")
        title_lbl.setWordWrap(True)

        uploader = track.get('uploader', '')
        dur = track.get('duration', '')
        meta_text = f"👤 {uploader}" if uploader else ""
        if dur:
            meta_text += f"  •  ⏱️ {dur}" if meta_text else f"⏱️ {dur}"

        meta_lbl = QLabel(meta_text or "YouTube 추천 트랙")
        meta_lbl.setFont(QFont("Malgun Gothic", 8))
        meta_lbl.setStyleSheet("color: #7CA49B; border: none; background: transparent;")

        info_layout.addWidget(title_lbl)
        info_layout.addWidget(meta_lbl)

        layout.addWidget(badge_label)
        layout.addLayout(info_layout, 1)

        if not is_current:
            btn_play = QPushButton("▶")
            btn_play.setFixedSize(30, 28)
            btn_play.setToolTip("이 곡 바로 재생")
            btn_play.setCursor(Qt.PointingHandCursor)
            btn_play.setStyleSheet("""
                QPushButton {
                    background: rgba(78, 204, 163, 0.15);
                    color: #4ECCA3;
                    border: 1px solid #2A6E5F;
                    border-radius: 6px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #1B6655;
                    color: #FFFFFF;
                    border-color: #4ECCA3;
                }
            """)
            btn_play.clicked.connect(lambda: self.audio_player.play_queue_index(self.index))

            btn_skip = QPushButton("✕ 제외")
            btn_skip.setFixedHeight(28)
            btn_skip.setToolTip("대기열에서 이 곡 빼기")
            btn_skip.setCursor(Qt.PointingHandCursor)
            btn_skip.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 90, 95, 0.1);
                    color: #FF8F8F;
                    border: 1px solid #5A2A2E;
                    border-radius: 6px;
                    padding: 0 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #471F23;
                    color: #FFFFFF;
                    border-color: #FF5A5F;
                }
            """)
            btn_skip.clicked.connect(lambda: self.audio_player.remove_from_queue(self.index))

            layout.addWidget(btn_play)
            layout.addWidget(btn_skip)


class QueueDialog(QDialog):
    def __init__(self, audio_player, parent=None):
        super().__init__(parent)
        self.audio_player = audio_player

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(680, 540)

        self.init_ui()
        self.refresh_list(self.audio_player.queue, self.audio_player.current_index)
        self.audio_player.queue_updated.connect(self.refresh_list)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        card = QWidget(self)
        card.setStyleSheet("""
            QWidget {
                background-color: #071C17;
                border: 2px solid #1C4D42;
                border-radius: 20px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(26, 22, 26, 22)
        card_layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("📜 다음 대기열 미리보기 (Up Next)")
        title.setFont(QFont("Malgun Gothic", 13, QFont.Bold))
        title.setStyleSheet("color: #4ECCA3; border: none; background: transparent;")

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                color: #8EAEA7;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                font-size: 13px;
            }
            QPushButton:hover { background: #FF5A5F; color: white; }
        """)
        btn_close.clicked.connect(self.reject)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(btn_close)
        card_layout.addLayout(header)

        self.sub_label = QLabel("YouTube 알고리즘이 준비한 다음 추천 곡들입니다. 원치 않는 곡은 미리 [✕ 제외]할 수 있습니다.")
        self.sub_label.setFont(QFont("Malgun Gothic", 9))
        self.sub_label.setStyleSheet("color: #7CA49B; border: none; background: transparent;")
        card_layout.addWidget(self.sub_label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #061914;
                border: 1px solid #164037;
                border-radius: 12px;
                padding: 6px;
            }
            QListWidget::item {
                border-bottom: 1px solid #0F2D26;
                border-radius: 8px;
                margin-bottom: 4px;
            }
            QListWidget::item:hover {
                background-color: #0F362E;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        card_layout.addWidget(self.list_widget)

        main_layout.addWidget(card)

    def refresh_list(self, queue: list, current_index: int):
        self.list_widget.clear()
        if not queue:
            self.sub_label.setText("아직 재생 대기열이 비어 있습니다. 음악을 검색해 재생해 보세요!")
            return

        upcoming_count = max(0, len(queue) - current_index - 1)
        self.sub_label.setText(f"현재 곡 포함 총 {len(queue)}곡 (다음 대기 중 {upcoming_count}곡) — 더블 클릭 시 즉시 이동")

        for idx, track in enumerate(queue):
            # Show from current track onwards (and up to 2 recent tracks if any)
            if idx < max(0, current_index - 1):
                continue
            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.UserRole, idx)
            widget = QueueItemWidget(idx, track, idx == current_index, self.audio_player)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def _on_double_click(self, item):
        idx = item.data(Qt.UserRole)
        if idx is not None:
            self.audio_player.play_queue_index(idx)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        try:
            self.audio_player.queue_updated.disconnect(self.refresh_list)
        except Exception:
            pass
        super().closeEvent(event)

