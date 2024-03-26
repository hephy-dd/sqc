import logging
import threading
from typing import Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from ..core.utils import parse_strip_expression, normalize_strip_expression
from ..strategy import SequenceStrategy

__all__ = [
    "SequenceItem",
    "SequenceWidget",
    "SequenceController"
]

logger = logging.getLogger(__name__)


def loadSequenceItems(sequence):
    items = []
    for measurement in sequence.get("measurements", []):
        item = SequenceItem()
        item.setTypeName(measurement.get("type"))
        item.setName(measurement.get("name"))
        item.setEnabled(measurement.get("enabled", True))
        item.setAutoDisable(measurement.get("auto_disable", True))
        item.setNamespace(measurement.get("namespace", ""))
        item.setDefaultStrips(measurement.get("strips", ""))
        item.setStrips(measurement.get("strips", ""))
        item.setParameters(measurement.get("parameters", {}))
        for child in loadStripItems(measurement.get("strip_measurements", [])):
            item.addChild(child)
        items.append(item)
    return items


def loadStripItems(measurements):
    items = []
    for measurement in measurements:
        item = SequenceItem()
        item.setTypeName(measurement.get("type"))
        item.setName(measurement.get("name"))
        item.setEnabled(measurement.get("enabled", True))
        item.setDefaultInterval(measurement.get("interval", 1))
        item.setInterval(measurement.get("interval", 1))
        item.setParameters(measurement.get("parameters", {}))
        items.append(item)
    return items


class SequenceItemState:
    """Represents a sequence item state with name and color."""

    def __init__(self, name: str, color: str) -> None:
        self.name: str = name
        self.color: str = color

    def __str__(self) -> str:
        return format(self.name)


class SequenceItem(QtWidgets.QTreeWidgetItem):

    NameColumn: int = 0
    StripsColumn: int = 1
    IntervalColumn: int = 2
    StateColumn: int = 3

    PendingState: SequenceItemState = SequenceItemState("Pending", "grey")
    IgnoredState: SequenceItemState = SequenceItemState("Ignored", "grey")
    ActiveState: SequenceItemState = SequenceItemState("Active", "blue")
    HaltedState: SequenceItemState = SequenceItemState("Halted", "blue")
    SuccessState: SequenceItemState = SequenceItemState("Success", "green")
    AbortedState: SequenceItemState = SequenceItemState("Aborted", "red")
    ComplianceState: SequenceItemState = SequenceItemState("Compliance", "red")
    FailedState: SequenceItemState = SequenceItemState("Failed", "red")

    def __init__(self) -> None:
        super().__init__()
        self.setLocked(False)
        self.setEnabled(True)
        self.setAutoDisable(True)
        self.setTypeName("")
        self.setNamespace("")
        self.setName("")
        self.setDefaultStrips("")
        self.setDefaultInterval(0)
        self.setStrips("")
        self.setInterval(0)
        self.setProgress(0, 0)
        self.setState(type(self).PendingState)
        self.setParameters({})

    def isLocked(self) -> bool:
        return self._locked

    def setLocked(self, state: bool) -> None:
        self._locked = state
        if state:
            self.setFlags(self.flags() & ~QtCore.Qt.ItemIsUserCheckable)
        else:
            self.setFlags(self.flags() | QtCore.Qt.ItemIsUserCheckable)
        for child in self.allChildren():
            child.setLocked(state)

    def isEnabled(self) -> bool:
        return self.checkState(type(self).NameColumn) == QtCore.Qt.Checked

    def setEnabled(self, enabled: bool) -> None:
        state = QtCore.Qt.Checked if enabled else QtCore.Qt.Unchecked
        self.setCheckState(type(self).NameColumn, state)

    def isAutoDisable(self) -> bool:
        return self._autoDisable

    def setAutoDisable(self, enabled: bool) -> None:
        self._autoDisable = enabled

    def typeName(self) -> str:
        return self._type

    def setTypeName(self, type: str) -> None:
        self._type = type

    def namespace(self) -> str:
        return self._namespace

    def setNamespace(self, namespace: str) -> None:
        self._namespace = namespace

    def name(self) -> str:
        return self._name

    def setName(self, name: str) -> None:
        self._name = name
        self.setText(type(self).NameColumn, name)

    def fullName(self) -> str:
        item = self
        names = [item.name()]
        while item.parent():
            item = item.parent()  # type: ignore
            names.insert(0, item.name())
        return "/".join(names)

    def key(self) -> str:
        return "/".join([self.namespace(), self.typeName(), self.fullName()])

    def strips(self) -> str:
        return self._strips

    def setStrips(self, strips: str) -> None:
        self._strips = strips
        column = type(self).StripsColumn
        self.setText(column, strips)
        if strips == self.defaultStrips():
            brush = QtGui.QBrush()
        else:
            brush = QtGui.QBrush(QtGui.QColor("yellow"))
        self.setBackground(column, brush)

    def defaultStrips(self) -> str:
        return self._defaultStrips

    def setDefaultStrips(self, strips: str) -> None:
        self._defaultStrips = strips

    def interval(self) -> int:
        return self._interval

    def setInterval(self, interval: int) -> None:
        self._interval = interval
        column = type(self).IntervalColumn
        self.setText(column, format(interval or ""))
        if interval == self.defaultInterval():
            brush = QtGui.QBrush()
        else:
            brush = QtGui.QBrush(QtGui.QColor("yellow"))
        self.setBackground(column, brush)

    def defaultInterval(self) -> int:
        return self._defaultInterval

    def setDefaultInterval(self, interval: int) -> None:
        self._defaultInterval = interval

    def progress(self) -> Tuple[int, int]:
        return self._progress

    def setProgress(self, value: int, maximum: int) -> None:
        self._progress = value, maximum

    def state(self) -> SequenceItemState:
        return self._state

    def setState(self, state: SequenceItemState) -> None:
        self._state = state
        name = state.name
        try:
            value, maximum = self._progress
            if maximum and maximum >= value:
                name = f"{name} ({value}/{maximum})"
        except Exception:
            ...
        column = type(self).StateColumn
        self.setText(column, name)
        color = QtGui.QBrush(QtGui.QColor(state.color))
        self.setForeground(column, color)

    def parameters(self) -> dict:
        return self._parameters.copy()

    def setParameters(self, parameters: dict) -> None:
        self._parameters = parameters

    def allChildren(self) -> list:
        items = []
        for index in range(self.childCount()):
            item = self.child(index)
            items.append(item)
        return items


class SequenceWidget(QtWidgets.QTreeWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLocked(False)
        headerItem = QtWidgets.QTreeWidgetItem()
        headerItem.setText(SequenceItem.NameColumn, "Measurement")
        headerItem.setText(SequenceItem.StripsColumn, "Strips")
        headerItem.setText(SequenceItem.IntervalColumn, "Interval")
        headerItem.setText(SequenceItem.StateColumn, "State")
        self.setHeaderItem(headerItem)
        self.setAlternatingRowColors(True)
        self.setExpandsOnDoubleClick(False)
        self.itemDoubleClicked.connect(self.editItem)

    def showEditStripsDialog(self, item: SequenceItem) -> Optional[str]:
        value, success = QtWidgets.QInputDialog.getText(self, item.fullName(),
            "Strips", text=item.strips())
        return value if success else None

    def showEditIntervalDialog(self, item: SequenceItem) -> Optional[int]:
        value, success = QtWidgets.QInputDialog.getInt(self, item.fullName(),
            "Interval", value=item.interval(), min=1)
        return value if success else None

    def editItemStrips(self, item):
        if item.allChildren():
            strips = self.showEditStripsDialog(item)
            if strips is not None:
                strips = normalize_strip_expression(strips)
                try:
                    parse_strip_expression(strips)
                except Exception as exc:
                    QtWidgets.QMessageBox.warning(self, "Invalid strips", f"Invalid strips: {strips} ({exc})")
                else:
                    item.setStrips(strips)

    def editItemInterval(self, item):
        if item.interval():
            interval = self.showEditIntervalDialog(item)
            if interval is not None:
                item.setInterval(interval)

    def editItem(self, item, column):
        if not self.isLocked():
            if column == SequenceItem.StripsColumn:
                self.editItemStrips(item)
            if column == SequenceItem.IntervalColumn:
                self.editItemInterval(item)

    def isLocked(self):
        return self.property("locked")

    def setLocked(self, state):
        self.setProperty("locked", state)
        for item in self.allItems():
            item.setLocked(state)

    def resizeColumns(self):
        self.resizeColumnToContents(SequenceItem.NameColumn)
        self.resizeColumnToContents(SequenceItem.IntervalColumn)

    def addSequenceItem(self, item):
        self.addTopLevelItem(item)
        item.setExpanded(True)

    def allItems(self):
        items = []
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            items.append(item)
        return items

    def contextMenuEvent(self, event):
        if self.isLocked():
            return

        item = self.itemAt(event.pos())

        if isinstance(item, SequenceItem):
            menu = QtWidgets.QMenu()

            restoreStripsAction = menu.addAction("Default Strips")
            restoreStripsAction.setEnabled(False)
            restoreStripsAction.setToolTip("Restore default strips from config for selected measurement")

            menu.addSeparator()

            restoreIntervalsAction = menu.addAction("Default Intervals")
            restoreIntervalsAction.setEnabled(False)
            restoreIntervalsAction.setToolTip("Restore default intervals from config for selected measurement")

            resetIntervalsAction = menu.addAction("Reset Intervals")
            resetIntervalsAction.setEnabled(False)
            resetIntervalsAction.setToolTip("Reset intervals to 1 for selected measurement")

            if item.allChildren():
                restoreIntervalsAction.setEnabled(True)
                restoreStripsAction.setEnabled(True)
                resetIntervalsAction.setEnabled(True)

            res = menu.exec(event.globalPos())
            if res == restoreStripsAction:
                item.setStrips(item.defaultStrips())
            if res == resetIntervalsAction:
                for child in item.allChildren():
                    child.setInterval(1)
            if res == restoreIntervalsAction:
                for child in item.allChildren():
                    child.setInterval(child.defaultInterval())


class SequenceController(QtCore.QObject):

    finished = QtCore.pyqtSignal()
    failed = QtCore.pyqtSignal(Exception)

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.sequence = []
        self._thread = None

    def setSequence(self, sequence):
        self.sequence = sequence

    def start(self):
        self._thread = threading.Thread(target=self.run)
        self._thread.start()

    def shutdown(self):
        self.context.request_abort()
        if self._thread:
            self._thread.join()
            self._thread = None

    def run(self):
        try:
            SequenceStrategy(self.context)(self.sequence)
        except Exception as exc:
            logging.exception(exc)
            self.failed.emit(exc)
        finally:
            self.finished.emit()
            self._thread = None
