"""
FocusTime - Main Entry Point
Zero-distraction, Breathing Ambient Fullscreen Focus Application.
"""

import sys
import os

# Crucial Chromium flags for background audio playback without user gesture requirement
sys.argv.extend([
    '--autoplay-policy=no-user-gesture-required',
    '--no-sandbox',
    '--disable-web-security'
])

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from focus_window import FocusWindow


def main():
    # Enable High DPI scaling for QHD 2560x1440 display
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("FocusTime")

    # Default Font
    font = QFont("Malgun Gothic", 10)
    app.setFont(font)

    window = FocusWindow()
    window.showFullScreen()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
