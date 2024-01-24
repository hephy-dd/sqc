import logging
import os
import json
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets

from ..core.limits import LimitsAggregator
from ..core.utils import cv_inverse_square

from . import aboutMessage, showContents
from .plotwidget import (
    CStripPlotWidget,
    CVPlotWidget,
    CV2PlotWidget,
    StripPlotWidget,
    IStripPlotWidget,
    IVPlotWidget,
    RStripPlotWidget,
    DataMapper,
)

__all__ = ["DataBrowserWindow"]

logger = logging.getLogger(__name__)


def createDataMapper():
    mapper = DataMapper()

    mapper.setMapping("iv", "bias_smu_v", "bias_smu_i")
    mapper.setMapping("cv", "bias_smu_v", "lcr_cp")
    mapper.setMapping("cvfd", "bias_smu_v", "lcr_cp")
    mapper.setMapping("rpoly", "strip_index", "rpoly_r")
    mapper.setMapping("istrip", "strip_index", "istrip_i")
    mapper.setMapping("idiel", "strip_index", "idiel_i")
    mapper.setMapping("cac", "strip_index", "cac_cp")
    mapper.setMapping("cint", "strip_index", "cint_cp")
    mapper.setMapping("rint", "strip_index", "rint_r")
    mapper.setMapping("idark", "strip_index", "idark_i")

    mapper.setTransformation("iv", lambda x, y: (x, abs(y)))
    mapper.setTransformation("cv", lambda x, y: (x, abs(y)))
    mapper.setTransformation("cvfd", lambda x, y: cv_inverse_square(x, abs(y)))
    mapper.setTransformation("rpoly", lambda x, y: (x, abs(y)))
    mapper.setTransformation("istrip", lambda x, y: (x, abs(y)))
    mapper.setTransformation("idiel", lambda x, y: (x, abs(y)))
    mapper.setTransformation("cac", lambda x, y: CStripPlotWidget.transform(x, abs(y)))  # TODO
    mapper.setTransformation("cint", lambda x, y: CStripPlotWidget.transform(x, abs(y)))  # TODO
    mapper.setTransformation("rint", lambda x, y: (x, abs(y)))
    mapper.setTransformation("idark", lambda x, y: (x, abs(y)))

    return mapper


def createTextWidget(text):
    textEdit = QtWidgets.QTextEdit()
    textEdit.setReadOnly(True)
    textEdit.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
    font = QtGui.QFont("monospace")
    font.setStyleHint(QtGui.QFont.Monospace)
    textEdit.setFont(font)
    textEdit.setFontFamily("monospace")
    textEdit.setText(text)
    return textEdit


def createPlotWidget(dataframe):
    data = dataframe.get("data")

    plotWidget = QtWidgets.QWidget()
    plotLayout = QtWidgets.QVBoxLayout(plotWidget)

    plotScrollArea = QtWidgets.QScrollArea()
    plotScrollArea.setWidgetResizable(True)
    plotScrollArea.setWidget(plotWidget)

    mapper = createDataMapper()

    def axisLabels(values):
        labels = {}
        for items in values:
            for item in items:
                labels[item.get("strip_index")] = item.get("strip")
        return labels

    def populate_header():
        header = dataframe.get("header", {})
        sensor_name = header.get("sensor_name")
        sensor_type = header.get("sensor_type")
        operator_name = header.get("operator_name")
        timestamp = header.get("timestamp")
        header_lines = []
        if sensor_type:
            header_lines.append(f"Sensor Type: {sensor_type}")
        if sensor_name:
            header_lines.append(f"Sensor Name: {sensor_name}")
        if operator_name:
            header_lines.append(f"Operator: {operator_name}")
        if timestamp:
            fmt_timestamp = datetime.fromtimestamp(timestamp).strftime('%a %b %d %H:%M:%S %Y')
            header_lines.append(f"Date: {fmt_timestamp}")
        header_label = QtWidgets.QLabel()
        header_label.setWordWrap(True)
        header_label.setText("\n".join(header_lines))
        header_frame = QtWidgets.QFrame()
        header_frame.setStyleSheet("QFrame{background: white; border-radius: 4px;}")
        layout = QtWidgets.QVBoxLayout(header_frame)
        layout.addWidget(header_label)
        plotLayout.addWidget(header_frame)

    def populate_plot(widget, name, key=None):
        limits = LimitsAggregator()
        if key is None:
            key = name
        for k, v in data.get(name, {}).items():
            series = widget.addLineSeries(k)
            raw_series = list(mapper(key, v))
            if len(raw_series) < 1:
                continue
            series.replace((QtCore.QPointF(float(x), float(y)) for x, y in raw_series))
            limits.add(raw_series)
        if limits.is_valid:
            xmin = round(limits.xmin)
            xmax = round(limits.xmax)
            if xmax < xmin + 10:
                xmax += (xmin + 10 - xmax)
            widget.setRange(xmin, xmax)
            widget.fitAllSeries()
        plotLayout.addWidget(widget)

    def populate_strips(widget, name, key=None):
        if key is None:
            key = name
        # Load strips from header
        geometry = dataframe.get("header", {}).get("geometry", {})
        labels = dict(enumerate(geometry.get("strips", [])))
        if not labels:
            # If no pads in header, reconstruct from data
            labels = axisLabels(data.get(name, {}).values())
        widget.setStrips(labels)
        for k, v in data.get(name, {}).items():
            series = widget.addScatterSeries(k)
            pen = QtGui.QPen(QtCore.Qt.transparent)
            series.setPen(pen)
            raw_series = list(mapper(key, v))
            if len(raw_series) < 1:
                continue
            series.replace((QtCore.QPointF(float(x), float(y)) for x, y in raw_series))
        widget.setRange(0, len(widget.strips()))
        widget.fitAllSeries()
        plotLayout.addWidget(widget)

    group = []

    populate_header()

    if "iv" in data:
        widget = IVPlotWidget("IV")
        populate_plot(widget, "iv")

    if "cv" in data:
        widget = CVPlotWidget("CV")
        populate_plot(widget, "cv")

    if "cv" in data:
        widget = CV2PlotWidget("CV full depletion")
        populate_plot(widget, "cv", "cvfd")

    if "rpoly" in data:
        widget = RStripPlotWidget("Rpoly")
        populate_strips(widget, "rpoly")
        group.append(widget)

    if "istrip" in data:
        widget = IStripPlotWidget("Istrip")
        populate_strips(widget, "istrip")
        group.append(widget)

    if "idiel" in data:
        widget = IStripPlotWidget("Idiel")
        populate_strips(widget, "idiel")
        group.append(widget)

    if "cac" in data:
        widget = CStripPlotWidget("Cac")
        populate_strips(widget, "cac")
        group.append(widget)

    if "cint" in data:
        widget = CStripPlotWidget("Cint")
        populate_strips(widget, "cint")
        group.append(widget)

    if "rint" in data:
        widget = RStripPlotWidget("Rint")
        populate_strips(widget, "rint")
        group.append(widget)

    if "idark" in data:
        widget = IStripPlotWidget("Idark")
        populate_strips(widget, "idark")
        group.append(widget)

    def syncXAxis(minimum, maximum):
        blockers = []
        for widget in group:
            blockers.append(QtCore.QSignalBlocker(widget))
        for widget in group:
            widget.setRange(max(0, minimum), min(4096, maximum))

    for widget in group:
        widget.xRangeChanged.connect(syncXAxis)

    plotLayout.addStretch()

    return plotScrollArea


class DataBrowserWindow(QtWidgets.QMainWindow):

    visibilityChanged = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("dataBrowserWindow")
        self.setWindowTitle("Data Browser")
        self.setWindowFlag(QtCore.Qt.Dialog, True)

        self.quitAction = QtWidgets.QAction("&Quit")
        self.quitAction.setShortcut("Ctrl+Q")
        self.quitAction.triggered.connect(self.close)

        self.contentsAction = QtWidgets.QAction("&Contents")
        self.contentsAction.setShortcut(QtGui.QKeySequence("F1"))
        self.contentsAction.triggered.connect(self.showContents)

        self.aboutQtAction = QtWidgets.QAction("&About Qt")
        self.aboutQtAction.triggered.connect(self.showAboutQt)

        self.aboutAction = QtWidgets.QAction("&About")
        self.aboutAction.triggered.connect(self.showAbout)

        self.fileMenu = self.menuBar().addMenu("&File")
        self.fileMenu.addAction(self.quitAction)

        self.helpMenu = self.menuBar().addMenu("&Help")
        self.helpMenu.addAction(self.contentsAction)
        self.helpMenu.addSeparator()
        self.helpMenu.addAction(self.aboutQtAction)
        self.helpMenu.addAction(self.aboutAction)

        self.rootPathLineEdit = QtWidgets.QLineEdit(self)
        self.rootPathLineEdit.editingFinished.connect(self.updateRootPath)
        completer = QtWidgets.QCompleter(self)
        completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        model = QtWidgets.QDirModel(completer)
        model.setFilter(QtCore.QDir.Dirs | QtCore.QDir.Drives | QtCore.QDir.NoDotAndDotDot | QtCore.QDir.AllDirs)
        completer.setModel(model)
        completer.activated.connect(self.updateRootPath)
        self.rootPathLineEdit.setCompleter(completer)

        self.rootPathToolButton = QtWidgets.QToolButton(self)
        self.rootPathToolButton.setText("...")
        self.rootPathToolButton.clicked.connect(self.selectRootPath)

        rootPathLayout = QtWidgets.QHBoxLayout()
        rootPathLayout.setContentsMargins(8, 0, 8, 0)
        rootPathLayout.addWidget(self.rootPathLineEdit)
        rootPathLayout.addWidget(self.rootPathToolButton)

        self.fileSystemModel = QtWidgets.QFileSystemModel()
        self.fileSystemModel.setNameFilters(["*.json", "*.txt"])
        self.fileSystemModel.setNameFilterDisables(False)

        self.treeView = QtWidgets.QTreeView(self)
        self.treeView.setSortingEnabled(True)
        self.treeView.sortByColumn(0, QtCore.Qt.AscendingOrder)
        self.treeView.setModel(self.fileSystemModel)
        self.treeView.selectionModel().currentChanged.connect(self.selectItem)

        self.leftWidget = QtWidgets.QWidget(self)

        leftLayout = QtWidgets.QVBoxLayout(self.leftWidget)
        leftLayout.setContentsMargins(0, 8, 0, 0)
        leftLayout.addLayout(rootPathLayout)
        leftLayout.addWidget(self.treeView)

        self.stackedWidget = QtWidgets.QStackedWidget()

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.leftWidget)
        self.splitter.addWidget(self.stackedWidget)

        self.setCentralWidget(self.splitter)

        self.fileNameLabel = QtWidgets.QLabel(self)
        self.statusBar().addPermanentWidget(self.fileNameLabel)

    def readSettings(self):
        settings = QtCore.QSettings()
        settings.beginGroup(self.objectName())

        geometry = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)
        if not self.restoreGeometry(geometry):
            self.resize(800, 600)

        state = settings.value("state", QtCore.QByteArray(), QtCore.QByteArray)
        self.restoreState(state)

        splitterState = settings.value("splitter/state", QtCore.QByteArray(), QtCore.QByteArray)
        if splitterState.isEmpty():
            self.splitter.setSizes([400, 900])
        else:
            self.splitter.restoreState(splitterState)

        settings.endGroup()

    def syncSettings(self):
        settings = QtCore.QSettings()
        settings.beginGroup(self.objectName())

        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())
        settings.setValue("splitter/state", self.splitter.saveState())

        settings.endGroup()

    def rootPath(self) -> str:
        return self.fileSystemModel.rootPath()

    def setRootPath(self, path: str) -> None:
        self.rootPathLineEdit.setText(path)
        self.updateRootPath()

    def updateRootPath(self) -> None:
        path = self.rootPathLineEdit.text()
        self.fileSystemModel.setRootPath(path)
        self.treeView.setRootIndex(self.fileSystemModel.index(path))
        self.treeView.setColumnWidth(0, 200)

    def selectRootPath(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Root Directory", self.rootPath())
        if path:
            self.setRootPath(path)

    def setVisible(self, visible: bool) -> None:
        super().setVisible(visible)
        self.visibilityChanged.emit(visible)

    def selectItem(self, current, previous):
        self.fileNameLabel.clear()
        fileInfo = self.fileSystemModel.fileInfo(current)
        if fileInfo is not None:
            filename = fileInfo.absoluteFilePath()
            if os.path.isfile(filename):
                self.loadFile(filename)
            self.fileNameLabel.setText(filename)

    def clearWidget(self):
        while self.stackedWidget.count():
            widget = self.stackedWidget.currentWidget()
            self.stackedWidget.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()

    def loadFile(self, filename):
        self.setEnabled(False)
        self.clearWidget()
        try:
            with open(filename, "rt") as fp:
                self.loadData(fp.read())
        except Exception as exc:
            logger.exception(exc)
        finally:
            self.setEnabled(True)

    def loadData(self, data):
        loaders = [self.loadJsonData, self.loadTextData]
        for loader in loaders:
            if loader(data):
                break

    def loadTextData(self, data):
        widget = createTextWidget(format(data))
        self.stackedWidget.addWidget(widget)
        self.stackedWidget.setCurrentWidget(widget)
        return True

    def loadJsonData(self, data):
        try:
            data = json.loads(data)
        except Exception:
            return False
        widget = createPlotWidget(data)
        self.stackedWidget.addWidget(widget)
        self.stackedWidget.setCurrentWidget(widget)
        return True

    def showContents(self) -> None:
        showContents()

    def showAboutQt(self) -> None:
        QtWidgets.QMessageBox.aboutQt(self, "About Qt")

    def showAbout(self) -> None:
        QtWidgets.QMessageBox.about(self, "About", aboutMessage())
