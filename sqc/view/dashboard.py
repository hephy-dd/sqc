import logging
import math
import os
from pathlib import Path
from collections import Counter
from typing import Any, Dict, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from ..core.utils import cv_inverse_square

from .plotarea import PlotAreaWidget
from .plotwidget import (
    CStripPlotWidget,
    CVPlotWidget,
    CV2PlotWidget,
    IStripPlotWidget,
    IVPlotWidget,
    RStripPlotWidget,
    RecontactPlotWidget,
)
from ..core.sequence import load as load_sequence
from ..settings import Settings
from .sequence import SequenceItem, SequenceWidget, loadSequenceItems
from .utils import setForeground, setBackground, Colors
from .profiles import readProfiles, padfileType, padfileCategory, padfileName

__all__ = ["DashboardWidget"]

logger = logging.getLogger(__name__)


def formatTemperature(value: float) -> str:
    if math.isfinite(value):
        return f"{value:.1f} °C"
    return "n/a"


def formatHumidity(value: float) -> str:
    if math.isfinite(value):
        return f"{value:.1f} %rel."
    return "n/a"


class DashboardWidget(QtWidgets.QWidget):

    outputPathChanged = QtCore.pyqtSignal(str)

    def __init__(self, context, parent: QtWidgets.QWidget = None) -> None:
        super().__init__(parent)

        self.context = context

        self.context.data_changed.connect(self.updateData)
        self.context.statistics_changed.connect(self.updateHistograms)
        self.context.current_item_changed.connect(self.showSequenceItem)
        self.context.current_item_changed.connect(self.setCurrentItem)
        self.context.item_state_changed.connect(lambda item, state: item.setState(state))
        self.context.item_progress_changed.connect(lambda item, value, maximum: item.setProgress(value, maximum))
        self.context.bias_voltage_changed.connect(self.setBiasVoltage)
        self.context.current_strip_changed.connect(self.setCurrentStrip)
        self.context.stripscan_progress_changed.connect(self.setStripscanProgress)
        self.context.stripscan_estimation_changed.connect(self.setStripscanEstimation)

        # Sensor name

        self.nameLabel = QtWidgets.QLabel("Sensor Name")

        self.namePrefixLineEdit = QtWidgets.QLineEdit(self)
        self.namePrefixLineEdit.editingFinished.connect(self.sensorNameChanged)

        self.nameInfixLineEdit = QtWidgets.QLineEdit(self)
        self.nameInfixLineEdit.setText("Unnamed")
        self.nameInfixLineEdit.setClearButtonEnabled(True)
        self.nameInfixLineEdit.editingFinished.connect(self.sensorNameChanged)

        self.nameSuffixLineEdit = QtWidgets.QLineEdit(self)
        self.nameSuffixLineEdit.editingFinished.connect(self.sensorNameChanged)

        self.nameLayout = QtWidgets.QHBoxLayout()
        self.nameLayout.addWidget(self.namePrefixLineEdit)
        self.nameLayout.addWidget(self.nameInfixLineEdit)
        self.nameLayout.addWidget(self.nameSuffixLineEdit)
        self.nameLayout.setStretch(0, 3)
        self.nameLayout.setStretch(1, 7)
        self.nameLayout.setStretch(2, 3)

        # Sensor type

        self.profileLabel = QtWidgets.QLabel("Sensor Profile")

        self.profileComboBox = QtWidgets.QComboBox(self)
        self.profileComboBox.currentIndexChanged.connect(self.profileChanged)
        self.profileComboBoxPreviousIndex = -1

        # Sequence

        self.sequenceLabel = QtWidgets.QLabel("Sequence")

        self.sequenceWidget = SequenceWidget(self)
        self.sequenceWidget.currentItemChanged.connect(self.loadSequenceItemParameters)

        # Parameters

        self.parametersLabel = QtWidgets.QLabel("Parameters")

        self.parametersTreeWidget = QtWidgets.QTreeWidget()
        self.parametersTreeWidget.setHeaderLabels(["Name", "Value"])
        self.parametersTreeWidget.setRootIsDecorated(False)

        # Options

        self.optionsGroupBox = QtWidgets.QGroupBox(self)
        self.optionsGroupBox.setTitle("Options")

        self.remeasurementsLabel = QtWidgets.QLabel(self)
        self.remeasurementsLabel.setText("Remeasurement Attempts")

        self.remeasureCountSpinBox = QtWidgets.QSpinBox(self)
        self.remeasureCountSpinBox.setRange(0, 8)
        self.remeasureCountSpinBox.setValue(0)
        self.remeasureCountSpinBox.setSuffix("x")
        self.remeasureCountSpinBox.setStatusTip("Number of remeasurement attempts for failed strip measurements")

        self.recontactsLabel = QtWidgets.QLabel(self)
        self.recontactsLabel.setText("Recontact Attempts")

        self.recontactCountSpinBox = QtWidgets.QSpinBox(self)
        self.recontactCountSpinBox.setRange(0, 3)
        self.recontactCountSpinBox.setValue(0)
        self.recontactCountSpinBox.setSuffix("x")
        self.recontactCountSpinBox.setStatusTip("Number of recontact attempts for failed strip measurements")

        optionsLayout = QtWidgets.QGridLayout(self.optionsGroupBox)
        optionsLayout.addWidget(self.remeasurementsLabel, 0, 0, 1, 1)
        optionsLayout.addWidget(self.remeasureCountSpinBox, 0, 1, 1, 1)
        optionsLayout.addWidget(self.recontactsLabel, 0, 2, 1, 1)
        optionsLayout.addWidget(self.recontactCountSpinBox, 0, 3, 1, 1)
        optionsLayout.setColumnStretch(1, 1)
        optionsLayout.setColumnStretch(3, 1)
        optionsLayout.setColumnStretch(4, 10)

        # Setpoints

        self.setpointsGroupBox = QtWidgets.QGroupBox()
        self.setpointsGroupBox.setTitle("Setpoints")

        self.minTemperatureSpinBox = QtWidgets.QDoubleSpinBox()
        self.minTemperatureSpinBox.setSuffix(" °C")
        self.minTemperatureSpinBox.setDecimals(1)
        self.minTemperatureSpinBox.setRange(0, 100)
        self.minTemperatureSpinBox.setValue(20)
        self.minTemperatureSpinBox.editingFinished.connect(self.syncTemperature)

        self.maxTemperatureSpinBox = QtWidgets.QDoubleSpinBox()
        self.maxTemperatureSpinBox.setSuffix(" °C")
        self.maxTemperatureSpinBox.setDecimals(1)
        self.maxTemperatureSpinBox.setRange(0, 100)
        self.maxTemperatureSpinBox.setValue(25)
        self.maxTemperatureSpinBox.editingFinished.connect(self.syncTemperature)

        self.minHumiditySpinBox = QtWidgets.QDoubleSpinBox()
        self.minHumiditySpinBox.setSuffix(" %rel")
        self.minHumiditySpinBox.setDecimals(1)
        self.minHumiditySpinBox.setRange(0, 100)
        self.minHumiditySpinBox.setValue(5)
        self.minHumiditySpinBox.editingFinished.connect(self.syncHumidity)

        self.maxHumiditySpinBox = QtWidgets.QDoubleSpinBox()
        self.maxHumiditySpinBox.setSuffix(" %rel")
        self.maxHumiditySpinBox.setDecimals(1)
        self.maxHumiditySpinBox.setRange(0, 100)
        self.maxHumiditySpinBox.setValue(40)
        self.maxHumiditySpinBox.editingFinished.connect(self.syncHumidity)

        temperatureLayout = QtWidgets.QFormLayout()
        temperatureLayout.addRow("Min. Temperature", self.minTemperatureSpinBox)
        temperatureLayout.addRow("Max. Temperature", self.maxTemperatureSpinBox)

        humidityLayout = QtWidgets.QFormLayout()
        humidityLayout.addRow("Min. Humidity", self.minHumiditySpinBox)
        humidityLayout.addRow("Max. Humidity", self.maxHumiditySpinBox)

        setpointsLayout = QtWidgets.QGridLayout(self.setpointsGroupBox)
        setpointsLayout.addLayout(temperatureLayout, 0, 0)
        setpointsLayout.addLayout(humidityLayout, 0, 1)

        # Status

        self.biasVoltageLineEdit = QtWidgets.QLineEdit(f"{0:G} V")
        self.biasVoltageLineEdit.setReadOnly(True)

        self.chuckTemperatureAction = QtWidgets.QAction()
        self.chuckTemperatureAction.setIcon(QtGui.QIcon.fromTheme("icons:warning.svg"))
        self.chuckTemperatureAction.setStatusTip("Chuck temperature out of bounds")
        self.chuckTemperatureAction.setVisible(False)

        self.chuckTemperatureLineEdit = QtWidgets.QLineEdit()
        self.chuckTemperatureLineEdit.setReadOnly(True)
        self.chuckTemperatureLineEdit.addAction(self.chuckTemperatureAction, QtWidgets.QLineEdit.TrailingPosition)

        self.boxTemperatureAction = QtWidgets.QAction()
        self.boxTemperatureAction.setIcon(QtGui.QIcon.fromTheme("icons:warning.svg"))
        self.boxTemperatureAction.setStatusTip("Box temperature out of bounds")
        self.boxTemperatureAction.setVisible(False)

        self.boxTemperatureLineEdit = QtWidgets.QLineEdit()
        self.boxTemperatureLineEdit.setReadOnly(True)
        self.boxTemperatureLineEdit.addAction(self.boxTemperatureAction, QtWidgets.QLineEdit.TrailingPosition)

        self.boxHumidityAction = QtWidgets.QAction()
        self.boxHumidityAction.setIcon(QtGui.QIcon.fromTheme("icons:warning.svg"))
        self.boxHumidityAction.setStatusTip("Box humidity out of bounds")
        self.boxHumidityAction.setVisible(False)

        self.boxHumidityLineEdit = QtWidgets.QLineEdit()
        self.boxHumidityLineEdit.setReadOnly(True)
        self.boxHumidityLineEdit.addAction(self.boxHumidityAction, QtWidgets.QLineEdit.TrailingPosition)

        self.boxDewPointAction = QtWidgets.QAction()
        self.boxDewPointAction.setIcon(QtGui.QIcon.fromTheme("icons:warning.svg"))
        self.boxDewPointAction.setStatusTip("Box dew point out of bounds")
        self.boxDewPointAction.setVisible(False)

        self.boxDewPointLineEdit = QtWidgets.QLineEdit()
        self.boxDewPointLineEdit.setReadOnly(True)
        self.boxDewPointLineEdit.addAction(self.boxDewPointAction, QtWidgets.QLineEdit.TrailingPosition)

        self.boxLightAction = QtWidgets.QAction()
        self.boxLightAction.setIcon(QtGui.QIcon.fromTheme("icons:warning.svg"))
        self.boxLightAction.setStatusTip("Box not dimmed")
        self.boxLightAction.setVisible(False)

        self.boxLightLineEdit = QtWidgets.QLineEdit()
        self.boxLightLineEdit.setReadOnly(True)
        self.boxLightLineEdit.addAction(self.boxLightAction, QtWidgets.QLineEdit.TrailingPosition)

        self.boxDoorAction = QtWidgets.QAction()
        self.boxDoorAction.setIcon(QtGui.QIcon.fromTheme("icons:warning.svg"))
        self.boxDoorAction.setStatusTip("Box door is open")
        self.boxDoorAction.setVisible(False)

        self.boxDoorLineEdit = QtWidgets.QLineEdit()
        self.boxDoorLineEdit.setReadOnly(True)
        self.boxDoorLineEdit.addAction(self.boxDoorAction, QtWidgets.QLineEdit.TrailingPosition)

        self.currentStripLineEdit = QtWidgets.QLineEdit()
        self.currentStripLineEdit.setReadOnly(True)

        self.currentItemLineEdit = QtWidgets.QLineEdit()
        self.currentItemLineEdit.setReadOnly(True)

        self.sequenceProgressBar = QtWidgets.QProgressBar()
        self.sequenceProgressBar.setVisible(False)
        self.sequenceProgressBar.setRange(0, 1)

        self.sequenceEstimationLabel = QtWidgets.QLabel()

        self.statusGroupBox = QtWidgets.QGroupBox("Status")
        statusFormLayout = QtWidgets.QFormLayout()
        statusFormLayout.addRow("Bias Voltage:", self.biasVoltageLineEdit)
        statusFormLayout.addRow("Current Strip:", self.currentStripLineEdit)
        statusFormLayout.addRow("Current Measurement:", self.currentItemLineEdit)
        statusGroupBoxLayout = QtWidgets.QVBoxLayout(self.statusGroupBox)
        statusGroupBoxLayout.addLayout(statusFormLayout)
        statusGroupBoxLayout.addWidget(self.sequenceProgressBar, 0)
        statusGroupBoxLayout.addWidget(self.sequenceEstimationLabel, 0)
        statusGroupBoxLayout.addStretch()

        self.environGroupBox = QtWidgets.QGroupBox("Environment")
        environGroupBoxLayout = QtWidgets.QFormLayout(self.environGroupBox)
        environGroupBoxLayout.addRow("Chuck Temperature:", self.chuckTemperatureLineEdit)
        environGroupBoxLayout.addRow("Box Temperature:", self.boxTemperatureLineEdit)
        environGroupBoxLayout.addRow("Box Humidity:", self.boxHumidityLineEdit)
        environGroupBoxLayout.addRow("Box Dew Point:", self.boxDewPointLineEdit)
        environGroupBoxLayout.addRow("Box Light:", self.boxLightLineEdit)
        environGroupBoxLayout.addRow("Box Door:", self.boxDoorLineEdit)

        self.statusLayout = QtWidgets.QHBoxLayout()
        self.statusLayout.addWidget(self.statusGroupBox)
        self.statusLayout.addWidget(self.environGroupBox)

        # Output path

        self.pathLabel = QtWidgets.QLabel("Output Path")

        self.pathLineEdit = QtWidgets.QLineEdit()
        self.pathLineEdit.textChanged.connect(self.outputPathChanged)

        self.pathButton = QtWidgets.QPushButton("...")
        self.pathButton.setMaximumWidth(24)
        self.pathButton.setStatusTip("Select output path")
        self.pathButton.clicked.connect(self.selectOutputPath)

        self.pathLayout = QtWidgets.QHBoxLayout()
        self.pathLayout.addWidget(self.pathLineEdit)
        self.pathLayout.addWidget(self.pathButton)

        # Operator name

        self.operatorLabel = QtWidgets.QLabel("Operator")

        self.operatorLineEdit = QtWidgets.QLineEdit()

        # Control widget

        self.controlWidget = QtWidgets.QWidget()

        self.controlWidgetLayout = QtWidgets.QVBoxLayout(self.controlWidget)
        self.controlWidgetLayout.addWidget(self.nameLabel)
        self.controlWidgetLayout.addLayout(self.nameLayout)
        self.controlWidgetLayout.addWidget(self.profileLabel)
        self.controlWidgetLayout.addWidget(self.profileComboBox)
        self.controlWidgetLayout.addWidget(self.sequenceLabel)
        self.controlWidgetLayout.addWidget(self.sequenceWidget)
        self.controlWidgetLayout.addWidget(self.parametersLabel)
        self.controlWidgetLayout.addWidget(self.parametersTreeWidget)
        self.controlWidgetLayout.addWidget(self.optionsGroupBox)
        self.controlWidgetLayout.addWidget(self.setpointsGroupBox)
        self.controlWidgetLayout.addLayout(self.statusLayout)
        self.controlWidgetLayout.addStretch()
        self.controlWidgetLayout.addWidget(self.pathLabel)
        self.controlWidgetLayout.addLayout(self.pathLayout)
        self.controlWidgetLayout.addWidget(self.operatorLabel)
        self.controlWidgetLayout.addWidget(self.operatorLineEdit)
        self.controlWidgetLayout.setStretch(0, 0)
        self.controlWidgetLayout.setStretch(1, 0)
        self.controlWidgetLayout.setStretch(2, 0)
        self.controlWidgetLayout.setStretch(3, 4)
        self.controlWidgetLayout.setStretch(4, 0)
        self.controlWidgetLayout.setStretch(5, 2)
        self.controlWidgetLayout.setStretch(6, 0)
        self.controlWidgetLayout.setStretch(7, 1)
        self.controlWidgetLayout.setStretch(8, 0)

        # Mapping sequence item type to series

        self.itemToSeriesMapping = {
            "iv": ["iv"],
            "cv": ["cv", "cvfd"],
            "rpoly": ["rpoly"],
            "istrip": ["istrip"],
            "idiel": ["idiel"],
            "cac": ["cac"],
            "cint": ["cint"],
            "rint": ["rint"],
            "idark": ["idark"],
        }

        # Plots

        self.ivcPlotAreaWidget = PlotAreaWidget()
        self.ivcPlotAreaWidget.addPlotWidget("iv", IVPlotWidget("IV"))
        self.ivcPlotAreaWidget.addPlotWidget("cv", CVPlotWidget("CV"))
        self.ivcPlotAreaWidget.addPlotWidget("cvfd", CV2PlotWidget("CV full depletion"))

        # Apply transformation on plot data
        self.ivcPlotAreaWidget.setTransformation("iv", lambda x, y: (x, abs(y)))
        self.ivcPlotAreaWidget.setTransformation("cv", lambda x, y: (x, abs(y)))
        self.ivcPlotAreaWidget.setTransformation("cvfd", lambda x, y: cv_inverse_square(x, abs(y)))

        # TODO move to plots?
        self.ivcPlotAreaWidget.setMapping("iv", "bias_smu_v", "bias_smu_i")
        self.ivcPlotAreaWidget.setMapping("cv", "bias_smu_v", "lcr_cp")
        self.ivcPlotAreaWidget.setMapping("cvfd", "bias_smu_v", "lcr_cp")

        self.stripscanPlotAreaWidget = PlotAreaWidget()
        self.stripscanPlotAreaWidget.addPlotWidget("rpoly", RStripPlotWidget("Rpoly"), True)
        self.stripscanPlotAreaWidget.addPlotWidget("istrip", IStripPlotWidget("Istrip"), True)
        self.stripscanPlotAreaWidget.addPlotWidget("idiel", IStripPlotWidget("Idiel"), True)
        self.stripscanPlotAreaWidget.addPlotWidget("cac", CStripPlotWidget("Cac"), True)
        self.stripscanPlotAreaWidget.addPlotWidget("cint", CStripPlotWidget("Cint"), True)
        self.stripscanPlotAreaWidget.addPlotWidget("rint", RStripPlotWidget("Rint"), True)
        self.stripscanPlotAreaWidget.addPlotWidget("idark", IStripPlotWidget("Idark"), True)
        self.stripscanPlotAreaWidget.addPlotWidget("repeat", RecontactPlotWidget("Repeat Histogram"), True)

        # Apply transformation on plot data
        self.stripscanPlotAreaWidget.setTransformation("rpoly", lambda x, y: (x, abs(y)))
        self.stripscanPlotAreaWidget.setTransformation("istrip", lambda x, y: (x, abs(y)))
        self.stripscanPlotAreaWidget.setTransformation("idiel", lambda x, y: (x, abs(y)))
        self.stripscanPlotAreaWidget.setTransformation("cac", lambda x, y: CStripPlotWidget.transform(x, abs(y)))  # TODO
        self.stripscanPlotAreaWidget.setTransformation("cint", lambda x, y: CStripPlotWidget.transform(x, abs(y)))  # TODO
        self.stripscanPlotAreaWidget.setTransformation("rint", lambda x, y: (x, abs(y)))
        self.stripscanPlotAreaWidget.setTransformation("idark", lambda x, y: (x, abs(y)))

        # TODO move to plots?
        self.stripscanPlotAreaWidget.setMapping("rpoly", "strip_index", "rpoly_r")
        self.stripscanPlotAreaWidget.setMapping("istrip", "strip_index", "istrip_i")
        self.stripscanPlotAreaWidget.setMapping("idiel", "strip_index", "idiel_i")
        self.stripscanPlotAreaWidget.setMapping("cac", "strip_index", "cac_cp")
        self.stripscanPlotAreaWidget.setMapping("cint", "strip_index", "cint_cp")
        self.stripscanPlotAreaWidget.setMapping("rint", "strip_index", "rint_r")
        self.stripscanPlotAreaWidget.setMapping("idark", "strip_index", "idark_i")

        # Register plot areas

        self.plotAreaWidgets = []
        self.plotAreaWidgets.append(self.ivcPlotAreaWidget)
        self.plotAreaWidgets.append(self.stripscanPlotAreaWidget)

        # Content tabs

        self.contentTabWidget = QtWidgets.QTabWidget(self)
        self.contentTabWidget.addTab(self.ivcPlotAreaWidget, "IV/CV")
        self.contentTabWidget.addTab(self.stripscanPlotAreaWidget, "Stripscan")

        # Splitters

        self.horizontalSplitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.horizontalSplitter.setChildrenCollapsible(False)
        self.horizontalSplitter.addWidget(self.controlWidget)
        self.horizontalSplitter.addWidget(self.contentTabWidget)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.horizontalSplitter)

        # Environment timer

        self.environUpdateTimer = QtCore.QTimer()
        self.environUpdateTimer.timeout.connect(self.updateEnvironData)
        self.environUpdateTimer.start(500)

    def readSettings(self):
        settings = QtCore.QSettings()

        sampleNamePrefix = settings.value("sampleNamePrefix", "", str)
        self.setSampleNamePrefix(sampleNamePrefix)

        sampleNameInfix = settings.value("sampleNameInfix", "Unnamed", str)
        self.setSampleNameInfix(sampleNameInfix)

        sampleNameSuffix = settings.value("sampleNameSuffix", "", str)
        self.setSampleNameSuffix(sampleNameSuffix)

        self.clearSequence()

        with QtCore.QSignalBlocker(self.profileComboBox):
            self.profileComboBox.clear()
            for profile in readProfiles():
                self.profileComboBox.addItem(profile.get("name", ""), profile)
            self.profileComboBox.setCurrentIndex(-1)

        profileName = settings.value("profileName", "", str)
        index = self.profileComboBox.findText(profileName)
        self.profileComboBox.setCurrentIndex(index)

        remeasureCount = settings.value("remeasureCount", 0, int)
        self.setRemeasureCount(remeasureCount)

        recontactCount = settings.value("recontactCount", 0, int)
        self.setRecontactCount(recontactCount)

        minTemperature = settings.value("minTemperature", 20, float)
        maxTemperature = settings.value("maxTemperature", 24, float)
        self.setTemperatureRange(minTemperature, maxTemperature)

        minHumidity = settings.value("minHumidity", 5, float)
        maxHumidity = settings.value("maxHumidity", 10, float)
        self.setHumidityRange(minHumidity, maxHumidity)

        outputPath = settings.value("outputPath", "", str)
        self.setOutputPath(outputPath or os.path.expanduser("~"))

        operatorName = settings.value("operatorName", "", str)
        self.setOperatorName(operatorName)

        try:
            ivcLayoutIndex = settings.value("ivcLayoutIndex", 0, int)
            self.ivcPlotAreaWidget.setLayoutIndex(ivcLayoutIndex)
        except Exception as exc:
            logger.exception(exc)

        try:
            stripscanLayoutIndex = settings.value("stripscanLayoutIndex", 0, int)
            self.stripscanPlotAreaWidget.setLayoutIndex(stripscanLayoutIndex)
        except Exception as exc:
            logger.exception(exc)

        state = settings.value("horizontalSplitter/state", QtCore.QByteArray(), QtCore.QByteArray)
        if state.isEmpty():
            self.horizontalSplitter.setSizes([400, 900])
        else:
            self.horizontalSplitter.restoreState(state)

    def syncSettings(self):
        settings = QtCore.QSettings()

        settings.setValue("sampleNamePrefix", self.sampleNamePrefix())
        settings.setValue("sampleNameInfix", self.sampleNameInfix())
        settings.setValue("sampleNameSuffix", self.sampleNameSuffix())

        settings.setValue("profileName", self.profileComboBox.currentText())

        settings.setValue("remeasureCount", self.remeasureCount())
        settings.setValue("recontactCount", self.recontactCount())

        settings.setValue("minTemperature", self.minTemperature())
        settings.setValue("maxTemperature", self.maxTemperature())

        settings.setValue("minHumidity", self.minHumidity())
        settings.setValue("maxHumidity", self.maxHumidity())

        settings.setValue("outputPath", self.outputPath())
        settings.setValue("operatorName", self.operatorName())

        settings.setValue("ivcLayoutIndex", self.ivcPlotAreaWidget.layoutIndex())
        settings.setValue("stripscanLayoutIndex", self.stripscanPlotAreaWidget.layoutIndex())

        settings.setValue("horizontalSplitter/state", self.horizontalSplitter.saveState())

    # Sensor name

    def sensorName(self) -> str:
        return "".join((
            self.sampleNamePrefix(),
            self.sampleNameInfix(),
            self.sampleNameSuffix()
        ))

    def sampleNamePrefix(self) -> str:
        return self.namePrefixLineEdit.text().strip()

    def setSampleNamePrefix(self, prefix: str) -> None:
        self.namePrefixLineEdit.setText(prefix.strip())

    def sampleNameInfix(self) -> str:
        return self.nameInfixLineEdit.text().strip()

    def setSampleNameInfix(self, infix: str) -> None:
        self.nameInfixLineEdit.setText(infix.strip())

    def sampleNameSuffix(self) -> str:
        return self.nameSuffixLineEdit.text().strip()

    def setSampleNameSuffix(self, suffix: str) -> None:
        self.nameSuffixLineEdit.setText(suffix.strip())

    def sensorNameChanged(self):
        ...

    # Sensor Type

    def sensorCategory(self) -> str:
        data = self.profileComboBox.currentData() or {}
        return padfileCategory(data.get("padfile", ""))

    def sensorType(self) -> str:
        data = self.profileComboBox.currentData() or {}
        return padfileType(data.get("padfile", ""))

    def sensorFilename(self) -> str:
        data = self.profileComboBox.currentData() or {}
        return data.get("padfile", "")

    def profileChanged(self, index: int) -> None:
        if self.context.data:
            name = self.profileComboBox.currentText()
            result = QtWidgets.QMessageBox.question(self, "Change Sensor Profile", f"Do you want to change the sensor profile to \"{name}\" and clear current data?")
            if result == QtWidgets.QMessageBox.No:
                with QtCore.QSignalBlocker(self.profileComboBox):
                    self.profileComboBox.setCurrentIndex(self.profileComboBoxPreviousIndex)
                return
        self.profileComboBoxPreviousIndex = index
        self.reset()

    def reset(self) -> None:
        self.clearReadings()

        data = self.profileComboBox.currentData() or {}
        filename = data.get("padfile")
        if filename:
            self.loadPads(filename)

        self.clearSequence()
        filename = data.get("sequence")
        if filename:
            try:
                self.loadSequence(filename)
                logger.info("Loaded sequence file: %s", filename)
            except Exception as exc:
                logger.exception(exc)

        self.setInputsLocked(False)

    # Padfile

    def loadPads(self, filename: str) -> None:
        try:
            self.context.load_padfile(filename)
            logger.info("Imported pads: %s", filename)
            self.setStrips({index: label for index, label in enumerate(self.context.padfile.pads.keys())})
        except Exception as exc:
            logger.exception(exc)
            logger.error("Failed to import pads from: %s", filename)
            QtWidgets.QMessageBox.critical(self, "Load Error", f"Failed to import pads from: {filename}")

    # Sequence

    def sequence(self):
        return self.sequenceWidget.allItems()

    def clearSequence(self) -> None:
        self.sequenceWidget.clear()

    def loadSequence(self, filename: str) -> None:
        self.clearSequence()
        self.clearReadings()
        self.resetCharts()
        with open(filename, "rt") as fp:
            sequence = load_sequence(fp)
        for item in loadSequenceItems(sequence):
            self.sequenceWidget.addSequenceItem(item)
            if not item.allChildren():
                self.addItemSeries(item)
            for child in item.allChildren():
                self.addStripSeries(child)
        self.sequenceWidget.resizeColumns()
        self.syncPlots()

    # Parameters

    def loadSequenceItemParameters(self, current, previous) -> None:
        self.parametersTreeWidget.clear()
        if current:
            self.parametersLabel.setText(f"Parameters ({current.fullName()})")
            try:
                for key, value in current.parameters().items():
                    item = QtWidgets.QTreeWidgetItem()
                    item.setText(0, key)
                    if isinstance(value, list):
                        item.setText(1, ", ".join((item for item in value)))
                    else:
                        item.setText(1, format(value))
                    self.parametersTreeWidget.addTopLevelItem(item)
            except Exception as exc:
                logger.exception(exc)

    # Status

    def addItemSeries(self, item):
        # TODO
        for seriesType in self.itemToSeriesMapping.get(item.typeName(), []):
            self.ivcPlotAreaWidget.addLineSeries(seriesType, item.fullName())

    def addStripSeries(self, item):
        # TODO
        for seriesType in self.itemToSeriesMapping.get(item.typeName(), []):
            self.stripscanPlotAreaWidget.addLineSeries(seriesType, item.fullName())

    def setStrips(self, strips: Dict[int, str]) -> None:
        self.stripscanPlotAreaWidget.setStrips(strips)

    # Data content

    def syncPlots(self):
        # TODO
        ranges = {}
        for item in self.sequence():
            if item.typeName() in ("iv", "cv"): # TODO!!
                r = ranges.setdefault(item.typeName(), [])
                r.append(float(item.parameters().get("voltage_begin", "0").strip("V")))
                r.append(float(item.parameters().get("voltage_end", "0").strip("V")))
        for key, values in ranges.items():
            if len(values) > 1:
                for seriesType in self.itemToSeriesMapping.get(key, []):
                    plot = self.ivcPlotAreaWidget.plotWidget(seriesType)
                    if plot:
                        minimum, maximum = min(values), max(values)
                        plot.setRange(minimum, maximum)

    def clearReadings(self) -> None:
        for widget in self.plotAreaWidgets:
            widget.clear()

    def updateData(self, namespace: str, type: str, name: str) -> None:
        try:
            items = self.context.data.get(namespace, {}).get(type, {}).get(name, [])
            for widget in self.plotAreaWidgets:
                for seriesType in self.itemToSeriesMapping.get(type, []):
                    if widget.plotWidget(seriesType):
                        widget.replace(seriesType, name, items)
        except Exception as exc:
            logger.exception(exc)

    def createRecontactHistogram(self):
        data = {}
        padfile = self.context.padfile
        statistics = self.context.statistics

        if padfile:
            remeasure_values = []
            for index, strip in enumerate(padfile.pads.keys()):
                counter = statistics.remeasure_counter.get(strip)
                remeasure_values.append(sum(counter.values()) if counter else 0)
            data["Remeasurements"] = remeasure_values

        if padfile:
            recontact_values = []
            for index, strip in enumerate(padfile.pads.keys()):
                counter = statistics.recontact_counter.get(strip)
                recontact_values.append(sum(counter.values()) if counter else 0)
            data["Recontacts"] = recontact_values

        return data

    def updateHistograms(self) -> None:
        try:
            for widget in self.plotAreaWidgets:
                repeatWidget = widget.plotWidget("repeat")
                if repeatWidget:
                    data = self.createRecontactHistogram()
                    repeatWidget.replaceData(data)
        except Exception as exc:
            logger.exception(exc)

    def resetCharts(self) -> None:
        for widget in self.plotAreaWidgets:
            widget.reset()

    # Status

    def setBiasVoltage(self, level: float) -> None:
        self.biasVoltageLineEdit.setText(f"{level:G} V")

    def currentStrip(self) -> str:
        return self.currentStripLineEdit.text()

    def setCurrentStrip(self, name: str) -> None:
        if name:
            self.currentStripLineEdit.setText(name)
        else:
            self.currentStripLineEdit.clear()

    def setCurrentItem(self, item: SequenceItem) -> None:
        if item:
            self.currentItemLineEdit.setText(item.fullName())
        else:
            self.currentItemLineEdit.clear()

    def setStripscanProgress(self, strip: int, strips: int) -> None:
        self.sequenceProgressBar.setVisible(strips > 0)
        self.sequenceProgressBar.setRange(0, strips)
        self.sequenceProgressBar.setValue(strip)
        self.sequenceEstimationLabel.setVisible(strips > 0)

    def setStripscanEstimation(self, elapsed, remaining) -> None:
        elapsedValue = format(elapsed).split(".")[0]
        remainingValue = format(remaining).split(".")[0]
        self.sequenceEstimationLabel.setText(f"Elapsed {elapsedValue} / Remaining {remainingValue}")

    # Environment

    def updateEnvironData(self) -> None:
        data = self.context.station.box_environment()
        self.setChuckTemperature(data.get("pt100_1", float("nan")))
        self.setBoxTemperature(data.get("box_temperature", float("nan")))
        self.setBoxHumidity(data.get("box_humidity", float("nan")))
        self.setBoxDewPoint(data.get("box_dewpoint", float("nan")))
        self.setBoxLight(data.get("box_light"), data.get("box_lux", float("nan")))
        self.setBoxDoorState(data.get("box_door"))

    def setChuckTemperature(self, temperature: float) -> None:
        text = formatTemperature(temperature)
        self.chuckTemperatureLineEdit.setText(text)
        minimum, maximum = self.temperatureRange()
        if minimum <= temperature <= maximum:
            color = Colors.green
            self.chuckTemperatureAction.setVisible(False)
        else:
            color = Colors.red
            self.chuckTemperatureAction.setVisible(True)
        setForeground(self.chuckTemperatureLineEdit, color)

    def setBoxTemperature(self, temperature: float) -> None:
        text = formatTemperature(temperature)
        self.boxTemperatureLineEdit.setText(text)
        minimum, maximum = self.temperatureRange()
        if minimum <= temperature <= maximum:
            color = Colors.green
            self.boxTemperatureAction.setVisible(False)
        else:
            color = Colors.red
            self.boxTemperatureAction.setVisible(True)
        setForeground(self.boxTemperatureLineEdit, color)

    def setBoxHumidity(self, humidity: float) -> None:
        text = formatHumidity(humidity)
        self.boxHumidityLineEdit.setText(text)
        minimum, maximum = self.humidityRange()
        if minimum <= humidity <= maximum:
            color = Colors.green
            self.boxHumidityAction.setVisible(False)
        else:
            color = Colors.red
            self.boxHumidityAction.setVisible(True)
        setForeground(self.boxHumidityLineEdit, color)

    def setBoxDewPoint(self, dewPoint: float) -> None:
        text = formatTemperature(dewPoint)
        self.boxDewPointLineEdit.setText(text)
        if math.isfinite(dewPoint):
            color = Colors.green
            self.boxDewPointAction.setVisible(False)
        else:
            color = Colors.red
            self.boxDewPointAction.setVisible(True)
        setForeground(self.boxDewPointLineEdit, color)

    def setBoxLight(self, state: bool, lux: float) -> None:
        textState = {True: "ON", False: "OFF"}.get(state, "n/a")
        textLux = f"{lux:.1f} Lux" if math.isfinite(lux) else "n/a"
        self.boxLightLineEdit.setText(f"{textState} ({textLux})")
        hasLight = (state != False or lux > 0)
        color = QtGui.QColor({True: Colors.red, False: Colors.green}.get(hasLight, Colors.red))
        setForeground(self.boxLightLineEdit, color)
        self.boxLightAction.setVisible(hasLight)

    def setBoxDoorState(self, state: bool) -> None:
        isClosed = state == False
        text = {True: "OPEN", False: "CLOSED"}.get(state, "n/a")
        self.boxDoorLineEdit.setText(text)
        color = QtGui.QColor({True: Colors.red, False: Colors.green}.get(state, Colors.red))
        setForeground(self.boxDoorLineEdit, color)
        self.boxDoorAction.setVisible(not isClosed)

    # Options

    def remeasureCount(self) -> int:
        return self.remeasureCountSpinBox.value()

    def setRemeasureCount(self, count: int) -> None:
        self.remeasureCountSpinBox.setValue(count)

    def recontactCount(self) -> int:
        return self.recontactCountSpinBox.value()

    def setRecontactCount(self, count: int) -> None:
        self.recontactCountSpinBox.setValue(count)

    # Setpoints

    def minTemperature(self) -> float:
        return self.minTemperatureSpinBox.value()

    def maxTemperature(self) -> float:
        return self.maxTemperatureSpinBox.value()

    def temperatureRange(self) -> Tuple[float, float]:
        return self.minTemperature(), self.maxTemperature()

    def setTemperatureRange(self, minimum, maximum):
        if maximum < minimum:
            maximum = minimum
        self.minTemperatureSpinBox.setValue(minimum)
        self.maxTemperatureSpinBox.setValue(maximum)
        self.minTemperatureSpinBox.setMaximum(maximum)
        self.maxTemperatureSpinBox.setMinimum(minimum)
        self.context.parameters.update({
            "minimum_temperature": minimum,
            "maximum_temperature": maximum,
        })

    def syncTemperature(self):
        self.setTemperatureRange(self.minTemperature(), self.maxTemperature())

    def minHumidity(self) -> float:
        return self.minHumiditySpinBox.value()

    def maxHumidity(self) -> float:
        return self.maxHumiditySpinBox.value()

    def humidityRange(self) -> Tuple[float, float]:
        return self.minHumidity(), self.maxHumidity()

    def setHumidityRange(self, minimum, maximum):
        if maximum < minimum:
            maximum = minimum
        self.minHumiditySpinBox.setValue(minimum)
        self.maxHumiditySpinBox.setValue(maximum)
        self.minHumiditySpinBox.setMaximum(maximum)
        self.maxHumiditySpinBox.setMinimum(minimum)
        self.context.parameters.update({
            "minimum_humidity": minimum,
            "maximum_humidity": maximum,
        })

    def syncHumidity(self):
        self.setHumidityRange(self.minHumidity(), self.maxHumidity())

    # Output path

    def outputPath(self) -> str:
        return self.pathLineEdit.text().strip()

    def setOutputPath(self, path: str) -> None:
        self.pathLineEdit.setText(path)

    def selectOutputPath(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Output Directory", self.outputPath())
        if path:
            self.setOutputPath(path)

    # Operator

    def operatorName(self) -> str:
        return self.operatorLineEdit.text().strip()

    def setOperatorName(self, name: str) -> None:
        self.operatorLineEdit.setText(name)

    # Others

    def showSequenceItem(self, item):
        self.sequenceWidget.scrollToItem(item)

    def setLocked(self, locked: bool) -> None:
        enabled = not locked
        self.sequenceWidget.setLocked(locked)

    def setInputsLocked(self, locked: bool) -> None:
        enabled = not locked
        self.namePrefixLineEdit.setEnabled(enabled)
        self.nameInfixLineEdit.setEnabled(enabled)
        self.nameSuffixLineEdit.setEnabled(enabled)
        self.remeasureCountSpinBox.setEnabled(enabled)
        self.recontactCountSpinBox.setEnabled(enabled)
        self.profileComboBox.setEnabled(enabled)
        self.pathLineEdit.setEnabled(enabled)
        self.pathButton.setEnabled(enabled)
        self.operatorLineEdit.setEnabled(enabled)

    # Transformed positions

    def updateContext(self):
        self.context.parameters.update({
            "sensor_name": self.sensorName(),
            "sensor_type": self.sensorType(),
            "operator_name": self.operatorName(),
            "remeasure_count": self.remeasureCount(),
            "recontact_count": self.recontactCount(),
            "output_path": self.outputPath()
        })

    def shutdown(self):
        self.environUpdateTimer.stop()
