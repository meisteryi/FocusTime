"""
FocusTime - Exit Guard Warning Dialog
Displays a dim warning overlay when the user attempts to exit full-screen mode.
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class ExitGuardDialog(QDialog):
    def __init__(self, elapsed_seconds: int, parent=None, today_summary: str = ""):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        hours = elapsed_seconds // 3600
        minutes = (elapsed_seconds % 3600) // 60
        seconds = elapsed_seconds % 60

        if hours > 0:
            time_str = f"{hours}시간 {minutes:02d}분"
        elif minutes > 0:
            time_str = f"{minutes}분 {seconds:02d}초"
        else:
            time_str = f"{seconds}초"

        self.init_ui(time_str, today_summary)

    def init_ui(self, time_str: str, today_summary: str):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Container card
        card = QWidget(self)
        card.setFixedSize(540, 360 if today_summary else 320)
        card.setStyleSheet("""
            QWidget {
                background-color: #0B1C19;
                border: 2px solid #1C453E;
                border-radius: 20px;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 36, 40, 36)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignCenter)

        # Warning Title
        title_label = QLabel("⚠️ 잠깐만요!", card)
        title_font = QFont("Malgun Gothic", 22, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #FF7B7B; border: none; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)

        # Message
        msg_label = QLabel(
            f"현재 세션 <b style='color:#4ECCA3; font-size:18px;'>{time_str}</b> 동안 깊게 몰입 중입니다.<br>"
            "정말 집중을 중단하시겠습니까?", card
        )
        msg_font = QFont("Malgun Gothic", 12)
        msg_label.setFont(msg_font)
        msg_label.setStyleSheet("color: #D3E0DC; border: none; line-height: 1.5; background: transparent;")
        msg_label.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(title_label)
        card_layout.addWidget(msg_label)

        if today_summary:
            stat_label = QLabel(today_summary, card)
            stat_label.setFont(QFont("Malgun Gothic", 10, QFont.Bold))
            stat_label.setStyleSheet("""
                color: #FFD166;
                background: rgba(255, 209, 102, 0.1);
                border: 1px solid rgba(255, 209, 102, 0.3);
                border-radius: 10px;
                padding: 8px 14px;
            """)
            stat_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(stat_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)

        self.btn_continue = QPushButton("계속 집중하기 (ESC)", card)
        self.btn_continue.setFont(QFont("Malgun Gothic", 11, QFont.Bold))
        self.btn_continue.setCursor(Qt.PointingHandCursor)
        self.btn_continue.setStyleSheet("""
            QPushButton {
                background-color: #1F6E5B;
                color: #FFFFFF;
                border: 1px solid #36A588;
                border-radius: 10px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #26856E;
                border: 1px solid #4ECCA3;
            }
        """)
        self.btn_continue.clicked.connect(self.reject)

        self.btn_exit = QPushButton("포기하고 나가기", card)
        self.btn_exit.setFont(QFont("Malgun Gothic", 11))
        self.btn_exit.setCursor(Qt.PointingHandCursor)
        self.btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #201314;
                color: #FF8F8F;
                border: 1px solid #5A2A2E;
                border-radius: 10px;
                padding: 12px 20px;
            }
            QPushButton:hover {
                background-color: #381E21;
                border: 1px solid #FF5A5F;
            }
        """)
        self.btn_exit.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_continue)
        btn_layout.addWidget(self.btn_exit)

        card_layout.addSpacing(8)
        card_layout.addLayout(btn_layout)

        main_layout.addWidget(card)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

