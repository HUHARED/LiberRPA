# FileName: _Notifier.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont


class Notifier(QWidget):
    def __init__(self, title: str, message: str, duration: int) -> None:
        # Use Qt.Tool, Qt.FramelessWindowHint, etc. so it appears like a tooltip.
        super().__init__(flags=Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        self.setFixedSize(300, 100)

        # Position it at bottom-right of the primary screen
        mainScreenGeo = QApplication.primaryScreen().availableGeometry()
        self.move(mainScreenGeo.width() - self.width() - 10, mainScreenGeo.height() - self.height() - 10)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Create a label for show the message
        self.label = QLabel(f"--{title}--\n{message}", self)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.label.setFont(QFont("Noto Sans Mono", 10))
        self.label.setContentsMargins(5, 0, 5, 0)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            """
            background: grey;
            color: white;
            border-radius: 10px;
            """
        )

        # Use a layout so the label fills the entire widget area
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.setLayout(layout)

        QTimer.singleShot(duration * 1000, self.close)


_current_notifier: Notifier | None = None


def show_notification(title: str, message: str, duration: int = 1) -> None:
    global _current_notifier

    if message is None or message == "":
        raise ValueError("The message can't be empty or None.")
    if duration <= 0:
        raise ValueError("The duration should larger than 0.")

    # If there is a notification is showing, close it to show the new one.
    if _current_notifier:
        _current_notifier.close()

    notifier = Notifier(title=title, message=message, duration=duration)
    _current_notifier = notifier
    notifier.show()
