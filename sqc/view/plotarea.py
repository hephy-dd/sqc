import logging
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from .plotwidget import PlotWidget, DataMapper

__all__ = ["PlotAreaWidget"]

logger = logging.getLogger(__name__)


def __(singular, plural, quantity):
    if quantity == 1:
        return singular % quantity
    return plural % quantity


class PlotAreaWidget(QtWidgets.QWidget):

    LayoutColumns = 3

    def __init__(self, parent: QtWidgets.QWidget = None) -> None:
        super().__init__(parent)

        self._groups: List[PlotWidget] = []

        self._series: defaultdict = defaultdict(dict)

        self._plotWidgets: Dict[str, PlotWidget] = {}

        self._scrollAreaWidget = QtWidgets.QWidget()

        self._toolbar = QtWidgets.QToolBar()
        self._toolbar.setOrientation(QtCore.Qt.Vertical)

        self._showActionGroup = QtWidgets.QActionGroup(self)

        self._scrollAreaWidgetLayout = QtWidgets.QVBoxLayout(self._scrollAreaWidget)

        for columns in range(1, type(self).LayoutColumns + 1):
            action = QtWidgets.QAction(__("Show %d Column", "Show %d Columns", columns))
            action.setCheckable(True)
            action.setIcon(QtGui.QIcon(f"icons:column-{columns}.svg"))
            gridLayout = QtWidgets.QGridLayout()
            action.setProperty("gridLayout", gridLayout)
            action.setProperty("gridColumns", columns)
            self._scrollAreaWidgetLayout.addLayout(gridLayout)
            action.toggled.connect(self.updateLayout)
            if not self._showActionGroup.actions():
                action.setChecked(True)
            self._showActionGroup.addAction(action)
            self._toolbar.addAction(action)

        for index in range(self._scrollAreaWidgetLayout.count()):
            self._scrollAreaWidgetLayout.setStretch(index, 0)

        self._scrollAreaWidgetLayout.addStretch()
        index = self._scrollAreaWidgetLayout.count() - 1
        self._scrollAreaWidgetLayout.setStretch(index, 10)

        self._scrollArea = QtWidgets.QScrollArea()
        self._scrollArea.setWidgetResizable(True)
        self._scrollArea.setWidget(self._scrollAreaWidget)

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self._scrollArea)
        layout.addWidget(self._toolbar)

        self._mapper: DataMapper = DataMapper()

    def setMapping(self, type: str, x: str, y: str) -> None:
        self._mapper.setMapping(type, x, y)

    def setTransformation(self, type: str, function: Callable) -> None:
        self._mapper.setTransformation(type, function)

    def updateLayout(self):
        for index, action in enumerate(self._showActionGroup.actions()):
            action.setVisible(index < len(self._plotWidgets))
            if action.isChecked():
                layout = action.property("gridLayout")
                columns = action.property("gridColumns")
                for index, widget in enumerate(self._plotWidgets.values()):
                    layout.addWidget(widget, index // columns, index % columns)

    def layoutIndex(self) -> int:
        for index, action in enumerate(self._showActionGroup.actions()):
            if action.isChecked():
                return index
        return -1

    def setLayoutIndex(self, layoutIndex: int) -> None:
        for index, action in enumerate(self._showActionGroup.actions()):
            if layoutIndex == index:
                action.setChecked(True)
                break

    def plotWidget(self, type: str) -> Optional[PlotWidget]:
        return self._plotWidgets.get(type)

    def plotWidgets(self) -> list:
        return [widget for widget in self._plotWidgets.values()]

    def addPlotWidget(self, type: str, widget: PlotWidget, group=False) -> None:
        if type not in self._plotWidgets:
            self._plotWidgets[type] = widget
            if group:
                self._groups.append(widget)
                widget.xRangeChanged.connect(self.syncXAxis)
            self.updateLayout()
        else:
            logger.error("Chart widget already exists: %s", type)

    def syncXAxis(self, minimum, maximum):
        blockers = []
        for widget in self._groups:
            blockers.append(QtCore.QSignalBlocker(widget))
        for widget in self._groups:
            minimum = round(minimum)
            maximum = round(maximum)
            widget.setStripRange(minimum, maximum)

    def clear(self) -> None:
        for widget in self.plotWidgets():
            widget.clear()

    def replace(self, type: str, name: str, points) -> None:
        try:
            widget = self.plotWidget(type)
            series = self._series.get(type, {}).get(name)
            if series is not None:
                if len(points) > 1:
                    series.replace([QtCore.QPointF(x, y) for x, y in self._mapper(type, points)])
            else:
                logger.error("No such series: %s.%s", type, name)
            if isinstance(widget, PlotWidget):
                widget.fitAllSeries()
        except Exception as exc:
            logger.exception(exc)
            logger.error("Failed to load series: %s (%s)", name, type)

    def reset(self) -> None:
        for widget in self.plotWidgets():
            widget.removeAllSeries()

    def addLineSeries(self, type: str, name: str) -> object:
        widget = self.plotWidget(type)
        if widget:
            series = widget.addLineSeries(name)
            self._series[type][name] = series
            return series
        else:
            logger.error("No such type: %s", type)
        return None

    def addScatterSeries(self, type: str, name: str) -> object:
        widget = self.plotWidget(type)
        if widget:
            series = widget.addScatterSeries(name)
            self._series[type][name] = series
            return series
        else:
            logger.error("No such type: %s", type)
        return None

    def setStrips(self, strips: Dict[int, str]) -> None:
        for widget in self.plotWidgets():
            widget.setStrips(strips)
