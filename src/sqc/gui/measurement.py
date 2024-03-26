from typing import Iterable, Optional

from PyQt5 import QtCore, QtWidgets

__all__ = ["CreateMeasurementDialog"]


class CreateMeasurementDialog(QtWidgets.QDialog):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("New Measurement")

        self.nameLabel = QtWidgets.QLabel(self)
        self.nameLabel.setText("Sensor Name")

        self.nameLineEdit = QtWidgets.QLineEdit()

        self.profileLabel = QtWidgets.QLabel(self)
        self.profileLabel.setText("Sensor Profile")

        self.profileComboBox = QtWidgets.QComboBox(self)
        self.profileComboBox.currentIndexChanged.connect(self.updateDialogButtonBox)

        self.outputPathLabel = QtWidgets.QLabel(self)
        self.outputPathLabel.setText("Output Path")

        self.outputPathLineEdit = QtWidgets.QLineEdit()

        self.operatorLabel = QtWidgets.QLabel(self)
        self.operatorLabel.setText("Operator")

        self.operatorLineEdit = QtWidgets.QLineEdit()

        # Dialog button box

        self.dialogButtonBox = QtWidgets.QDialogButtonBox(self)
        self.acceptButton = self.dialogButtonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.acceptButton.setEnabled(False)
        self.dialogButtonBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.dialogButtonBox.accepted.connect(self.accept)
        self.dialogButtonBox.rejected.connect(self.reject)

        # Layout

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.nameLabel)
        layout.addWidget(self.nameLineEdit)
        layout.addWidget(self.profileLabel)
        layout.addWidget(self.profileComboBox)
        layout.addWidget(self.outputPathLabel)
        layout.addWidget(self.outputPathLineEdit)
        layout.addWidget(self.operatorLabel)
        layout.addWidget(self.operatorLineEdit)
        layout.addStretch()
        layout.addWidget(self.dialogButtonBox)

    def profile(self) -> dict:
        return self.profileComboBox.currentData() or {}

    def outputPath(self):
        return self.outputPathLineEdit.text().strip()

    def setOutputPath(self, path: str) -> None:
        self.outputPathLineEdit.setText(path)

    def operatorName(self):
        return self.operatorLineEdit.text().strip()

    def setOperatorName(self, name: str) -> None:
        self.operatorLineEdit.setText(name)

    def setProfiles(self, profiles: Iterable) -> None:
        self.profileComboBox.clear()
        for profile in profiles:
            self.profileComboBox.addItem(profile.get("name"), profile)

    @QtCore.pyqtSlot()
    def updateDialogButtonBox(self) -> None:
        enabled = True
        if not self.profile():
            enabled = False
        if not self.outputPath():
            enabled = False
        if not self.operatorName():
            enabled = False
        self.acceptButton.setEnabled(enabled)
