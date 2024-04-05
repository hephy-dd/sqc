"""Measurement sequence context."""

import logging
import threading
import time
from collections import Counter
from typing import Any, Callable, Dict, List, Optional

from PyQt5 import QtCore

from .station import Station
from .core.geometry import Padfile
from .core.geometry import load as load_padfile

__all__ = ["Context"]

logger = logging.getLogger(__name__)


def list_to_dict(items: list, sortkey: str) -> dict:
    return {item.get(sortkey): item for item in items}


def auto_insert_item(items, data, sortkey: str) -> List[Dict[str, Any]]:
    d = list_to_dict(items, sortkey)
    d[data.get(sortkey)] = data
    return sorted(d.values(), key=lambda item: item.get(sortkey, {}))


class AbortRequested(Exception): ...


class Statistics:

    def __init__(self) -> None:
        self.remeasure_counter: Dict[str, Counter] = {}
        self.recontact_counter: Dict[str, Counter] = {}

    def clear(self) -> None:
        self.remeasure_counter.clear()
        self.recontact_counter.clear()

    def increment_remeasure_counter(self, strip: str, name: str) -> None:
        self.remeasure_counter.setdefault(strip, Counter()).update([name])

    def increment_recontact_counter(self, strip: str, name: str) -> None:
        self.recontact_counter.setdefault(strip, Counter()).update([name])


class Context(QtCore.QObject):

    message_changed = QtCore.pyqtSignal(str)
    progress_changed = QtCore.pyqtSignal(int, int, int)

    bias_voltage_changed = QtCore.pyqtSignal(float)

    stripscan_progress_changed = QtCore.pyqtSignal(int, int)
    stripscan_estimation_changed = QtCore.pyqtSignal(object, object)

    current_item_changed = QtCore.pyqtSignal(object)
    item_state_changed = QtCore.pyqtSignal(object, object)
    item_enabled_changed = QtCore.pyqtSignal(object, bool)
    item_progress_changed = QtCore.pyqtSignal(object, int, int)

    current_strip_changed = QtCore.pyqtSignal(str)
    needle_position_changed = QtCore.pyqtSignal(str)
    data_changed = QtCore.pyqtSignal(str, str, str)
    statistics_changed = QtCore.pyqtSignal()

    suspended = QtCore.pyqtSignal()
    continued = QtCore.pyqtSignal()

    exception_raised = QtCore.pyqtSignal(Exception)

    def __init__(self, station: Station, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._station: Station = station
        self._padfile: Optional[Padfile] = None
        self._current_strip: str = ""
        self._writers: List = []
        self._parameters: Dict[str, Any] = {}
        self._data: Dict[str, Dict] = {}
        self._statistics: Statistics = Statistics()
        self._suspend_event: threading.Event = threading.Event()
        self._abort_event: threading.Event = threading.Event()
        self.environ_errors: int = 0
        self.auto_start_measurement: bool = False
        self.keep_light_flashing: bool = False  # TODO
        self.return_to_load_position: bool = False
        # Signals
        station.bias_voltage_changed.add(self.bias_voltage_changed.emit)

    @property
    def station(self) -> Station:
        return self._station

    def create_timestamp(self) -> None:
        self._parameters["timestamp"] = time.time()

    def reset(self) -> None:
        self._current_strip = ""
        self._suspend_event = threading.Event()
        self._abort_event = threading.Event()
        self.environ_errors = 0
        self.auto_start_measurement = False

    def reset_data(self) -> None:
        self._data = {}
        self._parameters["open_corrections"] = {}
        self._statistics = Statistics()

    def get_open_correction(self, namespace: str, type: str, name: str, key: str) -> float:
        open_corrections = self._parameters.get("open_corrections", {})
        return open_corrections.get(namespace, {}).get(type, {}).get(name, {}).get(key, 0.)

    def set_open_correction(self, namespace: str, type: str, name: str, key: str, value: float) -> None:
        open_corrections = self._parameters.setdefault("open_corrections", {})
        open_corrections.setdefault(namespace, {}).setdefault(type, {}).setdefault(name, {})[key] = value

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters

    @property
    def padfile(self) -> Optional[Padfile]:
        return self._padfile

    @property
    def current_strip(self) -> str:
        return self._current_strip

    # Events

    def set_current_strip(self, strip: Optional[str]) -> None:
        self._current_strip = strip or ""
        self.current_strip_changed.emit(self._current_strip)

    def set_needle_position(self, position: str) -> None:
        self.needle_position_changed.emit(position)

    def set_current_item(self, item: object) -> None:
        self.current_item_changed.emit(item)

    def set_item_state(self, item: object, state) -> None:
        self.item_state_changed.emit(item, state)

    def set_item_enabled(self, item: object, state) -> None:
        self.item_enabled_changed.emit(item, state)

    def set_item_progress(self, item: object, value: int, maximum: int) -> None:
        self.item_progress_changed.emit(item, value, maximum)

    def set_message(self, message: str) -> None:
        self.message_changed.emit(message)

    def set_progress(self, minimum: int, maximum: int, value: int) -> None:
        self.progress_changed.emit(minimum, maximum, value)

    def set_stripscan_progress(self, strip: int, strips: int) -> None:
        self.stripscan_progress_changed.emit(strip, strips)

    def set_stripscan_estimation(self, elapsed, remaining) -> None:
        self.stripscan_estimation_changed.emit(elapsed, remaining)

    # Data

    @property
    def data(self) -> Dict[str, Dict]:
        return self._data

    def insert_data(self, namespace: str, type: str, name: str, data: dict, sortkey: str) -> None:
        items: Dict[str, Dict] = self._data.setdefault(namespace, {}).setdefault(type, {}).get(name, [])
        self._data.setdefault(namespace, {}).setdefault(type, {})[name] = auto_insert_item(items, data, sortkey=sortkey)
        logger.debug("inserted data: namespace=%r, type=%r, name=%r, data=%r", namespace, type, name, data)
        self.data_changed.emit(namespace, type, name)

    # Statistics

    @property
    def statistics(self) -> Statistics:
        return self._statistics

    # Writer

    @property
    def writers(self) -> List:
        return self._writers.copy()


    def add_writer(self, writer) -> None:
        if writer not in self._writers:
            self._writers.append(writer)

    # Suspend

    @property
    def is_suspend_requested(self) -> bool:
        return self._suspend_event.is_set()

    def request_suspend(self) -> None:
        self._suspend_event.set()

    def request_continue(self) -> None:
        self._suspend_event = threading.Event()

    def handle_suspend(self) -> None:
        self.suspended.emit()
        try:
            while self._suspend_event.wait(timeout=0.025):
                if self._abort_event.is_set():
                    break
        finally:
            self.continued.emit()

    # Abort

    @property
    def is_abort_requested(self) -> bool:
        return self._abort_event.is_set()

    def request_abort(self) -> None:
        self._abort_event.set()

    def handle_abort(self) -> None:
        if self._abort_event.is_set():
            raise AbortRequested

    # Exceptions

    def handle_exception(self, exc: Exception) -> None:
        self.exception_raised.emit(exc)

    # Wait

    def snooze(self, seconds: float) -> None:
        cv = threading.Condition()
        with cv:
            cv.wait_for(self._abort_event.is_set, timeout=seconds)

    # Padfile

    def load_padfile(self, filename: str) -> None:
        geometry: Dict[str, Any] = {}
        self._parameters.update({"geometry": geometry})
        try:
            with open(filename) as fp:
                padfile = load_padfile(fp)
                self._padfile = padfile
        except Exception as exc:
            logger.exception(exc)
            self.handle_exception(exc)
        else:
            properties = {key: value for key, value in padfile.properties.items()}
            strips = list(padfile.pads.keys())
            geometry.update({
                "properties": properties,
                "strips": strips,
            })
