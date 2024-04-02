import time
from collections import deque
from typing import Callable, Dict

from PyQt5 import QtCore, QtGui, QtWidgets

__all__ = ["CameraScene", "CameraView"]


class FPSCounter:
    def __init__(self, averaging_period=5.0):
        """
        Initialize the FPS counter.

        :param averaging_period: Time period (in seconds) over which to average the FPS.
        """
        self.averaging_period = averaging_period
        self.timestamps = deque()

    def tick(self):
        """
        Call this method once for each frame.
        """
        current_time = time.time()
        self.timestamps.append(current_time)

        # Remove timestamps outside of the averaging period
        while self.timestamps and (current_time - self.timestamps[0]) > self.averaging_period:
            self.timestamps.popleft()

    @property
    def fps(self) -> float:
        """
        Get the current average FPS.

        :return: Average FPS over the defined period.
        """
        if not self.timestamps:
            return 0.0
        time_elapsed = self.timestamps[-1] - self.timestamps[0]
        if time_elapsed == 0:
            return 0.0
        return len(self.timestamps) / time_elapsed


class CameraScene(QtWidgets.QGraphicsScene):

    imageChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._image = QtGui.QImage()
        self._factor = 1.0
        self._centerX = 0.5
        self._centerY = 0.5
        self.fps_counter = FPSCounter()
        self.imageChanged.connect(self.update)

    def image(self) -> QtGui.QImage:
        return self._image

    def setImage(self, image: QtGui.QImage) -> None:
        self._image = image
        self.fps_counter.tick()
        self.imageChanged.emit()

    def factor(self) -> float:
        return self._factor

    def setFactor(self, factor: float) -> None:
        self._factor = factor

    def centerX(self) -> float:
        return self._centerX

    def centerY(self) -> float:
        return self._centerY

    def setCenter(self, x: float, y: float) -> None:
        self._centerX = x
        self._centerY = y

    def drawBackground(self, painter, rect) -> None:
        painter.fillRect(rect, QtCore.Qt.black)
        image = self.image()

        if image.isNull():
            import random
            image = QtGui.QImage(32, 32, QtGui.QImage.Format_RGB16)
            for x in range(32):
                for y in range(32):
                    image.setPixelColor(x, y, QtGui.QColor(0, 0, int(random.uniform(0, 255))))

        if not image.isNull():
            factor = self.factor()
            if factor == 1.0:
                centerX = 0.5
                centerY = 0.5
            else:
                centerX = self.centerX()
                centerY = self.centerY()
            width = int(image.width() / factor)
            height = int(image.height() / factor)
            x = int(image.width() * centerX - width / 2)
            y = int(image.height() * centerY - height / 2)
            croppedImage = image.copy(x, y, width, height)
            scaledImage = croppedImage.scaled(int(rect.width()), int(rect.height()), QtCore.Qt.KeepAspectRatio)
            xOffset = int((rect.width() - scaledImage.width()) / 2)
            yOffset = int((rect.height() - scaledImage.height()) / 2)
            painter.drawImage(int(rect.x()) + xOffset, int(rect.y()) + yOffset, scaledImage)

        self.drawFpsCounter(painter, rect)

    def drawFpsCounter(self, painter, rect) -> None:
        # font
        font = painter.font()
        font.setPixelSize(24)
        painter.setFont(font)
        # color
        painter.setPen(QtCore.Qt.yellow)
        # text
        pos = QtCore.QPoint(int(rect.x()) + 10, int(rect.y()) + 34)
        painter.drawText(pos, f"{self.fps_counter.fps:.1f} fps")


class CameraView(QtWidgets.QGraphicsView):

    def __init__(self, scene, parent=None) -> None:
        super().__init__(parent)
        self.setScene(scene)
        self.scene().setSceneRect(self.scene().itemsBoundingRect())

    def createImage(self, image_data):
        """Creates image from array in format RGB888."""
        return QtGui.QImage(
            image_data,
            image_data.shape[1],
            image_data.shape[0],
            image_data.strides[0],
            QtGui.QImage.Format_RGB888,
        )

    def handle(self, image_data):
        scene = self.scene()
        if scene:
            image = self.createImage(image_data)
            scene.setImage(image)
