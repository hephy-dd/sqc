import logging
from typing import Callable, Dict, Iterator, Optional

from PyQt5 import QtChart, QtCore, QtGui, QtWidgets

from ..core.limits import LimitsAggregator
from .plothighlighter import PlotHighlighter, PlotMarkers

__all__ = [
    "DataMapper",
    "IVPlotWidget",
    "CVPlotWidget",
    "CV2PlotWidget",
    "IStripPlotWidget",
    "RStripPlotWidget",
    "CStripPlotWidget",
]


def auto_scale(value):
    scales = (
        (1e+24, "Y", "yotta"),
        (1e+21, "Z", "zetta"),
        (1e+18, "E", "exa"),
        (1e+15, "P", "peta"),
        (1e+12, "T", "tera"),
        (1e+9, "G", "giga"),
        (1e+6, "M", "mega"),
        (1e+3, "k", "kilo"),
        (1e+0, "", ""),
        (1e-3, "m", "milli"),
        (1e-6, "u", "micro"),
        (1e-9, "n", "nano"),
        (1e-12, "p", "pico"),
        (1e-15, "f", "femto"),
        (1e-18, "a", "atto"),
        (1e-21, "z", "zepto"),
        (1e-24, "y", "yocto")
    )
    for scale, prefix, name in scales:
        if abs(value) >= scale:
            return scale, prefix, name
    return 1e0, "", ""


class DataMapper:

    def __init__(self) -> None:
        self._mapping: dict[str, tuple[str, str]] = {}
        self._transformation: dict[str, Callable] = {}

    def setMapping(self, name: str, x: str, y: str) -> None:
        self._mapping[name] = x, y

    def setTransformation(self, name: str, f: Callable[[float, float], tuple[float, float]]) -> None:
        self._transformation[name] = f

    def __call__(self, name: str, items: list) -> Iterator:
        if name not in self._mapping:
            raise KeyError(f"No such series: {name!r}")
        x, y = self._mapping[name]
        tr = self._transformation.get(name, lambda x, y: (x, y))
        return (tr(item.get(x), item.get(y)) for item in items)


class DynamicValueAxis(QtChart.QValueAxis):

    def __init__(self, axis: QtChart.QValueAxis):
        super().__init__(axis)
        self.setProperty("axis", axis)
        self.setUnit("")
        self.setLocked(False)
        self.setRange(axis.min(), axis.max())
        axis.rangeChanged.connect(self.setRange)
        axis.hide()

    def axis(self) -> QtChart.QValueAxis:
        return self.property("axis")

    def unit(self) -> str:
        return self.property("unit")

    def setUnit(self, unit: str) -> None:
        self.setProperty("unit", unit)

    def isLocked(self) -> bool:
        return self.property("locked")

    def setLocked(self, state: bool) -> None:
        self.setProperty("locked", state)

    def setRange(self, minimum: float, maximum: float) -> None:
        if not self.isLocked():
            # Get best matching scale/prefix
            base = max(abs(minimum), abs(maximum))
            scale, prefix, _ = auto_scale(base)
            # Update labels prefix
            unit = self.unit()
            self.setLabelFormat(f"%.3G {prefix}{unit}")
            # Scale limits
            minimum *= 1. / scale
            maximum *= 1. / scale
            # Update axis range
            super().setRange(minimum, maximum)


class MarkerGraphicsItem(QtWidgets.QGraphicsRectItem):
    """Marker graphics item for series data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._polygon = QtWidgets.QGraphicsPolygonItem(self)
        self._text = QtWidgets.QGraphicsTextItem(self)
        self._format = None

    def setTextFormatter(self, function) -> None:
        self._format = function

    def setSeriesText(self, series, point):
        x, y = point.x(), point.y()
        text = f"{x:G}, {y:G}"
        if callable(self._format):
            try:
                text = self._format(series, point)
            except Exception:
                ...
        self._text.setPlainText(text)

    def setSeriesColor(self, color):
        # Set primary text and background color
        self._polygon.setBrush(QtGui.QBrush(color))
        # https://stackoverflow.com/questions/3942878/how-to-decide-font-color-in-white-or-black-depending-on-background-color
        if (color.red()*0.299 + color.green()*0.587 + color.blue()*0.114) > 186:
            penColor = QtGui.QColor(70, 70, 70)
        else:
            penColor = QtGui.QColor(255, 255, 255)
        self._text.setDefaultTextColor(penColor)
        self._polygon.setPen(penColor)

    def updateGeometry(self):
        rect = self._text.boundingRect()
        # Divide height by four to create left point
        quarter = rect.height() / 4
        self._text.setPos(rect.topLeft() + QtCore.QPointF(quarter, -rect.height() / 2))
        # Create pointed left label box
        polygon = QtGui.QPolygonF([
            rect.topLeft(),
            rect.topLeft() + QtCore.QPointF(0, quarter * 1),
            rect.topLeft() + QtCore.QPointF(-quarter, quarter * 2),
            rect.topLeft() + QtCore.QPointF(0, quarter * 3),
            rect.bottomLeft(),
            rect.bottomRight(),
            rect.topRight(),
        ])
        self._polygon.setPolygon(polygon)
        self._polygon.setPos(rect.topLeft().x() + quarter, rect.topLeft().y() - rect.height() / 2)

    def place(self, series, point):
        """Place marker for series at position of point."""
        visible = self.isVisible()
        self.setVisible(visible and series.chart().plotArea().contains(self.pos()))
        self.setPos(series.chart().mapToPosition(point))
        self.setSeriesText(series, point)
        if isinstance(series, QtChart.QLineSeries):
            self.setSeriesColor(series.pen().color())
        else:
            self.setSeriesColor(series.brush().color())
        self.updateGeometry()


class ChartView(QtChart.QChartView):
    """Custom chart view class providing a points marker."""

    MarkerRadius = 16

    def __init__(self, chart, parent=None):
        super().__init__(chart, parent)
        self._axisLabels = {}
        self.setMarkerEnabled(True)
        self.setMarker(MarkerGraphicsItem())

    def axisLabels(self):
        return self._axisLabels

    def setAxisLabels(self, prefix, labels):
        self._axisLabels[prefix] = labels

    def drawBackground(self, painter, rect):
        self.renameAxisLabels()

    def renameAxisLabels(self):
        """This is a hackish workaround to replace value axis tick labels with
        custom tick labels. All QGraphicsTextItem children containing a markup
        will be replaced by custom labels provided by axisLabels dict.
        """
        for prefix, labels in self._axisLabels.items():
            for item in self.items():
                if isinstance(item, QtWidgets.QGraphicsTextItem):
                    with QtCore.QSignalBlocker(item):
                        text = item.toPlainText()
                        if text.startswith(prefix):
                            index = text.lstrip(prefix)
                            width = item.textWidth()
                            pos = item.pos()
                            if index.isnumeric():
                                try:
                                    index = int(index)
                                    default = "..."
                                    item.setPlainText(format(labels.get(index, default)))
                                except Exception as exc:
                                    ...
                            else:
                                item.setPlainText("...")
                            item.adjustSize()
                            # Adjust position
                            dx = pos.x() + ((width - item.textWidth()) // 2)
                            item.setPos(dx, pos.y())

    def marker(self):
        return self._marker

    def setMarker(self, item):
        self._marker = item
        item.setZValue(100)
        self.scene().addItem(item)

    def setMarkerEnabled(self, enabled):
        self._setMarkerEnabled = enabled

    def isMarkerEnabled(self):
        return self._setMarkerEnabled

    def nearestPoints(self, series, pos):
        items = []
        chart = self.chart()
        for point in series.pointsVector():
            distance = (pos - chart.mapToPosition(point)).manhattanLength()
            items.append((distance, series, point))
        items.sort(key=lambda item: item[0])
        return items

    def mouseMoveEvent(self, event):
        """Draws marker and symbols/labels."""
        chart = self.chart()
        # Position in data
        value = chart.mapToValue(event.pos())
        # Position in plot
        pos = chart.mapToScene(event.pos())
        # Hide if mouse pressed (else collides with rubber band)
        visible = chart.plotArea().contains(pos)
        visible = visible and self.isMarkerEnabled()
        visible = visible and not event.buttons()
        self.marker().setVisible(visible)
        if self.isMarkerEnabled():
            items = []
            for series in chart.series():
                if isinstance(series, QtChart.QXYSeries):
                    points = self.nearestPoints(series, pos)
                    if len(points):
                        items.append(points[0])
            items.sort(key=lambda item: item[0])
            if len(items):
                distance, series, point = items[0]
                if distance < self.MarkerRadius:
                    self.marker().place(series, point)
                else:
                    self.marker().setVisible(False)
        super().mouseMoveEvent(event)


class PlotWidget(QtWidgets.QWidget):

    xRangeChanged = QtCore.pyqtSignal(float, float)

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self._chart = QtChart.QChart()
        self._chart.setTitle(title)
        self._chart.setMargins(QtCore.QMargins(4, 4, 4, 4))
        #self._chart.legend().setVisible(False)
        self._chart.legend().setAlignment(QtCore.Qt.AlignBottom)
        self._chart.layout().setContentsMargins(0, 0, 0, 0)
        # self._chart.setBackgroundRoundness(0)

        self._chartView = ChartView(self._chart)
        self._chartView.setMinimumHeight(430)
        self._chartView.setMaximumHeight(640)

        self._xAxis = QtChart.QValueAxis()
        self._xAxis.rangeChanged.connect(self.xRangeChanged)
        self._chart.addAxis(self._xAxis, QtCore.Qt.AlignBottom)

        self._yAxis = QtChart.QValueAxis()
        self._chart.addAxis(self._yAxis, QtCore.Qt.AlignRight)

        self._highlighter = PlotHighlighter(self._chart, self._xAxis, self._yAxis)
        self._markers = PlotMarkers(self._chart, self._xAxis, self._yAxis)

        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(self._chartView)
        layout.setContentsMargins(0, 0, 0, 0)

        self._boxes: dict[QtWidgets.QGraphicsRectItem, QtCore.QRectF] = {}

    def addBox(self, rect: QtCore.QRectF) -> None:
        self._highlighter.addBox(rect, QtGui.QColor(0, 255, 0, 50))

    def clearBoxes(self) -> None:
        self._highlighter.clear()

    def addMarker(self, point: QtCore.QPointF) -> None:
        self._markers.addMarker(point)

    def clearMarkers(self) -> None:
        self._markers.clear()

    def title(self) -> str:
        return self._chart.title()

    def setTitle(self, title: str) -> None:
        self._chart.setTitle(title)

    def chart(self) -> QtChart.QChart:
        return self._chart

    def clear(self) -> None:
        for series in self._chart.series():
            if isinstance(series, QtChart.QXYSeries):
                series.clear()

    def removeAllSeries(self) -> None:
        self._chart.removeAllSeries()

    def addLineSeries(self, name) -> QtChart.QLineSeries:
        series = QtChart.QLineSeries()
        series.setName(name)
        self._chart.addSeries(series)
        series.attachAxis(self._xAxis)
        series.attachAxis(self._yAxis)
        series.setPen(QtGui.QPen(series.pen().color()))
        return series

    def addScatterSeries(self, name) -> QtChart.QScatterSeries:
        series = QtChart.QScatterSeries()
        series.setName(name)
        self._chart.addSeries(series)
        series.attachAxis(self._xAxis)
        series.attachAxis(self._yAxis)
        series.setPen(QtGui.QPen(series.pen().color()))
        series.setMarkerSize(7)
        series.setBorderColor(series.pen().color())
        return series

    def setRange(self, minimum, maximum):
        self._xAxis.setRange(minimum, maximum)
        self._xAxis.setReverse(minimum < 0)

    def seriesLimits(self, xmin=None, xmax=None):
        limits = LimitsAggregator()
        for series in self._chart.series():
            if isinstance(series, QtChart.QXYSeries):
                for point in series.pointsVector():
                    x = point.x()
                    y = point.y()
                    if xmin is not None and xmax is not None:
                        if not (xmin <= x <= xmax):
                            continue
                    limits.add([(x, y)])
        return limits

    def fitAllSeries(self, xmin=None, xmax=None):
        limits = self.seriesLimits(xmin, xmax)
        if limits.is_valid:
            ymin, ymax = limits.ymin, limits.ymax
            # HACK
            # Fix very small ranges
            diff = abs(ymax - ymin)
            if diff < 1e-12:
                ymin = ymin - abs(5e-13 - ymin)
                ymax = ymax + abs(5e-13 - ymax)
            self._yAxis.setRange(ymin, ymax)
        tickCount = self._yAxis.tickCount()
        self._yAxis.applyNiceNumbers()
        self._yAxis.setTickCount(tickCount)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        tickCounts = [
            (680, 9, 5),
            (480, 5, 4),
            (380, 5, 2),
            (240, 3, 2),
            #(0, 2, 3),
        ]
        for width, tickCount, minorTickCount in tickCounts:
            if self.width() > width:
                self._xAxis.setTickCount(tickCount)
                self._xAxis.setMinorTickCount(minorTickCount)
                break


class IVPlotWidget(PlotWidget):

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        self._xAxis.setTitleText("Voltage")
        self._xAxis.setRange(0, 600)
        self._xAxis.setTickCount(9)
        self._xAxis.setMinorTickCount(3)
        self._xAxis.setLabelFormat("%G V")

        self._iDynamicAxis = DynamicValueAxis(self._yAxis)
        self._iDynamicAxis.setUnit("A")
        self._iDynamicAxis.setTitleText("Current")
        self._iDynamicAxis.setTickCount(9)
        self._iDynamicAxis.setMinorTickCount(1)
        self._chart.addAxis(self._iDynamicAxis, QtCore.Qt.AlignRight)

        self._yAxis.setRange(0, 200e-9)


class CVPlotWidget(PlotWidget):

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        # Fix stretch of bottom axis
        self._chart.setMargins(QtCore.QMargins(4, 4, 26, 4))

        self._xAxis.setTitleText("Voltage")
        self._xAxis.setRange(0, 300)
        self._xAxis.setTickCount(9)
        self._xAxis.setMinorTickCount(3)
        self._xAxis.setLabelFormat("%.3G V")

        self._iDynamicAxis = DynamicValueAxis(self._yAxis)
        self._iDynamicAxis.setUnit("F")
        self._iDynamicAxis.setTitleText("Capacity")
        self._iDynamicAxis.setTickCount(9)
        self._iDynamicAxis.setMinorTickCount(1)
        self._chart.addAxis(self._iDynamicAxis, QtCore.Qt.AlignRight)

        self._yAxis.setRange(0, 60e-9)


class CV2PlotWidget(PlotWidget):

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        # Fix stretch of bottom axis
        self._chart.setMargins(QtCore.QMargins(4, 4, 26, 4))

        self._xAxis.setTitleText("Voltage")
        self._xAxis.setRange(0, 300)
        self._xAxis.setTickCount(9)
        self._xAxis.setMinorTickCount(3)
        self._xAxis.setLabelFormat("%.3G V")

        self._yAxis.setTitleText("Capacity 1/c^2")
        self._yAxis.setTickCount(9)
        self._yAxis.setMinorTickCount(1)
        self._yAxis.setLabelFormat("%G")


class StripPlotWidget(PlotWidget):

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        self._strips: dict = {}

        self._xAxis.setTitleText("Strip #")
        self._xAxis.setLabelFormat("#%d")
        self._xAxis.setTickCount(9)
        self._xAxis.setMinorTickCount(3)
        self._xAxis.rangeChanged.connect(self.setStripRange)

        self._chartView.setRubberBand(self._chartView.HorizontalRubberBand)
        self._chartView.marker().setTextFormatter(self.formatMarkerText)

    def strips(self) -> dict:
        return self._strips

    def setStrips(self, strips: Dict[int, str]):
        self._strips = strips
        self._chartView.setAxisLabels("#", strips)
        self._xAxis.setRange(0, max(1, len(strips) - 1))

    def setStripRange(self, minimum: int, maximum: int) -> None:
        strips: int = max(1, len(self._strips) - 1)
        minimum = int(round(minimum))
        maximum = int(round(maximum))
        minimum, maximum = sorted((max(0, minimum), min(strips, maximum)))
        # Calculate minimum window based on ticks
        tickCount = abs(self._xAxis.tickCount() - 1)
        diff = abs(maximum - minimum)
        if diff < tickCount:
            maximum = minimum + tickCount
            if maximum > strips:
                maximum = strips
                minimum = maximum - tickCount
        with QtCore.QSignalBlocker(self._xAxis):
            self._xAxis.setRange(minimum, maximum)

    def formatMarkerText(self, series, point):
        x, y = point.x(), point.y()
        index = int(round(x))
        strip = self._strips.get(index, "n/a")
        return f"Strip: {strip}\nValue: {y:G}"


class IStripPlotWidget(StripPlotWidget):

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        self._yAxis.setRange(0, .001)
        self._yAxis.setTitleText("Current")

        self._iDynamicAxis = DynamicValueAxis(self._yAxis)
        self._iDynamicAxis.setUnit("A")
        self._iDynamicAxis.setTitleText("Current")
        self._iDynamicAxis.setTickCount(9)
        self._iDynamicAxis.setMinorTickCount(1)
        self._chart.addAxis(self._iDynamicAxis, QtCore.Qt.AlignRight)

        self._yAxis.setRange(0, 1e-06)

class RStripPlotWidget(StripPlotWidget):

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        self._iDynamicAxis = DynamicValueAxis(self._yAxis)
        self._iDynamicAxis.setUnit("Ohm")
        self._iDynamicAxis.setTitleText("Resistance")
        self._iDynamicAxis.setTickCount(9)
        self._iDynamicAxis.setMinorTickCount(1)
        self._chart.addAxis(self._iDynamicAxis, QtCore.Qt.AlignRight)

        self._yAxis.setRange(0, 1e03)


class CStripPlotWidget(StripPlotWidget):

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        # TODO
        # It appears that QChart can't display double values < 10e-12 (10 pF),
        # this needs more investigation.
        #

        # self._iDynamicAxis = DynamicValueAxis(self._yAxis)
        # self._iDynamicAxis.setUnit("F")
        # self._iDynamicAxis.setTitleText("Capacity")
        # self._iDynamicAxis.setTickCount(9)
        # self._iDynamicAxis.setMinorTickCount(1)

        self._yAxis.setTitleText("Capacity")
        self._yAxis.setTickCount(9)
        self._yAxis.setMinorTickCount(1)
        self._yAxis.setLabelFormat("%G pF")

        # self._chart.addAxis(self._iDynamicAxis, QtCore.Qt.AlignRight)

        #self._yAxis.setRange(0, 1e-09)
        self._yAxis.setRange(0, 200)  # pF

    @classmethod
    def transform(cls, x, y):
        # TODO
        return x, y * 1e12  # pF

    @classmethod
    def transformPoint(cls, point: QtCore.QPointF) -> QtCore.QPointF:
        x, y = cls.transform(point.x(), point.y())
        return QtCore.QPointF(x, y)

    def addBox(self, rect: QtCore.QRectF) -> None:
        topLeft = self.transformPoint(rect.topLeft())
        bottomRight = self.transformPoint(rect.bottomRight())
        self._highlighter.addBox(QtCore.QRectF(topLeft, bottomRight), QtGui.QColor(0, 255, 0, 50))
        super().addBox(rect)

    def addMarker(self, point: QtCore.QPointF) -> None:
        super().addMarker(self.transformPoint(point))


class RecontactPlotWidget(StripPlotWidget):
    """Histogram of recontacts and remeasurements."""

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        self._yAxis.setTitleText("Times")
        self._yAxis.setTickCount(9)
        self._yAxis.setMinorTickCount(0)
        self._yAxis.setVisible(True)
        self._yAxis.setRange(0, 8)
        self._yAxis.setLabelFormat("%dx")

        self._stackedBarSeries = QtChart.QStackedBarSeries()

        self._chart.addSeries(self._stackedBarSeries)
        self._stackedBarSeries.attachAxis(self._xAxis)
        self._stackedBarSeries.attachAxis(self._yAxis)

        self._stackedBarSeries.setBarWidth(1.0)

        self.replaceData({"Remeasurements": [], "Recontacts": []})

    def removeAllSeries(self) -> None:
        ...

    def clear(self) -> None:
        self.replaceData({"Remeasurements": [], "Recontacts": []})

    def replaceData(self, data):
        order = ["Recontacts", "Remeasurements",]
        colors = {"Recontacts": "red", "Remeasurements": "orange",}

        def sort_keys(item):
            key = item[0]
            if key in order:
                return order.index(key)
            return -1

        barSets = []

        for key, values in sorted(data.items(), key=sort_keys):
            barSet = QtChart.QBarSet(key)
            # barSet.destroyed.connect(lambda: logging.debug("Destroyed Count BarSet"))
            barSet.setPen(QtGui.QColor(colors.get(key, "blue")))
            barSet.setBrush(QtGui.QColor(colors.get(key, "blue")))
            for value in values:
                barSet.append(value)
            barSets.append(barSet)

        self._stackedBarSeries.clear()
        for barSet in barSets:
            self._stackedBarSeries.append(barSet)


class EnvironPlotWidget(PlotWidget):

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)

        x = QtChart.QValueAxis()
        x.setTitleText("Time")
        x.setRange(0, 255)
        self._chart.addAxis(x, QtCore.Qt.AlignBottom)

        y = QtChart.QDateTimeAxis()
        y.setTitleText("Value")
        self._chart.addAxis(y, QtCore.Qt.AlignRight)

        self._series = QtChart.QLineSeries()
        self._chart.addSeries(self._series)
        self._series.attachAxis(x)
        self._series.attachAxis(y)
