# FileName: _Screenshot.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from PyQt5 import QtWidgets, QtCore, QtGui
import os
import inspect
import subprocess


SCREENSHOT_DOCUMENTS_PATH = os.path.join(os.environ.get("USERPROFILE", "N/A"), R"Documents\LiberRPA\Screenshot")
os.makedirs(name=SCREENSHOT_DOCUMENTS_PATH, exist_ok=True)
FULL_SCREENSHOT_PATH = os.path.join(SCREENSHOT_DOCUMENTS_PATH, "LiberRPA_full_screenshot.png")
SCREENSHOT_PROJECT_PATH = os.path.join(os.getcwd(), "Screenshot")
SCREENSHOT_TEMP_NAME = "captured_temp.png"

SELECTED_KEYWORD = "Save completed!"


class ScreenshotCapture(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()

        # Capture all screens and combine them into one large pixmap with correct positioning
        temp = capture_all_screen(needImage=True)
        self.pixmapScreenshot: QtGui.QPixmap = temp[0]  # type: ignore
        self.intMinX = temp[1]
        self.intMinY = temp[2]
        print("intMinX=" + str(self.intMinX) + ", intMinY=" + str(self.intMinY))

        # Create a QLabel to display the combined screenshot
        self.label = QtWidgets.QLabel(self)
        self.label.setPixmap(self.pixmapScreenshot)

        # Set the size of the widget to cover the entire virtual desktop
        self.setGeometry(self.pixmapScreenshot.rect())

        # Move the window to the top-left of the virtual desktop (even if it's not the main screen)
        # Make sure to call move before calling showFullScreen() to properly place the window
        self.move(self.intMinX, self.intMinY)
        # Set the window flags to make the window borderless
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        # Show it.
        self.show()

        # Variables to store the start and end points of the rectangle
        self.origin = None
        self.rubberBand = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            # Get the starting point of the rectangle
            self.origin = event.pos()
            self.rubberBand.setGeometry(QtCore.QRect(self.origin, QtCore.QSize()))
            self.rubberBand.show()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        # Update the rectangle size
        if self.origin is not None:
            self.rubberBand.setGeometry(QtCore.QRect(self.origin, event.pos()).normalized())

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton:
            self.rubberBand.hide()
            # Capture the rectangle's coordinates
            rect = self.rubberBand.geometry()
            self.save_cropped_image(rect)

    def save_cropped_image(self, rect: QtCore.QRect):
        # Crop the selected region and save it as a PNG
        cropped_pixmap = self.pixmapScreenshot.copy(rect)
        cropped_pixmap.save(os.path.join(SCREENSHOT_DOCUMENTS_PATH, SCREENSHOT_TEMP_NAME), "PNG")
        print(SELECTED_KEYWORD)
        self.close()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == QtCore.Qt.Key_Escape:
            print("ESC pressed, exiting.")
            self.close()


def capture_all_screen(needImage: bool = False) -> tuple[QtGui.QPixmap | None, int, int]:
    """
    Returns (combinedPixmap, minX, minY)
    and also writes the full screenshot to FULL_SCREENSHOT_PATH

    Use needImage to control whether return QtGui.QPixmap because can't pickle it in Queue and the MainPrcess didn't need it.
    """

    # Create qtApp in the current process.
    qtApp = QtWidgets.QApplication.instance()
    if not qtApp:
        qtApp = QtWidgets.QApplication([])

    screens: list[QtGui.QScreen] = QtWidgets.QApplication.screens()
    if not screens:
        raise RuntimeError("No screens found.")

    # Get the bounds of the virtual desktop space
    intMinX = min(screen.geometry().x() for screen in screens)
    intMinY = min(screen.geometry().y() for screen in screens)
    intMaxX = max(screen.geometry().x() + screen.geometry().width() for screen in screens)
    intMaxY = max(screen.geometry().y() + screen.geometry().height() for screen in screens)

    # Calculate total width and height of the virtual desktop
    intTotalWidth = intMaxX - intMinX
    intTotalHeight = intMaxY - intMinY

    # Create a QPixmap to hold the combined screenshot
    pixmapCombined = QtGui.QPixmap(intTotalWidth, intTotalHeight)
    # Fill with transparency for unused areas
    pixmapCombined.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmapCombined)

    try:
        # Add a border around the screenshot to indicate that it’s not the real screen.
        # Set the pen color to green and the thickness to 4px
        pen = QtGui.QPen(QtCore.Qt.green)
        pen.setWidth(4)
        painter.setPen(pen)

        # Capture each screen and paint it onto the combined QPixmap at the correct position
        for screen in screens:
            geometry = screen.geometry()
            pixmap = screen.grabWindow(0)  # type: ignore - use QtWidgets.QApplication.desktop().winId() will not show error but it can't get the right whole screen.
            # Draw the screenshot at the correct position based on the monitor's geometry
            painter.drawPixmap(geometry.x() - intMinX, geometry.y() - intMinY, pixmap)

            # Draw the green border inside each screen (4px border)
            painter.drawRect(
                geometry.x() - intMinX + 2,
                geometry.y() - intMinY + 2,
                geometry.width() - 4,
                geometry.height() - 4,
            )

        # Save the screenshot into the specified folder.
        if pixmapCombined.save(FULL_SCREENSHOT_PATH, "PNG") == False:
            raise RuntimeError("Failed to save the full screenshot.")

        # Also return the top-left corner of the entire virtual desktop to draw it later.
        if needImage:
            return (pixmapCombined, intMinX, intMinY)
        else:
            return (None, intMinX, intMinY)
    finally:
        painter.end()


def _create_screenshot_manually() -> None:
    print("create_screenshot_manually start.")
    qtApp = QtWidgets.QApplication.instance()
    if not qtApp:
        qtApp = QtWidgets.QApplication([])

    # Create the screenshot capture window
    captureWindow = ScreenshotCapture()

    captureWindow.show()

    qtApp.exec()

    # At this point, the user has selected an area or pressed ESC
    print("create_screenshot_manually done.")


def create_screenshot_manually() -> bool | None:
    # Because QT can't work finely with Flask, use subprocess to run the file in a isolate environment.
    strFilePath = inspect.stack()[0].filename
    result = subprocess.run(["python", strFilePath], shell=True, capture_output=True, text=True)
    print("-" * 40)
    print(result.stdout)
    print(result.stderr)
    print("-" * 40)

    if result.stdout.find(SELECTED_KEYWORD) != -1:
        return True
    return None


if __name__ == "__main__":
    # NOTE: Not modify here for unittesting, because it will be invoke as a file in subprocess.run
    _create_screenshot_manually()
