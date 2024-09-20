from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets, QtChart


class PlotHighlighter:
    """Draw colored highligh boxes inside a plot area."""

    def __init__(self, chart: QtChart.QChart, xAxis: QtChart.QAbstractAxis, yAxis: QtChart.QAbstractAxis) -> None:
        self.chart: QtChart.QChart = chart
        self.xAxis: QtChart.QAbstractAxis = xAxis
        self.yAxis: QtChart.QAbstractAxis = yAxis
        self.highlightBoxes: list[QtChart.QAreaSeries] = []

    def addBox(self, rect: QtCore.QRectF, color: QtGui.QColor) -> None:
        """Adds a highlight box to the chart."""
        # Ensure coordinates are correctly ordered
        xStart = min(rect.left(), rect.right())
        xEnd = max(rect.left(), rect.right())
        yStart = min(rect.top(), rect.bottom())
        yEnd = max(rect.top(), rect.bottom())

        # Create lower and upper boundary series
        lowerSeries = QtChart.QLineSeries()
        lowerSeries.append(xStart, yStart)
        lowerSeries.append(xEnd, yStart)

        upperSeries = QtChart.QLineSeries()
        upperSeries.append(xStart, yEnd)
        upperSeries.append(xEnd, yEnd)

        # Create the area series (highlight box)
        areaSeries = QtChart.QAreaSeries(upperSeries, lowerSeries)
        areaSeries.setBrush(QtGui.QBrush(color))
        areaSeries.setPen(QtGui.QPen(QtCore.Qt.NoPen))  # Remove border

        # Add the area series to the chart
        self.chart.addSeries(areaSeries)

        # Attach axes to the area series
        areaSeries.attachAxis(self.xAxis)
        areaSeries.attachAxis(self.yAxis)

        # Hide the legend marker for this series
        for marker in self.chart.legend().markers(areaSeries):
            marker.setVisible(False)

        # Keep track of the area series
        self.highlightBoxes.append(areaSeries)

    def clear(self) -> None:
        """Removes all highlight boxes from the chart."""
        for areaSeries in self.highlightBoxes:
            self.chart.removeSeries(areaSeries)
        self.highlightBoxes.clear()


class PlotMarkers:
    """Draw colored markers inside a plot area."""

    def __init__(self, chart: QtChart.QChart, xAxis: QtChart.QAbstractAxis, yAxis: QtChart.QAbstractAxis) -> None:
        self.chart: QtChart.QChart = chart
        self.xAxis: QtChart.QAbstractAxis = xAxis
        self.yAxis: QtChart.QAbstractAxis = yAxis

        self.markerSeries: Optional[QtChart.QScatterSeries] = None

    def addMarker(self, point: QtCore.QPointF) -> None:
        if not self.markerSeries:
            self.markerSeries = QtChart.QScatterSeries()
            self.markerSeries.setColor(QtGui.QColor("red"))
            self.markerSeries.setMarkerSize(8)
            self.chart.addSeries(self.markerSeries)
            self.markerSeries.attachAxis(self.xAxis)
            self.markerSeries.attachAxis(self.yAxis)
            for marker in self.chart.legend().markers(self.markerSeries):
                marker.setVisible(False)
        self.markerSeries.append(point)

    def clear(self) -> None:
        """Removes all markers from the chart."""
        if self.markerSeries in self.chart.series():
            self.chart.removeSeries(self.markerSeries)
        self.markerSeries = None
