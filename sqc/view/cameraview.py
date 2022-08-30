import time
from typing import Callable, Dict

from PyQt5 import QtCore, QtGui, QtWidgets

__all__ = ["camera_registry", "CameraScene", "CameraView"]

camera_registry: Dict[str, Callable] = {}


class CameraScene(QtWidgets.QGraphicsScene):

    imageChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._timestamp = time.monotonic()
        self._image = QtGui.QImage()
        self._factor = 1.0
        self._centerX = 0.5
        self._centerY = 0.5
        self._fps = 0
        self.imageChanged.connect(self.update)

    def image(self) -> QtGui.QImage:
        return self._image

    def setImage(self, image: QtGui.QImage) -> None:
        self._image = image
        self.updateFps()
        self.imageChanged.emit()

    def updateFps(self):
        t = time.monotonic()
        try:
            dt = t - self._timestamp
        except ZeroDivisionError:
            dt = 1.
        self._fps = abs(1. / dt)
        self._timestamp = t

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
            scaledImage = croppedImage.scaled(rect.width(), rect.height(), QtCore.Qt.KeepAspectRatio)
            xOffset = int((rect.width() - scaledImage.width()) / 2)
            yOffset = int((rect.height() - scaledImage.height()) / 2)
            painter.drawImage(rect.x() + xOffset, rect.y() + yOffset, scaledImage)

        self.drawFpsCounter(painter, rect)

    def drawFpsCounter(self, painter, rect) -> None:
        # font
        font = painter.font()
        font.setPixelSize(24)
        painter.setFont(font)
        # color
        painter.setPen(QtCore.Qt.yellow)
        # text
        pos = QtCore.QPoint(rect.x() + 10, rect.y() + 34)
        painter.drawText(pos, f"{self._fps:.1f} fps")


class CameraView(QtWidgets.QGraphicsView):

    def __init__(self, scene, parent=None) -> None:
        super().__init__(parent)
        self.setScene(scene)
        self.scene().setSceneRect(self.scene().itemsBoundingRect())

    def createImage(self, data):
        return QtGui.QImage(
            data,
            data.shape[1],
            data.shape[0],
            data.strides[0],
            QtGui.QImage.Format_RGB888,
        )

    def handle(self, image_data):
        data = image_data.as_1d_image()
        image_data.unlock()
        scene = self.scene()
        if scene:
            image = self.createImage(data)
            scene.setImage(image)
