import logging
from typing import Any, Iterable, List, Dict, Optional

from PyQt5 import QtCore, QtWidgets

from ..settings import Settings

__all__ = ["PreferencesDialog"]


class PreferencesDialog(QtWidgets.QDialog):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Preferences")

        self.tableWidget = TableWidget(self)
        self.cameraWidget = CameraWidget(self)

        # Tabs

        self.tabWidget = QtWidgets.QTabWidget(self)
        self.tabWidget.addTab(self.tableWidget, "Table")
        self.tabWidget.addTab(self.cameraWidget, "Camera")

        # Dialog button box

        self.dialogButtonBox = QtWidgets.QDialogButtonBox(self)
        self.dialogButtonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.dialogButtonBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.dialogButtonBox.accepted.connect(self.accept)
        self.dialogButtonBox.rejected.connect(self.reject)

        # Layout

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tabWidget)
        layout.addWidget(self.dialogButtonBox)

    def readSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("PreferencesDialog")
        self.restoreGeometry(settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray))
        settings.endGroup()

    def writeSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("PreferencesDialog")
        settings.setValue("geometry", self.saveGeometry())
        settings.endGroup()

    def loadValues(self) -> None:
        self.tableWidget.loadValues()
        self.cameraWidget.loadValues()

    def saveValues(self) -> None:
        self.tableWidget.saveValues()
        self.cameraWidget.saveValues()


class TableProfile:

    def __init__(self, title: str) -> None:
        self.label = QtWidgets.QLabel(title)
        self.accelSpinBox = QtWidgets.QSpinBox()
        self.accelSpinBox.setRange(0, 100000)
        self.accelSpinBox.setSuffix("")  # TODO
        self.velSpinBox = QtWidgets.QSpinBox()
        self.velSpinBox.setRange(0, 100000)
        self.velSpinBox.setSuffix("")  # TODO

    def accel(self) -> int:
        return self.accelSpinBox.value()

    def setAccel(self, accel: int) -> None:
        self.accelSpinBox.setValue(int(accel))

    def vel(self) -> int:
        return self.velSpinBox.value()

    def setVel(self, vel: int) -> None:
        self.velSpinBox.setValue(int(vel))


class TableWidget(QtWidgets.QWidget):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.profiles = {
            "cruise": TableProfile("Cruising"),
            "strip_scan": TableProfile("Strip scan"),
            "optical_scan": TableProfile("Optical Scan"),
        }

        self.profilesGroupBox = QtWidgets.QGroupBox(self)
        self.profilesGroupBox.setTitle("Profiles")

        profilesLayout = QtWidgets.QGridLayout(self.profilesGroupBox)
        profilesLayout.addWidget(QtWidgets.QLabel("Acceleration"), 0, 1)
        profilesLayout.addWidget(QtWidgets.QLabel("Velocity"), 0, 2)
        row = 1
        for profile in self.profiles.values():
            profilesLayout.addWidget(profile.label, row, 0)
            profilesLayout.addWidget(profile.accelSpinBox, row, 1)
            profilesLayout.addWidget(profile.velSpinBox, row, 2)
            row += 1
        profilesLayout.setColumnStretch(3, 1)

        self.contactGroupBox = QtWidgets.QGroupBox(self)
        self.contactGroupBox.setTitle("Contact")

        self.gradualZApproachCheckBox = QtWidgets.QCheckBox(self)
        self.gradualZApproachCheckBox.setText("Gradual Z Approach")

        contactLayout = QtWidgets.QGridLayout(self.contactGroupBox)
        contactLayout.addWidget(self.gradualZApproachCheckBox, 0, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.profilesGroupBox)
        layout.addWidget(self.contactGroupBox)
        layout.addStretch()

    def loadValues(self) -> None:
        settings = Settings()
        for key, profile in self.profiles.items():
            try:
                data = settings.tableProfile(key)
                profile.setAccel(data["accel"])
                profile.setVel(data["vel"])
            except Exception as exc:
                logging.exception(exc)
        self.gradualZApproachCheckBox.setChecked(settings.gradualZApproach())

    def saveValues(self) -> None:
        settings = Settings()
        for key, profile in self.profiles.items():
            try:
                data = {
                    "accel": profile.accel(),
                    "vel": profile.vel(),
                }
                settings.setTableProfile(key, data)
            except Exception as exc:
                logging.exception(exc)
        settings.setGradualZApproach(self.gradualZApproachCheckBox.isChecked())


class CameraWidget(QtWidgets.QWidget):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.cameraComboBox = QtWidgets.QComboBox(self)

        self.deviceIdSpinBox = QtWidgets.QSpinBox(self)
        self.deviceIdSpinBox.setRange(0, 100)

        layout = QtWidgets.QFormLayout(self)
        layout.addRow("Model", self.cameraComboBox)
        layout.addRow("Device ID", self.deviceIdSpinBox)

    def addCamera(self, model: str) -> None:
        self.cameraComboBox.addItem(model, model)

    def loadValues(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("camera")
        model = settings.value("model", "", str)
        deviceId = settings.value("deviceId", 0, int)
        settings.endGroup()
        index = self.cameraComboBox.findData(model)
        if index >= 0:
            self.cameraComboBox.setCurrentIndex(index)
        self.deviceIdSpinBox.setValue(deviceId)

    def saveValues(self) -> None:
        model = self.cameraComboBox.currentData()
        deviceId = self.deviceIdSpinBox.value()
        settings = QtCore.QSettings()
        settings.beginGroup("camera")
        settings.setValue("model", model)
        settings.setValue("deviceId", deviceId)
        settings.endGroup()
