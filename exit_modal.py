"""
FocusTime - Exit Guard Warning Dialog
Displays a dim warning overlay when the user attempts to exit full-screen mode.
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class ExitGuardDialog(QDialog):
    def __init__(self, elapsed_seconds: int, parent=None):
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

        self.init_ui(time_str)

    def init_ui(self, time_str: str):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Container card
        card = QWidget(self)
        card.setFixedSize(520, 320)
        card.setStyleSheet("""
            QWidget {
                background-color: #0B1C19;
                border: 2px solid #1C453E;
                border-radius: 20px;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(18)
        card_layout.setAlignment(Qt.AlignCenter)

        # Warning Title
        title_label = QLabel("⚠️ 잠깐만요!", card)
        title_font = QFont("Malgun Gothic", 22, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #FF7B7B; border: none; background: transparent;")
        title_label.setAlignment(Qt.AlignCenter)

        # Message
        msg_label = QLabel(
            f"현재 <b style='color:#4ECCA3; font-size:18px;'>{time_str}</b> 동안 깊게 몰입 중입니다.<br>"
            "지금 나가시면 소중한 집중 흐름이 끊기게 됩니다.<br><br>"
            "정말 집중을 중단하시겠습니까?", card
        )
        msg_font = QFont("Malgun Gothic", 12)
        msg_label.setFont(msg_font)
        msg_label.setStyleSheet("color: #D3E0DC; border: none; line-height: 1.5; background: transparent;")
        msg_label.setAlignment(Qt.AlignCenter)

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

        card_layout.addWidget(title_label)
        card_layout.addWidget(msg_label)
        card_layout.addSpacing(10)
        card_layout.addLayout(btn_layout)

        main_layout.addWidget(card)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

