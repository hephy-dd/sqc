"""Controller classes for abstracting complex intrument communication."""

import logging
import queue
import threading
import time
from typing import Any, Tuple
from functools import partial

from PyQt5 import QtCore

from ..core.timer import Timer
from ..core.request import RequestHandler
from ..settings import Settings

__all__ = ["TableController"]

logger = logging.getLogger(__name__)


class Table:  # TODO

    def __init__(self, driver) -> None:
        self.driver = driver
        self.poll_timeout = 60.
        self.poll_interval = .100
        self.safe_z_offset = 250.

    def identify(self) -> str:
        return self.driver.identification

    def configure(self) -> None:
        # Disable joystick
        self.driver.joystick = False
        # MAke sure to use micro meter (1) units
        unit = self.driver.unit
        assert unit == (1, 1, 1, 1), f"Invalid table exis unit: {unit}"

    def position(self) -> Tuple[float, float, float]:
        return self.driver.pos

    def move_relative(self, position, position_changed=None) -> None:
        x, y, z = position
        self.driver.rmove(x, y, z)  # non blocking
        self.wait_movement_finished(position_changed)

    def safe_move_absolute(self, position, position_changed=None) -> None:
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

    def wait_movement_finished(self, position_changed=None) -> None:
        t = Timer()
        pos = [self.driver.pos]
        while True:
            if t.delta() > self.poll_timeout:
                raise RuntimeError("Table movement timeout.")
            time.sleep(self.poll_interval)
            pos.append(self.driver.pos)
            if callable(position_changed):
                position_changed(pos[-1])
            # if position not changed movement has finished
            if pos[0] == pos[1]:
                break
            pos.pop(0)

    def set_joystick_enabled(self, enabled: bool) -> None:
        self.driver.joystick = enabled


class TableContext:

    def __init__(self, station):
        self.station = station

    def __enter__(self):
        self.station.open_resource("table")
        return Table(self.station.get_resource("table"))

    def __exit__(self, *exc):
        self.station.close_resource("table")
        return False


class TableController(QtCore.QObject):

    positionChanged = QtCore.pyqtSignal(tuple)

    movementFinished = QtCore.pyqtSignal()

    failed = QtCore.pyqtSignal(Exception)

    def __init__(self, station, parent=None) -> None:
        super().__init__(parent)
        self.handler = RequestHandler(TableContext(station))

    def start(self) -> None:
        self.handler.start()

    def shutdown(self) -> None:
        self.handler.shutdown()

    # Requests

    def requestPosition(self) -> None:
        def request(context):
            position = context.position()
            self.positionChanged.emit(position)
        self.handler.submit(request)

    def moveRelative(self, position) -> None:
        def request(context):
            try:
                context.move_relative(position, position_changed=self.positionChanged.emit)
            finally:
                self.movementFinished.emit()
        self.handler.submit(request)

    def moveAbsolute(self, position) -> None:
        def request(context):
            try:
                context.safe_move_absolute(position, position_changed=self.positionChanged.emit)
            finally:
                self.movementFinished.emit()
        self.handler.submit(request)

    def setJoystickEnabled(self, enabled: bool) -> None:
        def request(context):
            context.set_joystick_enabled(enabled)
        self.handler.submit(request)
