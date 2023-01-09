import logging
import traceback
import os
import webbrowser
from pathlib import Path
from typing import List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from ..settings import Settings, load_padfiles, load_sequences
from .dashboard import DashboardWidget, formatTemperature, formatHumidity
from .profiles import ProfilesDialog, readProfiles
from .resources import ResourcesDialog
from .databrowser import DataBrowserWindow
from .loggerwidget import QueuedLoggerWidget
from .alignment import AlignmentDialog
from .sequence import SequenceController
from .recover import RecoverDialog
# from .measurement import CreateMeasurementDialog

__all__ = ["MainWindow"]

APP_TITLE = "SQC"
APP_COPY = "Copyright &copy; 2022-2023 HEPHY"
APP_LICENSE = "This software is licensed under the GNU General Public License v3.0"
APP_DECRIPTION = """Sensor Quality Control (SQC) characterises a sample of
sensors from each batch delivered by the producer and ensures that they
fully satisfy the specifications so they can be used to build modules for
the CMS Tracker."""

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):

    startRequested = QtCore.pyqtSignal()
    stopRequested = QtCore.pyqtSignal()

    def __init__(self, context, parent=None):
        super().__init__(parent)

        self.context = context

        self.plugins = []

        # Dock widgets

        self.loggerWidget = QueuedLoggerWidget(self)

        self.loggerDockWidget = QtWidgets.QDockWidget(self)
        self.loggerDockWidget.setObjectName("logger")
        self.loggerDockWidget.setWindowTitle("Logger")
        self.loggerDockWidget.setFloating(False)
        self.loggerDockWidget.setFeatures(QtWidgets.QDockWidget.DockWidgetClosable)
        self.loggerDockWidget.setWidget(self.loggerWidget)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.loggerDockWidget)

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

        self.dataBrowserAction = QtWidgets.QAction("Data &Browser")
        self.dataBrowserAction.setIcon(QtGui.QIcon.fromTheme("icons:view-browser.svg"))
        self.dataBrowserAction.setStatusTip("Browse previous measurement data")
        self.dataBrowserAction.setCheckable(True)
        self.dataBrowserAction.setChecked(False)
        self.dataBrowserAction.triggered.connect(self.setDataBrowserVisible)

        self.loggerAction = self.loggerDockWidget.toggleViewAction()
        self.loggerAction.setIcon(QtGui.QIcon("icons:view-logger.svg"))
        self.loggerAction.setChecked(False)

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

        self.boxLightAction = QtWidgets.QAction("Box Light")
        self.boxLightAction.setIcon(QtGui.QIcon.fromTheme("icons:light.svg"))
        self.boxLightAction.setStatusTip("Toggle box light")
        self.boxLightAction.setCheckable(True)
        self.boxLightAction.setVisible(False)  # TODO
        self.boxLightAction.toggled.connect(self.toggleBoxLight)

        self.identifyAction = QtWidgets.QAction("Identify Instruments")
        self.identifyAction.setStatusTip("Identify Instruments")
        self.identifyAction.setVisible(False)
        self.identifyAction.triggered.connect(self.showIdentify)


        self.contentsAction = QtWidgets.QAction("&Contents")
        self.contentsAction.setShortcut(QtGui.QKeySequence("F1"))
        self.contentsAction.triggered.connect(self.showContents)

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

        self.viewMenu = self.menuBar().addMenu("&View")
        self.viewMenu.addAction(self.dataBrowserAction)
        self.viewMenu.addAction(self.loggerAction)

        self.sequenceMenu = self.menuBar().addMenu("&Sequence")
        self.sequenceMenu.addAction(self.startAction)
        self.sequenceMenu.addAction(self.suspendAction)
        self.sequenceMenu.addAction(self.stopAction)
        self.sequenceMenu.addSeparator()
        self.sequenceMenu.addAction(self.alignmentAction)

        self.toolsMenu = self.menuBar().addMenu("&Tools")
        self.toolsMenu.addAction(self.recoverAction)
        self.toolsMenu.addAction(self.boxLightAction)
        self.toolsMenu.addAction(self.identifyAction)

        self.helpMenu = self.menuBar().addMenu("&Help")
        self.helpMenu.addAction(self.contentsAction)
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

    def readSettings(self):
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

    def syncSettings(self):
        settings = QtCore.QSettings()
        settings.beginGroup("mainwindow")

        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())

        settings.endGroup()

        self.dashboardWidget.syncSettings()
        self.dataBrowserWindow.syncSettings()

    # Lock

    def isLocked(self) -> bool:
        return self.property("locked") or False

    def setLocked(self, state: bool) -> None:
        self.setProperty("locked", state)

    # Plugins

    def installPlugin(self, plugin):
        try:
            self.plugins.append(plugin)
            plugin.install(self)
        except Exception as exc:
            logger.exception(exc)

    def uninstallPlugin(self, plugin):
        if plugin in self.plugins:
            try:
                plugin.uninstall(self)
                self.plugins.remove(plugin)
            except Exception as exc:
                logger.exception(exc)

    # Shutdown

    def shutdown(self):
        self.dashboardWidget.shutdown()
        self.sequenceController.shutdown()
        self.stateMachine.stop()

    # Logger

    def addLogger(self, logger: logging.Logger) -> None:
        self.loggerWidget.addLogger(logger)

    def removeLogger(self, logger: logging.Logger) -> None:
        self.loggerWidget.removeLogger(logger)

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
        # dialog = CreateMeasurementDialog(self)
        # dialog.setOutputPath(self.dashboardWidget.outputPath())
        # dialog.setOperatorName(self.dashboardWidget.operatorName())
        # dialog.exec()
        # if dialog.result() == dialog.Accepted:
        #     self.dashboardWidget.setOutputPath(dialog.outputPath())
        #     self.dashboardWidget.setOperatorName(dialog.operatorName())
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
            dialog.syncSettings()
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
            dialog.syncSettings()
            if dialog.result() == dialog.Accepted:
                Settings().setResources(dialog.resources())
        except Exception as exc:
            logger.exception(exc)

    # View

    def setDataBrowserVisible(self, checked: bool) -> None:
        self.dataBrowserWindow.setVisible(checked)

    def setLoggerVisible(self, checked: bool) -> None:
        self.loggerDockWidget.setVisible(checked)

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
        dialog = AlignmentDialog(self.context)
        try:
            dialog.setPadfile(self.context.padfile)
            dialog.readSettings()
            dialog.setLightsOn()
            dialog.setJoystickEnabled(False)
            dialog.exec()
            dialog.syncSettings()
        except Exception as exc:
            logger.exception(exc)
        finally:
            dialog.shutdown()

    def showRecoverStation(self) -> None:
        dialog = RecoverDialog(self.context)
        dialog.run()

    def showIdentify(self) -> None:
        try:
            station = self.context.station
            station.open_resources()
            station.check_identities()
            station.close_resources()
        except Exception as exc:
            logger.exception(exc)

    def toggleBoxLight(self, state) -> None:
        try:
            station = self.context.station
            if state:
                station.box_switch_lights_on()
            else:
                station.box_switch_lights_off()
        except Exception as exc:
            logger.exception(exc)

    # Help

    def showContents(self) -> None:
        contentsUrl = QtWidgets.QApplication.instance().property("ContentsUrl")  # type: ignore
        if contentsUrl:
            webbrowser.open(contentsUrl)

    def showAboutQt(self) -> None:
        QtWidgets.QMessageBox.aboutQt(self, "About Qt")

    def showAbout(self) -> None:
        version = QtWidgets.QApplication.applicationVersion()  # type: ignore
        QtWidgets.QMessageBox.about(self, "About", f"<h1>{APP_TITLE}</h1><p>Version {version}</p><p>{APP_DECRIPTION}</p><p>{APP_COPY}</p><p>{APP_LICENSE}</p>")

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
        self.startAction.setEnabled(True)
        self.suspendAction.setEnabled(False)
        self.suspendAction.setChecked(False)
        self.stopAction.setEnabled(False)
        self.alignmentAction.setEnabled(True)
        self.recoverAction.setEnabled(True)
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
        self.startAction.setEnabled(False)
        self.suspendAction.setEnabled(True)
        self.suspendAction.setChecked(False)
        self.stopAction.setEnabled(True)
        self.alignmentAction.setEnabled(False)
        self.recoverAction.setEnabled(False)
        self.boxLightAction.setEnabled(False)
        self.boxLightAction.setChecked(False)
        self.loggerWidget.showRecentRecords()
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
