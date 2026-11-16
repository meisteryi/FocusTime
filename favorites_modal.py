"""
FocusTime - Favorites Manager Dialog
Allows users to play or manage their saved favorite YouTube tracks & playlists with one click.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class FavoriteItemWidget(QWidget):
    play_requested = pyqtSignal(dict)
    remove_requested = pyqtSignal(dict)

    def __init__(self, track_info: dict, parent=None):
        super().__init__(parent)
        self.track_info = track_info

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        title_lbl = QLabel(track_info.get("title", "Unknown Track"))
        title_lbl.setFont(QFont("Malgun Gothic", 10, QFont.Bold))
        title_lbl.setStyleSheet("color: #E2F3F0; border: none; background: transparent;")
        title_lbl.setWordWrap(True)

        uploader = track_info.get("uploader", "Unknown Artist")
        dur = track_info.get("duration", "")
        meta_str = f"👤 {uploader}" + (f"  •  ⏱️ {dur}" if dur else "")
        meta_lbl = QLabel(meta_str)
        meta_lbl.setFont(QFont("Malgun Gothic", 9))
        meta_lbl.setStyleSheet("color: #7CA49B; border: none; background: transparent;")

        info_layout.addWidget(title_lbl)
        info_layout.addWidget(meta_lbl)

        btn_play = QPushButton("▶ 재생")
        btn_play.setCursor(Qt.PointingHandCursor)
        btn_play.setStyleSheet("""
            QPushButton {
                background: #1B6655;
                color: #FFFFFF;
                border: 1px solid #36A588;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #24826D;
                border-color: #4ECCA3;
            }
        """)
        btn_play.clicked.connect(lambda: self.play_requested.emit(self.track_info))

        btn_del = QPushButton("✕")
        btn_del.setFixedSize(28, 28)
        btn_del.setToolTip("즐겨찾기에서 삭제")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet("""
            QPushButton {
                background: rgba(255, 90, 95, 0.12);
                color: #FF8F8F;
                border: 1px solid #5A2A2E;
                border-radius: 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #471F23;
                color: #FFFFFF;
                border-color: #FF5A5F;
            }
        """)
        btn_del.clicked.connect(lambda: self.remove_requested.emit(self.track_info))

        layout.addLayout(info_layout, 1)
        layout.addWidget(btn_play, 0, Qt.AlignVCenter)
        layout.addWidget(btn_del, 0, Qt.AlignVCenter)


class FavoritesDialog(QDialog):
    track_selected = pyqtSignal(list, int)

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.favorites = []

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(680, 520)

        self.init_ui()
        self.refresh_list()

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
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("⭐ 나만의 플레이리스트 즐겨찾기")
        title.setFont(QFont("Malgun Gothic", 13, QFont.Bold))
        title.setStyleSheet("color: #FFD166; border: none; background: transparent;")

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

        self.sub_label = QLabel("저장해 둔 음악을 클릭 한 번으로 바로 재생할 수 있습니다.")
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

    def refresh_list(self):
        self.list_widget.clear()
        self.favorites = self.storage.get_favorites()

        if not self.favorites:
            self.sub_label.setText("저장된 즐겨찾기가 없습니다. 음악 검색 결과나 하단 플레이어에서 [☆] 버튼을 눌러 추가해 보세요!")
            return

        self.sub_label.setText(f"총 {len(self.favorites)}개의 즐겨찾기 곡이 저장되어 있습니다.")
        for idx, track in enumerate(self.favorites):
            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.UserRole, idx)
            widget = FavoriteItemWidget(track)
            widget.play_requested.connect(lambda t, i=idx: self._play_index(i))
            widget.remove_requested.connect(self._remove_track)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def _play_index(self, idx: int):
        if 0 <= idx < len(self.favorites):
            self.track_selected.emit(self.favorites, idx)
            self.accept()

    def _remove_track(self, track: dict):
        self.storage.remove_favorite(track)
        self.refresh_list()

    def _on_double_click(self, item):
        idx = item.data(Qt.UserRole)
        if idx is not None:
            self._play_index(idx)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
