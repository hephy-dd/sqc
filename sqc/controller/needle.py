"""Controller classes for abstracting complex intrument communication."""

import logging
import queue
import threading

from PyQt5 import QtCore

from ..core.request import Request

__all__ = ["NeedleController"]

logger = logging.getLogger(__name__)


class NeedleController(QtCore.QObject):

    positionChanged = QtCore.pyqtSignal(float)

    movementFinished = QtCore.pyqtSignal()

    progressChanged = QtCore.pyqtSignal(int, int)

    failed = QtCore.pyqtSignal(Exception)

    def __init__(self, station, parent=None) -> None:
        super().__init__(parent)
        self.station = station
        self.abortRequested = False
        self._queue: queue.Queue = queue.Queue()
        self._shutdown = threading.Event()
        self._thread = threading.Thread(target=self.eventLoop)

    def start(self) -> None:
        self._thread.start()

    def eventLoop(self) -> None:
        self.station.open_resource("tango")
        while not self._shutdown.is_set():
            try:
                self.handleEvent()
            except Exception as exc:
                logger.exception(exc)
                self.failed.emit(exc)
        self.station.close_resource("tango")

    def handleEvent(self) -> None:
        try:
            request = self._queue.get(timeout=.250)
            self._queue.task_done()
        except queue.Empty:
            ...
        else:
            request()
            request.get()  # raise exceptions

    def shutdown(self) -> None:
        self._shutdown.set()
        self._thread.join()

    def requestAbort(self) -> None:
        self.abortRequested = True

    def requestMoveUp(self) -> None:
        self._queue.put(Request(self.moveUp))

    def requestMoveDown(self) -> None:
        self._queue.put(Request(self.moveDown))

    def requestCalibrate(self) -> None:
        self._queue.put(Request(self.calibrate))

    def moveUp(self) -> None:
        try:
            self.station.needles_up()
        finally:
            self.movementFinished.emit()

    def moveDown(self) -> None:
        try:
            self.station.needles_down()
        finally:
            self.movementFinished.emit()

    def calibrate(self) -> None:
        try:
            if not self.abortRequested:
                self.progressChanged.emit(0, 4)
                self.station.needles_calibrate()
            if not self.abortRequested:
                self.progressChanged.emit(1, 4)
                self.station.needles_range_measure()
            if not self.abortRequested:
                self.progressChanged.emit(2, 4)
                self.station.needles_verify_calibration()
            if not self.abortRequested:
                self.progressChanged.emit(3, 4)
                self.station.needles_down()
                self.progressChanged.emit(4, 4)
        finally:
            self.abortRequested = False
            self.movementFinished.emit()

    def diagnose(self) -> str:
        return self.station.needles_diagnose()
