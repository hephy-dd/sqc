"""Controller classes for abstracting complex intrument communication."""

import logging
import queue
import threading

from PyQt5 import QtCore

from ..core.request import RequestHandler

__all__ = ["NeedleController"]

logger = logging.getLogger(__name__)


class NeedleContext:

    def __init__(self, station):
        self.station = station

    def __enter__(self):
        self.station.open_resource("tango")
        return self.station

    def __exit__(self, *exc):
        self.station.close_resource("tango")
        return False


class NeedleController(QtCore.QObject):

    positionChanged = QtCore.pyqtSignal(float)

    movementFinished = QtCore.pyqtSignal()

    failed = QtCore.pyqtSignal(Exception)

    def __init__(self, station, parent=None) -> None:
        super().__init__(parent)
        self.handler = RequestHandler(NeedleContext(station))
        self.station = station
        self.positionChanged.connect(lambda pos: logger.info("Tango pos: %s", pos))

    def start(self) -> None:
        self.handler.start()

    def shutdown(self) -> None:
        self.handler.shutdown()

    # Requests

    def requestMoveUp(self) -> None:
        self.handler.submit(lambda context: self.moveUp())

    def requestMoveDown(self) -> None:
        self.handler.submit(lambda context: self.moveDown())

    def moveUp(self) -> None:
        try:
            self.station.needles_up()
            1/0
        finally:
            self.movementFinished.emit()

    def moveDown(self) -> None:
        try:
            self.station.needles_down()
        finally:
            self.movementFinished.emit()
