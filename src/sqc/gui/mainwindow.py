import logging
import traceback
import os
from pathlib import Path
from typing import List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from ..settings import Settings
from ..core.pluginmanager import PluginManager

from . import aboutMessage, showContents, showGithub
from .dashboard import DashboardWidget, formatTemperature, formatHumidity
from .profiles import ProfilesDialog, readProfiles
from .resources import ResourcesDialog
from .preferences import PreferencesDialog
from .databrowser import DataBrowserWindow
from .alignment import AlignmentDialog
from .sequence import SequenceController
from .recover import RecoverDialog

__all__ = ["MainWindow"]

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):

    startRequested = QtCore.pyqtSignal()
    stopRequested = QtCore.pyqtSignal()

    def __init__(self, context, parent=None):
        super().__init__(parent)

        self.context = context

        self.pluginManager = PluginManager()

        # Actions

        self.newMeasurementAction = QtWidgets.QAction("&New Measurement...")
        self.newMeasurementAction.setToolTip("New Measurement")
        self.newMeasurementAction.setStatusTip("Create a new measurement")
        self.newMeasurementAction.setIcon(QtGui.QIcon("icons:document-new.svg"))
        self.newMeasurementAction.triggered.connect(self.newMeasurement)

        self.quitAction = QtWidgets.QAction("&Quit")
        self.quitAction.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        self.quitAction.triggered.connect(self.close)

        self.profilesAction = QtWidgets.QAction("Sensor &Profiles...")
        self.profilesAction.setStatusTip("Manage sensor profiles")
        self.profilesAction.triggered.connect(self.showProfiles)

        self.resourcesAction = QtWidgets.QAction("&Resources...")
        self.resourcesAction.triggered.connect(self.showResources)

        self.preferencesAction = QtWidgets.QAction("Pre&ferences...")
        self.preferencesAction.triggered.connect(self.showPreferences)

        self.dataBrowserAction = QtWidgets.QAction("Data &Browser")
        self.dataBrowserAction.setIcon(QtGui.QIcon.fromTheme("icons:view-browser.svg"))
        self.dataBrowserAction.setStatusTip("Browse previous measurement data")
        self.dataBrowserAction.setCheckable(True)
        self.dataBrowserAction.setChecked(False)
        self.dataBrowserAction.triggered.connect(self.setDataBrowserVisible)

        self.startAction = QtWidgets.QAction("&Start")
        self.startAction.setStatusTip("Run measurement sequence")
        self.startAction.setIcon(QtGui.QIcon("icons:sequence-start.svg"))
        self.startAction.triggered.connect(self.requestStart)

        self.suspendAction = QtWidgets.QAction("S&uspend")
        self.suspendAction.setStatusTip("Suspend measurement sequence")
        self.suspendAction.setIcon(QtGui.QIcon("icons:sequence-suspend.svg"))
        self.suspendAction.setCheckable(True)
        self.suspendAction.toggled.connect(self.toggleSuspend)

        self.stopAction = QtWidgets.QAction("Sto&p")
        self.stopAction.setStatusTip("Abort measurement sequence")
        self.stopAction.setIcon(QtGui.QIcon("icons:sequence-stop.svg"))
        self.stopAction.triggered.connect(self.requestStop)

        self.alignmentAction = QtWidgets.QAction("&Alignment")
        self.alignmentAction.setIcon(QtGui.QIcon.fromTheme("icons:alignment.svg"))
        self.alignmentAction.setStatusTip("Show sensor alignment dialog")
        self.alignmentAction.triggered.connect(self.showAlignmentDialog)

        self.recoverAction = QtWidgets.QAction("Recover Station")
        self.recoverAction.setIcon(QtGui.QIcon.fromTheme("icons:recover.svg"))
        self.recoverAction.setStatusTip("Safely recover station by ramping down SMUs, discarge and releasing switches")
        self.recoverAction.triggered.connect(self.showRecoverStation)

        self.boxFlashingLightAction = QtWidgets.QAction("Box Flashing Light")
        self.boxFlashingLightAction.setIcon(QtGui.QIcon.fromTheme("icons:flashing-light.svg"))
        self.boxFlashingLightAction.setStatusTip("Toggle box flashing light")
        self.boxFlashingLightAction.setCheckable(True)
        self.boxFlashingLightAction.toggled.connect(self.toggleBoxFlashingLight)

        self.boxLightAction = QtWidgets.QAction("Box Light")
        self.boxLightAction.setIcon(QtGui.QIcon.fromTheme("icons:light.svg"))
        self.boxLightAction.setStatusTip("Toggle box and microscope light")
        self.boxLightAction.setCheckable(True)
        self.boxLightAction.triggered.connect(self.toggleBoxLight)

        self.identifyAction = QtWidgets.QAction("Identify Instruments")
        self.identifyAction.setStatusTip("Identify Instruments")
        self.identifyAction.setVisible(False)
        self.identifyAction.triggered.connect(self.showIdentify)

        self.contentsAction = QtWidgets.QAction("&Contents")
        self.contentsAction.setShortcut(QtGui.QKeySequence("F1"))
        self.contentsAction.triggered.connect(self.showContents)

        self.githubAction = QtWidgets.QAction(self)
        self.githubAction.setText("&GitHub")
        self.githubAction.triggered.connect(self.showGithub)

        self.aboutQtAction = QtWidgets.QAction("&About Qt")
        self.aboutQtAction.triggered.connect(self.showAboutQt)

        self.aboutAction = QtWidgets.QAction("&About")
        self.aboutAction.triggered.connect(self.showAbout)

        # Menus

        self.fileMenu = self.menuBar().addMenu("&File")
        self.fileMenu.addAction(self.newMeasurementAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.quitAction)

        self.editMenu = self.menuBar().addMenu("&Edit")
        self.editMenu.addAction(self.profilesAction)
        self.editMenu.addAction(self.resourcesAction)
        self.editMenu.addSeparator()
        self.editMenu.addAction(self.preferencesAction)

        self.viewMenu = self.menuBar().addMenu("&View")
        self.viewMenu.addAction(self.dataBrowserAction)

        self.sequenceMenu = self.menuBar().addMenu("&Sequence")
        self.sequenceMenu.addAction(self.startAction)
        self.sequenceMenu.addAction(self.suspendAction)
        self.sequenceMenu.addAction(self.stopAction)
        self.sequenceMenu.addSeparator()
        self.sequenceMenu.addAction(self.alignmentAction)

        self.toolsMenu = self.menuBar().addMenu("&Tools")
        self.toolsMenu.addAction(self.recoverAction)
        self.toolsMenu.addAction(self.boxFlashingLightAction)
        self.toolsMenu.addAction(self.boxLightAction)
        self.toolsMenu.addAction(self.identifyAction)

        self.helpMenu = self.menuBar().addMenu("&Help")
        self.helpMenu.addAction(self.contentsAction)
        self.helpMenu.addAction(self.githubAction)
        self.helpMenu.addSeparator()
        self.helpMenu.addAction(self.aboutQtAction)
        self.helpMenu.addAction(self.aboutAction)

        # Toolbars

        self.toolBar = self.addToolBar("Toolbar")
        self.toolBar.setObjectName("toolbar")
        self.toolBar.setMovable(False)
        self.toolBar.setFloatable(False)
        self.toolBar.addAction(self.newMeasurementAction)
        self.toolBar.addSeparator()
        self.toolBar.addActions(self.viewMenu.actions())
        self.toolBar.addSeparator()
        self.toolBar.addActions(self.sequenceMenu.actions())
        self.toolBar.addSeparator()
        self.toolBar.addActions(self.toolsMenu.actions())
        spacer = QtWidgets.QWidget(self.toolBar)
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.toolBar.addWidget(spacer)
        self.toolBarStateLabel = QtWidgets.QLabel()
        self.toolBarStateLabel.setStyleSheet("QLabel{margin-right: 4px; font-weight: bold; color: blue;}")
        self.toolBar.addWidget(self.toolBarStateLabel)

        # Sequence

        self.dashboardWidget = DashboardWidget(self.context, self)
        self.setCentralWidget(self.dashboardWidget)

        self.sequenceController = SequenceController(self.context, self)
        self.sequenceController.started.connect(self.sequenceStarted)
        self.sequenceController.finished.connect(self.sequenceFinished)
        self.sequenceController.failed.connect(self.context.handle_exception)

        # Data Browser

        self.dataBrowserWindow = DataBrowserWindow(self)
        self.dataBrowserWindow.hide()
        self.dataBrowserWindow.setRootPath(self.dashboardWidget.outputPath())
        self.dataBrowserWindow.visibilityChanged.connect(self.dataBrowserAction.setChecked)
        self.dashboardWidget.outputPathChanged.connect(self.dataBrowserWindow.setRootPath)

        # Status bar

        self.messageLabel = QtWidgets.QLabel()
        self.statusBar().addPermanentWidget(self.messageLabel)

        self.progressBar = QtWidgets.QProgressBar()
        self.progressBar.setFixedWidth(300)
        self.statusBar().addPermanentWidget(self.progressBar)

        # Signals

        self.context.message_changed.connect(self.setMessage)
        self.context.progress_changed.connect(self.setProgress)
        self.context.exception_raised.connect(self.showException)
        self.context.suspended.connect(self.setSuspended)
        self.context.box_light_changed.connect(self.boxLightAction.setChecked)

        # States

        self.idleState = QtCore.QState()
        self.idleState.entered.connect(self.enterIdleState)

        self.runningState = QtCore.QState()
        self.runningState.entered.connect(self.enterRunningState)

        self.abortingState = QtCore.QState()
        self.abortingState.entered.connect(self.enterAbortingState)

        # Transitions

        self.idleState.addTransition(self.startRequested, self.runningState)

        self.runningState.addTransition(self.stopRequested, self.abortingState)
        self.runningState.addTransition(self.sequenceController.finished, self.idleState)

        self.abortingState.addTransition(self.sequenceController.finished, self.idleState)

        # State machine

        self.stateMachine = QtCore.QStateMachine()
        self.stateMachine.addState(self.idleState)
        self.stateMachine.addState(self.runningState)
        self.stateMachine.addState(self.abortingState)
        self.stateMachine.setInitialState(self.idleState)

        self.stateMachine.start()

    def readSettings(self) -> None:
        self.pluginManager.dispatch("beforeReadSettings", (QtCore.QSettings(),))
        try:
            settings = QtCore.QSettings()
            settings.beginGroup("mainwindow")

            geometry = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)
            if not self.restoreGeometry(geometry):
                self.resize(800, 600)

            state = settings.value("state", QtCore.QByteArray(), QtCore.QByteArray)
            self.restoreState(state)

            settings.endGroup()
        except Exception as exc:
            logger.exception(exc)

        self.dashboardWidget.readSettings()
        self.dataBrowserWindow.readSettings()

        self.pluginManager.dispatch("afterReadSettings", (QtCore.QSettings(),))

    def writeSettings(self) -> None:
        self.pluginManager.dispatch("beforeWriteSettings", (QtCore.QSettings(),))

        settings = QtCore.QSettings()
        settings.beginGroup("mainwindow")

        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())

        settings.endGroup()

        self.dashboardWidget.writeSettings()
        self.dataBrowserWindow.writeSettings()

        self.pluginManager.dispatch("afterWriteSettings", (QtCore.QSettings(),))

    # Lock

    def isLocked(self) -> bool:
        return self.property("locked") or False

    def setLocked(self, state: bool) -> None:
        self.setProperty("locked", state)

    # Plugins

    def registerPlugin(self, plugin) -> None:
        self.pluginManager.register_plugin(plugin)

    def installPlugins(self):
        self.pluginManager.dispatch("install", (self,))

    def uninstallPlugins(self):
        self.pluginManager.dispatch("uninstall", (self,))

    # Shutdown

    def shutdown(self):
        self.dashboardWidget.shutdown()
        self.sequenceController.shutdown()
        self.stateMachine.stop()

    # Overloaded slots

    def closeEvent(self, event):
        if self.isLocked():
            self.showLockedNotification()
            event.ignore()
        else:
            if self.confirmShutdown():
                self.dataBrowserWindow.close()
                event.accept()
            else:
                event.ignore()

    # File

    @QtCore.pyqtSlot()
    def newMeasurement(self):
        result = QtWidgets.QMessageBox.question(
            self,
            "New Measurement",
            "Do you want to prepare a new measurement?\n\nThis will clear all plots and restore default sequence configuration."
        )
        if result == QtWidgets.QMessageBox.Yes:
            self.context.reset()
            self.context.reset_data()
            self.dashboardWidget.reset()
            self.dashboardWidget.updateContext()

    # Edit

    @QtCore.pyqtSlot()
    def showProfiles(self) -> None:
        try:
            # TODO
            currentProfile = self.dashboardWidget.profileComboBox.currentData()
            dialog = ProfilesDialog(self)
            dialog.readSettings()
            dialog.exec()
            dialog.writeSettings()
            # TODO
            with QtCore.QSignalBlocker(self.dashboardWidget.profileComboBox):
                self.dashboardWidget.profileComboBox.clear()
                for profile in readProfiles():
                    self.dashboardWidget.profileComboBox.addItem(profile.get("name", ""), profile)
                self.dashboardWidget.profileComboBox.setCurrentIndex(-1)
                index = self.dashboardWidget.profileComboBox.findData(currentProfile)
                self.dashboardWidget.profileComboBox.setCurrentIndex(index)
        except Exception as exc:
            logger.exception(exc)

    @QtCore.pyqtSlot()
    def showResources(self) -> None:
        try:
            dialog = ResourcesDialog(self)
            dialog.readSettings()
            resources = Settings().resources()
            dialog.setResources(resources)
            dialog.exec()
            dialog.writeSettings()
            if dialog.result() == dialog.Accepted:
                Settings().setResources(dialog.resources())
        except Exception as exc:
            logger.exception(exc)

    @QtCore.pyqtSlot()
    def showPreferences(self) -> None:
        try:
            dialog = PreferencesDialog(self)
            dialog.readSettings()
            self.pluginManager.dispatch("beforePreferences", (dialog,))
            dialog.loadValues()
            dialog.exec()
            if dialog.result() == dialog.Accepted:
                dialog.saveValues()
            self.pluginManager.dispatch("afterPreferences", (dialog,))
            dialog.writeSettings()
        except Exception as exc:
            logger.exception(exc)

    # View

    def setDataBrowserVisible(self, checked: bool) -> None:
        self.dataBrowserWindow.setVisible(checked)

    # Sequence

    def setSuspended(self):
        self.suspendAction.setEnabled(True)

    def toggleSuspend(self, checked) -> None:
        if checked:
            self.suspendAction.setEnabled(False)
            self.context.request_suspend()
        else:
            self.context.request_continue()

    def showAlignmentDialog(self) -> None:
        self.dashboardWidget.updateContext()
        name = self.dashboardWidget.sensorProfileName()
        self.context.keep_light_flashing = False  # TODO
        dialog = AlignmentDialog(self.context)
        try:
            dialog.setSensorName(name)
            dialog.setPadfile(self.context.padfile)
            dialog.readSettings()
            dialog.setLightsOn()
            dialog.setJoystickEnabled(False)
            dialog.exec()
            dialog.writeSettings()
            try:
                self.boxFlashingLightAction.setChecked(self.context.keep_light_flashing or self.boxFlashingLightAction.isChecked())  # TODO
            except Exception:
                ...
            self.handleAutoStart()
        except Exception as exc:
            logger.exception(exc)
        finally:
            dialog.shutdown()

    def showRecoverStation(self) -> None:
        dialog = RecoverDialog(self.context)
        dialog.run()

    def toggleBoxFlashingLight(self, state) -> None:
        try:
            station = self.context.station
            station.box_set_test_running(state == True)
        except Exception as exc:
            logger.exception(exc)

    def showIdentify(self) -> None:
        try:
            station = self.context.station
            station.open_resources()
            station.check_identities()
            station.close_resources()
        except Exception as exc:
            logger.exception(exc)

    def toggleBoxLight(self, state: bool) -> None:
        try:
            station = self.context.station
            station.box_set_light_enabled(state)
        except Exception as exc:
            logger.exception(exc)

    # Help

    def showContents(self) -> None:
        showContents()

    def showGithub(self) -> None:
        showGithub()

    def showAboutQt(self) -> None:
        QtWidgets.QMessageBox.aboutQt(self, "About Qt")

    def showAbout(self) -> None:
        QtWidgets.QMessageBox.about(self, "About", aboutMessage())

    def showLockedNotification(self) -> None:
        QtWidgets.QMessageBox.warning(self, "Active Measurement", "A measurement is active. Stop the measurement before quitting the application.")

    def confirmShutdown(self) -> bool:
        result = QtWidgets.QMessageBox.question(self, "Quit Application?", "Do you want to quit the Application?")
        return result == QtWidgets.QMessageBox.Yes

    def confirmReset(self):
        self.context.reset()
        if self.context.data:
            result = QtWidgets.QMessageBox.question(self, "Re-measure?", "Do you want to merge new data with existing data?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
            if result != QtWidgets.QMessageBox.Yes:
                return False
        return True

    # Toolbar

    def setToolBarState(self, text) -> None:
        self.toolBarStateLabel.setText(text)

    def clearToolBarState(self) -> None:
        self.toolBarStateLabel.clear()

    # Status bar

    def setMessage(self, message: str) -> None:
        self.messageLabel.setText(message)

    def setProgress(self, minimum: int, maximum: int, value: int) -> None:
        self.progressBar.setRange(minimum, maximum)
        self.progressBar.setValue(value)
        self.progressBar.show()

    def clearProgress(self) -> None:
        self.progressBar.setRange(0, 1)
        self.progressBar.setValue(0)
        self.progressBar.hide()

    def checkEnvironment(self, data: dict) -> bool:
        minTemperature, maxTemperature = self.dashboardWidget.temperatureRange()
        minHumidity, maxHumidity = self.dashboardWidget.humidityRange()

        temperature = data.get("pt100_1")
        if temperature is None:
            QtWidgets.QMessageBox.warning(self, "Temperature", f"Chuck temperature not available.")
            return False

        if temperature < minTemperature or temperature > maxTemperature:
            QtWidgets.QMessageBox.warning(self, "Temperature", f"Chuck temperature out of range ({formatTemperature(temperature)}).")
            return False

        temperature2 = data.get("box_temperature")
        if temperature2 is None:
            QtWidgets.QMessageBox.warning(self, "Temperature", f"Box temperature not available.")
            return False

        if temperature < minTemperature or temperature2 > maxTemperature:
            QtWidgets.QMessageBox.warning(self, "Temperature", f"Box temperature out of range ({formatTemperature(temperature2)}).")
            return False

        humidity = data.get("box_humidity")
        if humidity is None:
            QtWidgets.QMessageBox.warning(self, "Humidity", f"Box humidity not available.")
            return False

        # Disabled, wait for humidity after door open/close in sequence
        # if humidity < minHumidity or humidity > maxHumidity:
        #     QtWidgets.QMessageBox.warning(self, "Humidity", f"Box humidity out of range ({formatHumidity(humidity)}).")
        #     return False

        return True

    # Actions

    def handleAutoStart(self) -> None:
        """Auto starts measurements if requested by context."""
        if self.context.auto_start_measurement:
            self.context.auto_start_measurement = False

            progress = QtWidgets.QProgressDialog("Auto Start Measurements...", "Cancel", 0, 5, self)
            progress.setValue(0)

            def updateProgress():
                counter = progress.value() + 1
                progress.setValue(counter)

            timer = QtCore.QTimer()
            timer.timeout.connect(updateProgress)
            timer.start(1000)  # 1000 ms = 1 second

            progress.exec()

            if not progress.wasCanceled():
                self.startAction.trigger()

    @QtCore.pyqtSlot()
    def requestStart(self):
        if not self.dashboardWidget.sensorName().strip():
            QtWidgets.QMessageBox.warning(self, "Missing Sensor Name", "No sensor name is set.")
            return
        if not self.dashboardWidget.outputPath().strip():
            QtWidgets.QMessageBox.warning(self, "Missing Output Path", "No output path is set.")
            return
        if not self.dashboardWidget.operatorName().strip():
            QtWidgets.QMessageBox.warning(self, "Missing Operator Name", "No operator name is set.")
            return
        # Check environment limits
        data = self.context.station.box_environment()
        if not self.checkEnvironment(data):
            return
        if not self.confirmReset():
            return
        self.startRequested.emit()

    @QtCore.pyqtSlot()
    def requestStop(self):
        self.stopRequested.emit()

    # States

    @QtCore.pyqtSlot()
    def enterIdleState(self):
        self.newMeasurementAction.setEnabled(True)
        self.profilesAction.setEnabled(True)
        self.resourcesAction.setEnabled(True)
        self.preferencesAction.setEnabled(True)
        self.startAction.setEnabled(True)
        self.suspendAction.setEnabled(False)
        self.suspendAction.setChecked(False)
        self.stopAction.setEnabled(False)
        self.alignmentAction.setEnabled(True)
        self.recoverAction.setEnabled(True)
        self.boxFlashingLightAction.setEnabled(True)
        self.boxFlashingLightAction.setChecked(False)
        self.boxLightAction.setEnabled(True)
        self.dashboardWidget.setLocked(False)
        self.dashboardWidget.setInputsLocked(False)
        self.context.reset()
        self.clearToolBarState()
        self.clearProgress()
        self.setLocked(False)

        if self.dashboardWidget.wasEnvironOutOfBounds():
            QtWidgets.QMessageBox.warning(self, "Environment", "Temperature/Humidity limits exceeded durring past measurement.")

    @QtCore.pyqtSlot()
    def enterRunningState(self):
        self.setLocked(True)
        self.newMeasurementAction.setEnabled(False)
        self.profilesAction.setEnabled(False)
        self.resourcesAction.setEnabled(False)
        self.preferencesAction.setEnabled(False)
        self.startAction.setEnabled(False)
        self.suspendAction.setEnabled(True)
        self.suspendAction.setChecked(False)
        self.stopAction.setEnabled(True)
        self.alignmentAction.setEnabled(False)
        self.recoverAction.setEnabled(False)
        self.boxFlashingLightAction.setEnabled(False)
        self.boxLightAction.setEnabled(False)
        self.dashboardWidget.setLocked(True)
        self.dashboardWidget.setInputsLocked(True)
        self.dashboardWidget.updateContext()
        self.sequenceController.setSequence(self.dashboardWidget.sequence())
        self.sequenceController.start()
        self.setToolBarState("Running...")

    @QtCore.pyqtSlot()
    def enterAbortingState(self):
        self.startAction.setEnabled(False)
        self.suspendAction.setEnabled(False)
        self.suspendAction.setChecked(False)
        self.stopAction.setEnabled(False)
        self.context.request_abort()
        self.setToolBarState("Aborting...")

    @QtCore.pyqtSlot(Exception)
    def showException(self, exc):
        details = "".join(traceback.format_tb(exc.__traceback__))
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle("Exception occured")
        dialog.setIcon(dialog.Critical)
        dialog.setText(format(exc))
        dialog.setDetailedText(details)
        dialog.setStandardButtons(dialog.Ok)
        dialog.setDefaultButton(dialog.Ok)
        # Fix message box width
        spacer = QtWidgets.QSpacerItem(448, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        dialog.layout().addItem(spacer, dialog.layout().rowCount(), 0, 1, dialog.layout().columnCount())
        dialog.exec()

    # Callbacks

    def sequenceStarted(self) -> None:
        self.pluginManager.dispatch("sequenceStarted", (self,))

    def sequenceFinished(self) -> None:
        self.pluginManager.dispatch("sequenceFinished", (self,))
