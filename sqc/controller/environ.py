import copy
import logging
import queue
import threading
import time

from PyQt5 import QtCore

from ..core.resource import create_driver
from ..core.timer import Timer
from ..core.request import Request
from ..settings import Settings

__all__ = ["EnvironController"]

logger = logging.getLogger(__name__)


class EnvironController(QtCore.QObject):

    dataChanged = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.interval = 2.0
        self.dataChanged.connect(self._pc_data_available)

        self._data = {}
        self._shutdown = threading.Event()
        self._queue = queue.Queue()

        self._lock: threading.RLock = threading.RLock()
        self._thread: threading.Thread = threading.Thread(target=self.eventLoop)

    def reset(self) -> None:
        with self._lock:
            self._data.clear()

    def start(self) -> None:
        logger.info("Starting environ worker...")
        self._thread.start()

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data)

    def _pc_data(self, resource):
        data = resource.get_data()
        logger.debug("Environment data: %s", data)
        self.dataChanged.emit(data)

    def _pc_data_available(self, data):
        with self._lock:
            self._data.update(data)

    def get_box_door_state(self) -> bool:
        request = Request(lambda res: res.get_box_door_state())
        self._queue.put(request)
        return request.get()

    # Box luminosity

    def get_box_lux(self) -> bool:
        request = Request(lambda res: res.get_box_lux())
        self._queue.put(request)
        return request.get()

    # Box light

    def get_box_light_state(self) -> bool:
        request = Request(lambda res: res.get_box_light())
        self._queue.put(request)
        return request.get()

    def set_box_light_state(self, state: bool) -> None:
        request = Request(lambda res, state=state: res.set_box_light(state))
        self._queue.put(request)
        request.get()

    # Microscope light

    def get_microscope_light_state(self) -> bool:
        request = Request(lambda res: res.get_microscope_light())
        self._queue.put(request)
        return request.get()

    def set_microscope_light_state(self, state: bool) -> None:
        request = Request(lambda res, state=state: res.set_microscope_light(state))
        self._queue.put(request)
        request.get()

    # Discarge capacitor

    def set_discharge(self, state: bool) -> None:
        request = Request(lambda res, state=state: res.set_discharge(state))
        self._queue.put(request)
        request.get()

    def eventLoop(self) -> None:
        t = Timer()
        while not self._shutdown.is_set():
            try:
                with Settings().createResource("environ") as res:
                    while not self._shutdown.is_set():
                        self.handleRequest(create_driver(res.model)(res))
                        if t.delta() > self.interval:
                            self._queue.put(self._pc_data)
                            t.reset()
            except Exception as exc:
                self.reset()
                logger.exception(exc)
                time.sleep(4.0)

    def handleRequest(self, resource) -> None:
        try:
            request = self._queue.get(timeout=0.025)
            self._queue.task_done()
            logger.debug("environ.dispatch: %s", request)
            request(resource)
        except queue.Empty:
            ...

    def shutdown(self) -> None:
        logger.info("Shutting down environ worker...")
        self._shutdown.set()
        self._thread.join()
