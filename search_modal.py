"""
FocusTime - In-App YouTube Search Dialog
Allows users to search YouTube music directly without leaving the fullscreen focus app.
Results are displayed in a clean dark UI, with quick [Copy URL] buttons and endless autoplay.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QWidget, QCheckBox,
    QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont


class SearchResultItemWidget(QWidget):
    copy_requested = pyqtSignal(str)

    def __init__(self, track_info: dict, parent=None):
        super().__init__(parent)
        self.track_info = track_info
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Info Box (Title + Meta)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        title_label = QLabel(track_info.get('title', 'Unknown'))
        title_label.setFont(QFont("Malgun Gothic", 10, QFont.Bold))
        title_label.setStyleSheet("color: #E2F3F0; border: none; background: transparent;")
        title_label.setWordWrap(True)

        meta_layout = QHBoxLayout()
        uploader_label = QLabel(f"👤 {track_info.get('uploader', 'Unknown')}")
        uploader_label.setFont(QFont("Malgun Gothic", 9))
        uploader_label.setStyleSheet("color: #8EAEA7; border: none; background: transparent;")

        dur_label = QLabel(f"⏱️ {track_info.get('duration', '')}")
        dur_label.setFont(QFont("Malgun Gothic", 9))
        dur_label.setStyleSheet("color: #4ECCA3; border: none; background: transparent;")

        meta_layout.addWidget(uploader_label)
        meta_layout.addSpacing(16)
        meta_layout.addWidget(dur_label)
        meta_layout.addStretch()

        info_layout.addWidget(title_label)
        info_layout.addLayout(meta_layout)

        # Quick Copy Button for this item
        self.btn_copy = QPushButton("📋 복사")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: #A3D1C8;
                border: 1px solid #1C4D42;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #1C5447;
                color: #FFFFFF;
                border-color: #4ECCA3;
            }
        """)
        self.btn_copy.clicked.connect(self._copy_url)

        layout.addLayout(info_layout, 1)
        layout.addWidget(self.btn_copy, 0, Qt.AlignVCenter)

    def _copy_url(self):
        url = self.track_info.get('url', '')
        if url:
            QApplication.clipboard().setText(url)
            self.btn_copy.setText("✓ 완료")
            self.btn_copy.setStyleSheet("""
                QPushButton {
                    background: #1B6655;
                    color: #FFFFFF;
                    border: 1px solid #4ECCA3;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 11px;
                }
            """)
            QTimer.singleShot(1500, self._reset_copy_btn)
            self.copy_requested.emit(url)

    def _reset_copy_btn(self):
        self.btn_copy.setText("📋 복사")
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                color: #A3D1C8;
                border: 1px solid #1C4D42;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #1C5447;
                color: #FFFFFF;
                border-color: #4ECCA3;
            }
        """)


class YouTubeSearchDialog(QDialog):
    track_selected = pyqtSignal(list, int)  # results_list, selected_index

    def __init__(self, audio_player, parent=None):
        super().__init__(parent)
        self.audio_player = audio_player
        self.results = []

        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(720, 570)

        self.init_ui()

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

        # Header
        header = QHBoxLayout()
        title = QLabel("🔍 YouTube 음악 / 플레이리스트 검색")
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

        # Search Input Bar
        search_bar = QHBoxLayout()
        search_bar.setSpacing(10)

        self.input_query = QLineEdit()
        self.input_query.setPlaceholderText("검색어 입력 (예: 코딩할 때 듣는 로파이, 지브리 피아노, 스터디 재즈)")
        self.input_query.setFont(QFont("Malgun Gothic", 10))
        self.input_query.setStyleSheet("""
            QLineEdit {
                background: #0D2B24;
                color: #FFFFFF;
                border: 1px solid #1E5C4F;
                border-radius: 10px;
                padding: 10px 14px;
            }
            QLineEdit:focus {
                border: 1px solid #4ECCA3;
            }
        """)
        self.input_query.returnPressed.connect(self.do_search)

        self.btn_search = QPushButton("검색")
        self.btn_search.setFont(QFont("Malgun Gothic", 10, QFont.Bold))
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.setStyleSheet("""
            QPushButton {
                background: #1B6655;
                color: #FFFFFF;
                border: 1px solid #36A588;
                border-radius: 10px;
                padding: 10px 22px;
            }
            QPushButton:hover {
                background: #237A67;
                border-color: #4ECCA3;
            }
        """)
        self.btn_search.clicked.connect(self.do_search)

        search_bar.addWidget(self.input_query)
        search_bar.addWidget(self.btn_search)
        card_layout.addLayout(search_bar)

        # Quick suggestions
        suggest_bar = QHBoxLayout()
        suggest_bar.setSpacing(8)
        sug_label = QLabel("추천:")
        sug_label.setStyleSheet("color: #6C938B; border: none; font-size: 11px; background: transparent;")
        suggest_bar.addWidget(sug_label)

        for kw in ["Lofi Beats", "지브리 피아노", "카페 재즈", "빗소리 ASMR"]:
            btn_s = QPushButton(kw)
            btn_s.setCursor(Qt.PointingHandCursor)
            btn_s.setStyleSheet("""
                QPushButton {
                    background: rgba(22, 64, 55, 0.4);
                    color: #A3D1C8;
                    border: 1px solid #1A473E;
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
            btn_s.clicked.connect(lambda checked, text=kw: self._apply_keyword(text))
            suggest_bar.addWidget(btn_s)

        suggest_bar.addStretch()
        card_layout.addLayout(suggest_bar)

        # Status / Feedback label
        self.label_status = QLabel("검색어를 입력하고 검색 버튼을 누르세요.")
        self.label_status.setFont(QFont("Malgun Gothic", 9))
        self.label_status.setStyleSheet("color: #7CA49B; border: none; background: transparent;")
        card_layout.addWidget(self.label_status)

        # Results List
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
            QListWidget::item:selected {
                background-color: #174E42;
                border: 1px solid #4ECCA3;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        card_layout.addWidget(self.list_widget)

        # Footer
        footer = QHBoxLayout()
        self.chk_autoplay = QCheckBox("곡 종료 시 연관 곡 자동 이어재생 (무한 재생)")
        self.chk_autoplay.setChecked(self.audio_player.autoplay)
        self.chk_autoplay.setStyleSheet("""
            QCheckBox {
                color: #A3D1C8;
                border: none;
                background: transparent;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
        """)
        self.chk_autoplay.toggled.connect(self._on_autoplay_toggled)

        self.btn_copy_selected = QPushButton("📋 선택한 URL 복사")
        self.btn_copy_selected.setFont(QFont("Malgun Gothic", 10))
        self.btn_copy_selected.setCursor(Qt.PointingHandCursor)
        self.btn_copy_selected.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: #BBE3DC;
                border: 1px solid #1E5C4F;
                border-radius: 8px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: rgba(78, 204, 163, 0.2);
                border-color: #4ECCA3;
                color: #FFFFFF;
            }
        """)
        self.btn_copy_selected.clicked.connect(self._copy_selected_url)

        self.btn_play_selected = QPushButton("▶ 선택 곡 재생")
        self.btn_play_selected.setFont(QFont("Malgun Gothic", 10, QFont.Bold))
        self.btn_play_selected.setCursor(Qt.PointingHandCursor)
        self.btn_play_selected.setStyleSheet("""
            QPushButton {
                background: #1B6655;
                color: #FFFFFF;
                border: 1px solid #36A588;
                border-radius: 8px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background: #24826D;
                border-color: #4ECCA3;
            }
        """)
        self.btn_play_selected.clicked.connect(self._on_play_clicked)

        footer.addWidget(self.chk_autoplay)
        footer.addStretch()
        footer.addWidget(self.btn_copy_selected)
        footer.addWidget(self.btn_play_selected)
        card_layout.addLayout(footer)

        main_layout.addWidget(card)

    def _apply_keyword(self, kw: str):
        self.input_query.setText(kw)
        self.do_search()

    def _on_autoplay_toggled(self, checked: bool):
        self.audio_player.autoplay = checked
        self.audio_player.autoplay_changed.emit(checked)

    def do_search(self):
        query = self.input_query.text().strip()
        if not query:
            return

        self.label_status.setText(f"'{query}' 검색 중입니다...")
        self.btn_search.setEnabled(False)
        self.list_widget.clear()

        def on_results(results):
            self.results = results
            self.btn_search.setEnabled(True)
            self.list_widget.clear()

            if not results:
                self.label_status.setText("검색 결과가 없습니다.")
                return

            self.label_status.setText(f"{len(results)}개의 음악을 찾았습니다. 더블 클릭하거나 [선택 곡 재생]을 누르세요.")
            for r in results:
                item = QListWidgetItem(self.list_widget)
                widget = SearchResultItemWidget(r)
                widget.copy_requested.connect(self._on_item_copy_requested)
                item.setSizeHint(widget.sizeHint())
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, widget)

            if results:
                self.list_widget.setCurrentRow(0)

        def on_error(err_msg):
            self.btn_search.setEnabled(True)
            self.label_status.setText(err_msg)

        self.audio_player.search(query, on_results, on_error)

    def _on_item_copy_requested(self, url: str):
        self.label_status.setText("✓ URL이 클립보드에 복사되었습니다!")

    def _copy_selected_url(self):
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.results):
            url = self.results[row].get('url', '')
            if url:
                QApplication.clipboard().setText(url)
                self.btn_copy_selected.setText("✓ 복사 완료!")
                self.label_status.setText(f"✓ '{self.results[row].get('title')}' 링크가 복사되었습니다!")
                QTimer.singleShot(1500, lambda: self.btn_copy_selected.setText("📋 선택한 URL 복사"))

    def _on_item_double_clicked(self, item):
        self._on_play_clicked()

    def _on_play_clicked(self):
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.results):
            self.track_selected.emit(self.results, row)
            self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
