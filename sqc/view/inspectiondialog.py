import logging
import os
import threading
import time
from typing import Optional

from comet.utils import ureg

from PyQt5 import QtCore, QtGui, QtWidgets

from comet.utils import make_iso, safe_filename

from ..core.utils import alternate_traversal, open_directory

__all__ = ["InspectionDialog"]

logger = logging.getLogger(__name__)


class InspectionDialog(QtWidgets.QDialog):
    """Optical inspection dialog."""

    progressRangeChanged = QtCore.pyqtSignal(int, int)
    progressValueChanged = QtCore.pyqtSignal(int)
    failed = QtCore.pyqtSignal(Exception)
    finished = QtCore.pyqtSignal()
    closeRequested = QtCore.pyqtSignal()

    def __init__(self, context, scene, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Optical Inspection")

        self.context = context
        self.scene = scene

        self._stopRequested = threading.Event()
        self._thread = None

        # Images

        self.xImagesSpinBox = QtWidgets.QSpinBox(self)
        self.xImagesSpinBox.setRange(1, 1000)
        self.xImagesSpinBox.setValue(15)

        self.yImagesSpinBox = QtWidgets.QSpinBox(self)
        self.yImagesSpinBox.setRange(1, 1000)
        self.yImagesSpinBox.setValue(15)

        self.imagesGroupBox = QtWidgets.QGroupBox(self)
        self.imagesGroupBox.setTitle("Images")

        imagesGroupBoxLayout = QtWidgets.QFormLayout(self.imagesGroupBox)
        imagesGroupBoxLayout.addRow("X", self.xImagesSpinBox)
        imagesGroupBoxLayout.addRow("Y", self.yImagesSpinBox)

        # Sensor geometry

        self.sensorWidthSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.sensorWidthSpinBox.setRange(0, 1000)
        self.sensorWidthSpinBox.setSuffix(" mm")

        self.sensorHeightSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.sensorHeightSpinBox.setRange(0, 1000)
        self.sensorHeightSpinBox.setSuffix(" mm")

        self.geometryGroupBox = QtWidgets.QGroupBox(self)
        self.geometryGroupBox.setTitle("Sensor Geometry")

        geometryGroupBoxLayout = QtWidgets.QFormLayout(self.geometryGroupBox)
        geometryGroupBoxLayout.addRow("X", self.sensorWidthSpinBox)
        geometryGroupBoxLayout.addRow("Y", self.sensorHeightSpinBox)

        # Options

        self.waitingTimeSpinBox = QtWidgets.QDoubleSpinBox(self)
        self.waitingTimeSpinBox.setRange(0, 60)
        self.waitingTimeSpinBox.setDecimals(2)
        self.waitingTimeSpinBox.setSingleStep(0.1)
        self.waitingTimeSpinBox.setValue(1)
        self.waitingTimeSpinBox.setSuffix(" s")

        self.outputLineEdit = QtWidgets.QLineEdit(self)
        self.outputLineEdit.setText("/tmp/images")

        self.autoStartMeasurementCheckBox = QtWidgets.QCheckBox(self)
        self.autoStartMeasurementCheckBox.setText("Start measurements when finished")

        self.startButton = QtWidgets.QPushButton(self)
        self.startButton.setText("&Start")

        self.stopButton = QtWidgets.QPushButton(self)
        self.stopButton.setText("Sto&p")

        self.openButton = QtWidgets.QPushButton(self)
        self.openButton.setText("Open")
        self.openButton.clicked.connect(self.openDirectory)

        self.progressBar = QtWidgets.QProgressBar(self)

        # Layout

        hLayout = QtWidgets.QHBoxLayout()
        hLayout.addWidget(self.imagesGroupBox)
        hLayout.addWidget(self.geometryGroupBox)

        layout = QtWidgets.QGridLayout(self)
        layout.addLayout(hLayout, 0, 0)
        layout.addWidget(QtWidgets.QLabel("Waiting Time"))
        layout.addWidget(self.waitingTimeSpinBox)
        layout.addWidget(QtWidgets.QLabel("Ouptut Path"))
        layout.addWidget(self.outputLineEdit)
        layout.addWidget(self.autoStartMeasurementCheckBox)
        layout.addWidget(self.progressBar)
        layout.addWidget(self.startButton)
        layout.addWidget(self.stopButton)
        layout.addWidget(self.openButton)

        self.progressRangeChanged.connect(self.progressBar.setRange)
        self.progressValueChanged.connect(self.progressBar.setValue)
        self.failed.connect(self.showException)
        self.closeRequested.connect(self.close)

        self.idleState = QtCore.QState()
        self.idleState.entered.connect(self.enterIdle)

        self.runningState = QtCore.QState()
        self.runningState.entered.connect(self.enterRunning)

        self.abortingState = QtCore.QState()
        self.abortingState.entered.connect(self.enterAborting)

        self.idleState.addTransition(self.startButton.clicked, self.runningState)
        self.runningState.addTransition(self.stopButton.clicked, self.abortingState)
        self.runningState.addTransition(self.finished, self.idleState)
        self.abortingState.addTransition(self.finished, self.idleState)

        self.stateMachine = QtCore.QStateMachine(self)
        self.stateMachine.addState(self.idleState)
        self.stateMachine.addState(self.runningState)
        self.stateMachine.addState(self.abortingState)
        self.stateMachine.setInitialState(self.idleState)
        self.stateMachine.start()

    def readSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("inspection")
        geometry = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)
        options = settings.value("options", {}, dict)
        settings.endGroup()
        self.restoreGeometry(geometry)
        sensor_type = self.context.parameters.get("sensor_type")
        sensor_options = options.get(sensor_type, {})
        self.setXImages(int(sensor_options.get("x_images", 15)))
        self.setYImages(int(sensor_options.get("y_images", 15)))
        self.setSensorWidth(float(sensor_options.get("sensor_width", 100.0)))
        self.setSensorHeight(float(sensor_options.get("sensor_height", 100.0)))
        output_path = self.context.parameters.get("output_path", "")
        self.outputLineEdit.setText(output_path)

    def writeSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("inspection")
        options = settings.value("options", {}, dict)
        sensor_type = self.context.parameters.get("sensor_type")
        sensor_options = options.setdefault(sensor_type, {})
        sensor_options.update({
            "x_images": self.xImages(),
            "y_images": self.yImages(),
            "sensor_width": self.sensorWidth(),
            "sensor_height": self.sensorHeight(),
        })
        settings.setValue("options", options)
        settings.setValue("geometry", self.saveGeometry())
        settings.endGroup()

    def xImages(self) -> int:
        return self.xImagesSpinBox.value()

    def setXImages(self, value: int) -> None:
        self.xImagesSpinBox.setValue(value)

    def yImages(self) -> int:
        return self.yImagesSpinBox.value()

    def setYImages(self, value: int) -> None:
        self.yImagesSpinBox.setValue(value)

    def sensorWidth(self) -> float:
        return self.sensorWidthSpinBox.value()

    def setSensorWidth(self, width: float) -> None:
        self.sensorWidthSpinBox.setValue(width)

    def sensorHeight(self) -> float:
        return self.sensorHeightSpinBox.value()

    def setSensorHeight(self, height: float) -> None:
        self.sensorHeightSpinBox.setValue(height)

    def outputPath(self) -> str:
        return os.path.abspath(self.outputLineEdit.text())

    def waitingTime(self) -> float:
        return self.waitingTimeSpinBox.value()

    def openDirectory(self) -> None:
        try:
            open_directory(self.outputPath())
        except Exception as exc:
            self.showException(exc)

    def currentImage(self) -> QtGui.QImage:
        return self.scene.image()

    def isAbortRequested(self) -> bool:
        return self._stopRequested.is_set()

    def isAutoStartEnabled(self) -> bool:
        return self.autoStartMeasurementCheckBox.isChecked()  #TODO thread safe?

    def showException(self, exc):
        logger.exception(exc)
        QtWidgets.QMessageBox.critical(self, "Exception Occurred", format(exc))

    def enterIdle(self):
        self.xImagesSpinBox.setEnabled(True)
        self.yImagesSpinBox.setEnabled(True)
        self.sensorWidthSpinBox.setEnabled(True)
        self.sensorHeightSpinBox.setEnabled(True)
        self.outputLineEdit.setEnabled(True)
        self.startButton.setEnabled(True)
        self.stopButton.setEnabled(False)
        self.progressBar.setVisible(False)

    def enterRunning(self):
        self.xImagesSpinBox.setEnabled(False)
        self.yImagesSpinBox.setEnabled(False)
        self.sensorWidthSpinBox.setEnabled(False)
        self.sensorHeightSpinBox.setEnabled(False)
        self.outputLineEdit.setEnabled(False)
        self.startButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self.progressBar.setVisible(True)
        self.progressBar.setRange(0, 0)
        x_images = self.xImagesSpinBox.value()
        y_images = self.yImagesSpinBox.value()
        sensor_name = self.context.parameters.get("sensor_name", "unnamed")
        timestamp = make_iso()
        path = os.path.abspath(os.path.join(
            self.outputPath(),
            safe_filename(sensor_name),
            "images",
            safe_filename(timestamp),
        ))
        config = {
            "sensor_name": sensor_name,
            "x_images": self.xImages(),
            "y_images": self.yImages(),
            "sensor_width": self.sensorWidth(),
            "sensor_height": self.sensorHeight(),
            "path": path,
        }
        self._stopRequested = threading.Event()
        self._thread = threading.Thread(target=self.worker, args=[config])
        self._thread.start()

    def enterAborting(self):
        self.stopButton.setEnabled(False)
        self._stopRequested.set()

    def closeEvent(self, event: QtCore.QEvent) -> None:
        self.stopButton.click()
        if self._thread:
            self._thread.join()
        event.accept()

    def worker(self, config: dict):
        try:
            sensor_name = config.get("sensor_name", "")
            x_images = config.get("x_images", 0)
            y_images = config.get("y_images", 0)
            sensor_width = (ureg("mm") * config.get("sensor_width", 0)).to("um").m
            sensor_height = (ureg("mm") * config.get("sensor_height", 0)).to("um").m
            path = config.get("path", ".")
            image_suffix = config.get("image_suffix", ".jpg")
            image_format = config.get("image_format", "JPG")
            image_quality = config.get("image_quality", 90)

            maximum_steps = x_images * y_images
            finished_steps = 0

            # Calculate offset for sectors
            x_step_size = sensor_width / max(x_images - 1, 1)
            y_step_size = sensor_height / max(y_images - 1, 1)

            self.progressRangeChanged.emit(0, maximum_steps + 1)
            self.progressValueChanged.emit(0)

            # Move table down 1 mm
            # self.context.station.table_move_relative((0, 0, -1.0))
            start_position = self.context.station.table_position()  # make sure this is 1 mm < all alignment points

            if not os.path.exists(path):
                os.makedirs(path)

            def table_move_to_sector(x: int, y: int):
                """Move table to sector by x, y index relative to start position."""
                x_pos, y_pos, z_pos = start_position
                x_pos += (x * x_step_size)
                y_pos += (y * y_step_size)
                logger.info("move table to: %r", (x_pos, y_pos, z_pos))
                self.context.station.table_move_absolute((x_pos, y_pos, z_pos))

            def table_return_to_start():
                """Return table to start position."""
                x_pos, y_pos, z_pos = start_position
                logger.info("move table to: %r", (x_pos, y_pos, z_pos))
                self.context.station.table_move_absolute((x_pos, y_pos, z_pos))

            def apply_waiting_time():
                time.sleep(self.waitingTime())

            def increment_progress():
                nonlocal finished_steps
                finished_steps += 1
                self.progressValueChanged.emit(finished_steps)

            def grab_image(x: int, y: int):
                filename = os.path.join(path, f"{sensor_name}_x{x:03d}_y{y:03d}{image_suffix}")
                image = self.currentImage()
                result = image.save(filename, image_format, image_quality)
                if result:
                    logger.info("saved image %r", filename)
                else:
                    logger.error("failed to write image %r", filename)

            # Traverse the sensor in zig-zag
            for x, y in alternate_traversal(x_images, y_images):

                if self.isAbortRequested():
                    break

                table_move_to_sector(x, y)
                apply_waiting_time()

                if self.isAbortRequested():
                    break

                grab_image(x, y)
                increment_progress()

            # Return table to start position (testing)
            if not self.isAbortRequested():
                table_return_to_start()
                increment_progress()

            if not self.isAbortRequested():
                if self.isAutoStartEnabled():
                    self.context.auto_start_measurement = True
                    self.closeRequested.emit()

        except Exception as exc:
            self.failed.emit(exc)
        finally:
            self.finished.emit()
