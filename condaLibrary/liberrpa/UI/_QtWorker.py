# FileName: _QtWorker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._Exception import get_exception_info
from liberrpa.UI._Notifier import show_notification

from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtGui import QTextCursor, QFont, QFontMetrics, QColor, QPainter, QPen

from queue import Empty
import uuid
from multiprocessing import Queue
from typing import Literal, Any

# print(f"Import QtWorker in process: {current_process().name}")

# Put the qtApp in global, otherwise Python may clean it after create_area() return.
qtApp = QApplication([])


class ScreenPrintObj(str):
    pass


class RealScreenPrintObj(QMainWindow):
    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 400,
        height: int = 200,
        fontFamily: str = "Roboto Mono",
        fontSize: int = 16,
        fontColor: Literal["red", "green", "blue", "yellow", "purple", "pink", "black"] = "red",
    ):
        super().__init__()

        # Check if the specified color is one of the allowed values
        listColors = ["red", "green", "blue", "yellow", "purple", "pink", "black"]
        if fontColor not in listColors:
            raise ValueError(f"fontColor should be one of {listColors}")

        # Window setup
        self.setGeometry(x, y, width, height)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Create the text widget
        self.text_widget = QTextEdit(self)
        self.text_widget.setReadOnly(True)

        # Hide scroll bars
        self.text_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Use a StyleSheet for color and transparent background
        self.text_widget.setStyleSheet(f"QTextEdit {{ border: none; background: transparent; color: {fontColor};}}")

        # Set font and color
        font = QFont(fontFamily, fontSize)
        self.text_widget.setFont(font)

        # Layout
        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.text_widget)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def display_text(self, text: str) -> None:
        """Display text in the window with roll-up effect."""

        # Make sure the text is a string
        if not isinstance(text, str):
            typeTemp = type(text)
            text = str(text)

        # Append the new text to the end
        self.text_widget.append(text)

        # Scroll the end
        cursor = self.text_widget.textCursor()
        cursor.movePosition((QTextCursor.End))
        self.text_widget.setTextCursor(cursor)

    def clean_text(self) -> None:
        self.text_widget.clear()

    def close(self) -> None:
        super().close()


# Due to QT will stick uiautomation search, use a dicitonary to manage all QT object.
dictScreenPrintObj: dict[ScreenPrintObj, RealScreenPrintObj] = {}


def create_area(
    x: int = 0,
    y: int = 0,
    width: int = 400,
    height: int = 200,
    fontFamily: str = "Roboto Mono",
    fontSize: int = 16,
    fontColor: Literal["red", "green", "blue", "yellow", "purple", "pink", "black"] = "red",
) -> ScreenPrintObj:

    screenPrintObj: ScreenPrintObj = str(uuid.uuid4())  # type: ignore
    dictScreenPrintObj[screenPrintObj] = RealScreenPrintObj(
        x=x, y=y, width=width, height=height, fontFamily=fontFamily, fontSize=fontSize, fontColor=fontColor
    )

    dictScreenPrintObj[screenPrintObj].show()
    QApplication.processEvents()

    return screenPrintObj


def display_text(screenPrintObj: ScreenPrintObj, text: str) -> None:
    dictScreenPrintObj[screenPrintObj].display_text(text=text)
    QApplication.processEvents()


def clean_text(screenPrintObj: ScreenPrintObj) -> None:
    dictScreenPrintObj[screenPrintObj].clean_text()
    QApplication.processEvents()


def close_area(screenPrintObj: ScreenPrintObj) -> None:
    dictScreenPrintObj[screenPrintObj].close()
    QApplication.processEvents()

    del dictScreenPrintObj[screenPrintObj]


class TransparentOverlay(QWidget):
    def __init__(self, x, y, width, height, color="red", label: str = "") -> None:
        super().__init__()

        # Check if the specified color is one of the allowed values
        listColors = ["red", "green", "blue", "yellow", "purple", "pink", "black"]
        if color not in listColors:
            raise ValueError(f"color should be one of {listColors}")

        self.borderThickness = 4

        # Set up the label text
        self.label = label

        # Determine label width using a QFontMetrics
        font = QFont("Arial", 10)
        fontMetrics = QFontMetrics(font)
        intLabelWidth = fontMetrics.width(label) + 10  # Add padding to the label width

        # Ensure the widget is wide enough for the rectangle and the label
        intWidgetWidth = max(width + self.borderThickness * 2, intLabelWidth)

        # Set up the window flags for a frameless window and to keep it on top
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Set widget geometry to fit the label and rectangle
        self.setGeometry(
            x - self.borderThickness,
            y - self.borderThickness - 20,  # Add space above for the label
            intWidgetWidth,
            height + self.borderThickness * 2 + 20,  # Include label height
        )

        # Store rectangle geometry for drawing
        self.rectX = self.borderThickness
        self.rectY = self.borderThickness + 20  # Adjust for label space
        self.rectWidth = width
        self.rectWeight = height

        # Set up the border color and thickness
        self.border_color = QColor(color)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)

            # Draw the rectangle
            painter.setPen(QPen(self.border_color, self.borderThickness, Qt.SolidLine))
            rect = QRectF(
                self.rectX - (self.borderThickness // 2),
                self.rectY - (self.borderThickness // 2),
                self.rectWidth + self.borderThickness,
                self.rectWeight + self.borderThickness,
            )
            painter.drawRect(rect)

            # Draw the label
            if self.label:
                painter.setFont(QFont("Arial", 10))
                painter.setPen(QPen(self.border_color))
                label_rect = QRectF(
                    self.borderThickness // 2,
                    self.borderThickness // 2,
                    self.width() - self.borderThickness,  # Use widget's width for label
                    20,  # Height for the label
                )
                painter.drawText(label_rect, Qt.AlignLeft, self.label)
        finally:
            painter.end()


dictOverlayCache: dict[str, TransparentOverlay] = {}


def create_overlay(
    x: int, y: int, width: int, height: int, color: str = "red", duration: int = 1000, label: str = ""
) -> None:
    # print("Funciton create_overlay start")
    overlay = TransparentOverlay(x, y, width, height, color, label)
    overlay.show()

    # Store the overlay so it isn't garbage collected
    strId = str(uuid.uuid4())
    dictOverlayCache[strId] = overlay

    # Use a QTimer so the event loop can continue, and close the overlay later
    close_timer = QTimer(overlay)
    close_timer.setSingleShot(True)
    close_timer.setInterval(duration)  # duration is already in milliseconds
    close_timer.timeout.connect(lambda: _remove_overlay(strId))
    close_timer.start()
    # print("Funciton create_overlay done.")


def _remove_overlay(id: str) -> None:
    global dictOverlayCache
    dictOverlayCache[id].close()
    del dictOverlayCache[id]


def run_qt_worker(queueCommand: Queue, queueReturn: Queue) -> None:
    """
    This function runs in a separate process.
    It holds the Qt Event Loop, creates RealScreenPrintObj objects, etc.
    """

    # print(f"Run QtWorker in process: {current_process().name}")

    # Poll commands without blocking the PyQt event loop
    timer = QTimer()
    timer.setInterval(50)

    def poll_command() -> None:
        while True:
            try:
                dictCommand = queueCommand.get_nowait()  # may raise queue.Empty
            except Empty:
                # print("No command in queue.")
                break

            try:
                command: str = dictCommand["command"]
                data: dict[str, Any] = dictCommand["data"]
                requestId = dictCommand["requestId"]
                # print("command", command)
                match command:
                    case "create_area":
                        screenPrintObj: ScreenPrintObj = create_area(
                            x=data["x"],
                            y=data["y"],
                            width=data["width"],
                            height=data["height"],
                            fontFamily=data["fontFamily"],
                            fontSize=data["fontSize"],
                            fontColor=data["fontColor"],
                        )
                        queueReturn.put({"requestId": requestId, "result": screenPrintObj})

                    case "display_text":
                        display_text(screenPrintObj=data["screenPrintObj"], text=data["text"])
                        queueReturn.put({"requestId": requestId, "result": "OK"})

                    case "clean_text":
                        clean_text(screenPrintObj=data["screenPrintObj"])
                        queueReturn.put({"requestId": requestId, "result": "OK"})

                    case "close_area":
                        close_area(screenPrintObj=data["screenPrintObj"])
                        queueReturn.put({"requestId": requestId, "result": "OK"})

                    case "create_overlay":
                        create_overlay(
                            x=data["x"],
                            y=data["y"],
                            width=data["width"],
                            height=data["height"],
                            color=data["color"],
                            duration=data["duration"],
                            label=data["label"],
                        )
                        queueReturn.put({"requestId": requestId, "result": "OK"})

                    case "show_notification":
                        show_notification(title=data["title"], message=data["message"], duration=data["duration"])
                        queueReturn.put({"requestId": requestId, "result": "OK"})

                    case "quit":
                        # Quit the Qt event loop and exit the worker process.
                        queueReturn.put({"requestId": requestId, "result": "Quitting"})
                        qtApp.quit()
                        print("Quit QtWorker process.")
                        return None

                    case _:
                        queueReturn.put({"requestId": requestId, "error": f"Unknown command: {command}"})
            except Exception as e:
                queueReturn.put({"requestId": requestId, "error": str(get_exception_info(e))})

    timer.timeout.connect(poll_command)
    timer.start()

    # Start the Qt event loop
    qtApp.exec()


if __name__ == "__main__":
    ...
