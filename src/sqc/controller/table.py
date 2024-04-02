"""Controller classes for abstracting complex intrument communication."""

import logging
import queue
import threading
import time
from typing import Callable, Tuple, Optional
from functools import partial

from PyQt5 import QtCore

from ..core.timer import Timer
from ..core.request import Request
from ..settings import Settings

__all__ = ["TableController"]

logger = logging.getLogger(__name__)


class Table:  # TODO

    def __init__(self, driver) -> None:
        self.driver = driver
        self.poll_interval: float = .100
        self.safe_z_offset: float = 250.

    def identify(self) -> str:
        return self.driver.identification

    def configure(self) -> None:
        # Disable joystick
        self.driver.joystick = False
        # Make sure to use micro meter (1) units
        unit = self.driver.unit
        assert unit == (1, 1, 1, 1), f"Invalid table axis unit: {unit}"

    def set_accel(self, accel: int) -> None:
        self.driver.resource.write(f"{accel:d} setaccel")

    def set_vel(self, vel: int) -> None:
        self.driver.resource.write(f"{vel:d} setvel")

    def set_accelfunc(self, accelfunc: int) -> None:
        self.driver.resource.write(f"{accelfunc:d} setaccelfunc")

    def position(self) -> Tuple[float, float, float]:
        return self.driver.pos

    def move_relative(self, position, position_changed: Optional[Callable] = None) -> None:
        if not self.is_calibrated():
            raise RuntimeError("Table requires calibration.")
        x, y, z = position
        self.driver.rmove(x, y, z)  # non blocking
        self.wait_movement_finished(position_changed)

    def move_absolute(self, position, position_changed: Optional[Callable] = None) -> None:
        if not self.is_calibrated():
            raise RuntimeError("Table requires calibration.")
        x, y, z = position
        self.driver.move(x, y, z)  # non blocking
        self.wait_movement_finished(position_changed)

    def safe_move_absolute(self, position, position_changed: Optional[Callable] = None) -> None:
        if not self.is_calibrated():
            raise RuntimeError("Table requires calibration.")
        x, y, z = position
        pos = self.driver.pos
        self.driver.rmove(0, 0, -abs(self.safe_z_offset))  # non blocking
        self.wait_movement_finished(position_changed)
        pos = self.driver.pos
        self.driver.move(x, y, pos[2])  # non blocking
        self.wait_movement_finished(position_changed)
        pos = self.driver.pos
        self.driver.rmove(0, 0, z - abs(pos[2]))  # non blocking
        self.wait_movement_finished(position_changed)

    def safe_travel_absolute(self, position, position_changed: Optional[Callable] = None) -> None:
        if not self.is_calibrated():
            raise RuntimeError("Table requires calibration.")
        x, y, z = position
        pos = self.driver.pos
        self.driver.rmove(0, 0, -abs(pos[2]))  # non blocking
        self.wait_movement_finished(position_changed)
        self.driver.move(x, y, 0)  # non blocking
        self.wait_movement_finished(position_changed)
        self.driver.move(x, y, z)  # non blocking
        self.wait_movement_finished(position_changed)

    def wait_movement_finished(self, position_changed: Optional[Callable] = None) -> None:
        while True:
            time.sleep(self.poll_interval)
            pos = self.driver.pos
            if callable(position_changed):
                position_changed(pos)
            moving = self.driver.status & 0x1 == 0x1
            if not moving:
                break

    def set_joystick_enabled(self, enabled: bool) -> None:
        self.driver.joystick = enabled

    def is_calibrated(self) -> bool:
        if self.driver.x.caldone != 0x3:
            return False
        if self.driver.y.caldone != 0x3:
            return False
        if self.driver.x.caldone != 0x3:
            return False
        return True

    def calibrate_x(self) -> None:
        self.driver.x.ncal()
        self.wait_movement_finished()

    def calibrate_y(self) -> None:
        self.driver.y.ncal()
        self.wait_movement_finished()

    def calibrate_z(self) -> None:
        self.driver.z.ncal()
        self.wait_movement_finished()

    def range_measure_x(self) -> None:
        self.driver.x.nrm()
        self.wait_movement_finished()

    def range_measure_y(self) -> None:
        self.driver.y.nrm()
        self.wait_movement_finished()

    def range_measure_z(self) -> None:
        self.driver.z.nrm()
        self.wait_movement_finished()


class TableController(QtCore.QObject):

    positionChanged = QtCore.pyqtSignal(tuple)

    movementFinished = QtCore.pyqtSignal()

    progressChanged = QtCore.pyqtSignal(int, int)

    failed = QtCore.pyqtSignal(Exception)

    def __init__(self, station, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self.station = station
        self.abortRequested = False
        self._shutdown: threading.Event = threading.Event()
        self._queue: queue.Queue = queue.Queue()

        self._thread = threading.Thread(target=self.eventLoop)

    def start(self) -> None:
        self._thread.start()

    def eventLoop(self) -> None:
        while not self._shutdown.is_set():
            try:
                self.enterContext()
            except Exception as exc:
                logger.exception(exc)
                time.sleep(1.)
            time.sleep(.250)  # throttle

    def enterContext(self) -> None:
        try:
            self.station.open_resource("table")
            context = Table(self.station.get_resource("table"))
            while not self._shutdown.is_set():
                self.handleRequest(context)
        finally:
            self.station.close_resource("table")

    def handleRequest(self, context) -> None:
        try:
            request = self._queue.get(timeout=.250)
            self._queue.task_done()
        except queue.Empty:
            ...
        else:
            request(context)
            request.get()  # raise exceptions

    def shutdown(self) -> None:
        self._shutdown.set()
        self._thread.join()

    def requestAbort(self) -> None:
        self.abortRequested = True

    def applyProfile(self, name: str) -> None:
        def request(context):
            self.station.table_apply_profile(name)
        self._queue.put(Request(request))

    def requestPosition(self) -> None:
        def request(context):
            position = context.position()
            self.positionChanged.emit(position)
        self._queue.put(Request(request))

    def moveRelative(self, position) -> None:
        def request(context):
            try:
                context.move_relative(position, position_changed=self.positionChanged.emit)
            finally:
                self.movementFinished.emit()
        self._queue.put(Request(request))

    def moveAbsolute(self, position) -> None:
        def request(context):
            try:
                context.safe_move_absolute(position, position_changed=self.positionChanged.emit)
            finally:
                self.movementFinished.emit()
        self._queue.put(Request(request))

    def travelAbsolute(self, position) -> None:
        def request(context):
            try:
                context.safe_travel_absolute(position, position_changed=self.positionChanged.emit)
            finally:
                self.movementFinished.emit()
        self._queue.put(Request(request))

    def setJoystickEnabled(self, enabled: bool) -> None:
        def request(context):
            context.set_joystick_enabled(enabled)
        self._queue.put(Request(request))

    def requestCalibrate(self) -> None:
        def request(context):
            try:
                if not self.abortRequested:
                    self.progressChanged.emit(0, 6)
                    context.calibrate_z()
                if not self.abortRequested:
                    self.progressChanged.emit(1, 6)
                    context.calibrate_y()
                if not self.abortRequested:
                    self.progressChanged.emit(2, 6)
                    context.calibrate_x()
                if not self.abortRequested:
                    self.progressChanged.emit(3, 6)
                    context.range_measure_x()
                if not self.abortRequested:
                    self.progressChanged.emit(4, 6)
                    context.range_measure_y()
                if not self.abortRequested:
                    self.progressChanged.emit(5, 6)
                    context.range_measure_z()
                if not self.abortRequested:
                    self.progressChanged.emit(6, 6)
                    if not context.is_calibrated():
                        raise RuntimeError("failed to calibrate")
            finally:
                self.abortRequested = False
                self.movementFinished.emit()
        self._queue.put(Request(request))
