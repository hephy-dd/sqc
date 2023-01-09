"""Sensor profile management."""

import os
from typing import Any, Iterable, List, Dict, Optional

from PyQt5 import QtCore, QtWidgets

__all__ = ["readProfiles", "ProfilesDialog"]


def padfileCategory(filename: str) -> str:
    return os.path.basename(os.path.dirname(filename))


def padfileType(filename: str) -> str:
    return os.path.splitext(os.path.basename(filename))[0]


def padfileName(filename: str) -> str:
    category = padfileCategory(filename)
    type = padfileType(filename)
    return f"{category}/{type}"


def sequenceName(filename: str) -> str:
    return os.path.splitext(os.path.basename(filename))[0]


def readProfiles() -> List[Dict[str, Any]]:
    profiles = []
    settings = QtCore.QSettings()
    settings.beginGroup("ProfilesDialog")
    count = settings.beginReadArray("profiles")
    for index in range(count):
        settings.setArrayIndex(index)
        profiles.append({
            "name": settings.value("name", "", str),
            "padfile": settings.value("padfile", "", str),
            "sequence": settings.value("sequence", "", str),
        })
    settings.endArray()
    settings.endGroup()
    return profiles


class ProfileTreeItem(QtWidgets.QTreeWidgetItem):

    NameColumn: int = 0
    PadfileColumn: int = 1
    SequenceColumn: int = 2

    PadfileRole: int = 0x2000
    SequenceRole: int = 0x2001

    def name(self) -> str:
        return self.text(type(self).NameColumn)

    def setName(self, name: str) -> None:
        self.setText(type(self).NameColumn, name)

    def padfile(self) -> str:
        return self.data(type(self).PadfileColumn, type(self).PadfileRole) or ""

    def setPadfile(self, filename: str) -> None:
        self.setText(type(self).PadfileColumn, padfileName(filename))
        self.setData(type(self).PadfileColumn, type(self).PadfileRole, filename)
        self.setToolTip(type(self).PadfileColumn, filename)

    def sequence(self) -> str:
        return self.data(type(self).SequenceColumn, type(self).SequenceRole) or ""

    def setSequence(self, filename: str) -> None:
        self.setText(type(self).SequenceColumn, sequenceName(filename))
        self.setData(type(self).SequenceColumn, type(self).SequenceRole, filename)
        self.setToolTip(type(self).SequenceColumn, filename)


class ProfileDialog(QtWidgets.QDialog):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Sensor Profile")

        # Profile name

        self.nameLabel = QtWidgets.QLabel(self)
        self.nameLabel.setText("Name")

        self.nameLineEdit = QtWidgets.QLineEdit(self)
        self.nameLineEdit.setClearButtonEnabled(True)
        self.nameLineEdit.textChanged.connect(self.onUpdateDialogButtonBox)

        # Padfile

        self.padfileLabel = QtWidgets.QLabel(self)
        self.padfileLabel.setText("Padfile")

        self.padfileLineEdit = QtWidgets.QLineEdit(self)
        self.padfileLineEdit.textChanged.connect(self.onUpdateDialogButtonBox)

        self.selectPadfileButton = QtWidgets.QToolButton(self)
        self.selectPadfileButton.setText("...")
        self.selectPadfileButton.clicked.connect(self.selectPadfile)

        # Sequence

        self.sequenceLabel = QtWidgets.QLabel(self)
        self.sequenceLabel.setText("Sequence")

        self.sequenceLineEdit = QtWidgets.QLineEdit(self)
        self.sequenceLineEdit.textChanged.connect(self.onUpdateDialogButtonBox)

        self.selectSequenceButton = QtWidgets.QToolButton(self)
        self.selectSequenceButton.setText("...")
        self.selectSequenceButton.clicked.connect(self.selectSequence)

        # Dialog button box

        self.dialogButtonBox = QtWidgets.QDialogButtonBox(self)
        self.dialogAcceptButton = self.dialogButtonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.dialogAcceptButton.setEnabled(False)
        self.dialogButtonBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.dialogButtonBox.accepted.connect(self.accept)
        self.dialogButtonBox.rejected.connect(self.reject)

        # Layout

        padfileLayout = QtWidgets.QHBoxLayout()
        padfileLayout.addWidget(self.sequenceLineEdit)
        padfileLayout.addWidget(self.selectSequenceButton)

        sequenceLayout = QtWidgets.QHBoxLayout()
        sequenceLayout.addWidget(self.padfileLineEdit)
        sequenceLayout.addWidget(self.selectPadfileButton)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.nameLabel)
        layout.addWidget(self.nameLineEdit)
        layout.addWidget(self.padfileLabel)
        layout.addLayout(padfileLayout)
        layout.addWidget(self.sequenceLabel)
        layout.addLayout(sequenceLayout)
        layout.addStretch()
        layout.addWidget(self.dialogButtonBox)

    def profileName(self) -> str:
        return self.nameLineEdit.text().strip()

    def setProfileName(self, name: str) -> None:
        self.nameLineEdit.setText(name)

    def padfile(self) -> str:
        return self.padfileLineEdit.text().strip()

    def setPadfile(self, filename: str) -> None:
        self.padfileLineEdit.setText(filename)

    def sequence(self) -> str:
        return self.sequenceLineEdit.text()

    def setSequence(self, filename: str) -> None:
        self.sequenceLineEdit.setText(filename)

    def selectPadfile(self) -> None:
        filename, success = QtWidgets.QFileDialog.getOpenFileName(self, "Select Padfile", self.padfile(), "Padfile (*.txt)")
        if success:
            self.setPadfile(filename)

    def selectSequence(self) -> None:
        filename, success = QtWidgets.QFileDialog.getOpenFileName(self, "Select Sequence", self.sequence(), "Sequence (*.yaml)")
        if success:
            self.setSequence(filename)

    def readSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("ProfileDialog")
        geometry = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)
        if not self.restoreGeometry(geometry):
            self.resize(320, 128)
        settings.endGroup()

    def syncSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("ProfileDialog")
        settings.setValue("geometry", self.saveGeometry())
        settings.endGroup()

    @QtCore.pyqtSlot()
    def onUpdateDialogButtonBox(self) -> None:
        enabled = True
        if not self.profileName():
            enabled = False
        if not self.padfile():
            enabled = False
        if not self.sequence():
            enabled = False
        self.dialogAcceptButton.setEnabled(enabled)


class ProfilesDialog(QtWidgets.QDialog):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Sensor Profiles")

        # Profiles

        self.profilesTreeWidget = QtWidgets.QTreeWidget(self)
        self.profilesTreeWidget.setRootIsDecorated(False)
        headerItem = QtWidgets.QTreeWidgetItem()
        headerItem.setText(ProfileTreeItem.NameColumn, "Name")
        headerItem.setText(ProfileTreeItem.PadfileColumn, "Padfile")
        headerItem.setText(ProfileTreeItem.SequenceColumn, "Sequence")
        self.profilesTreeWidget.setHeaderItem(headerItem)
        self.profilesTreeWidget.itemSelectionChanged.connect(self.onUpdateButtons)

        self.addButton = QtWidgets.QPushButton(self)
        self.addButton.setText("&Add...")
        self.addButton.clicked.connect(self.onAddProfile)

        self.editButton = QtWidgets.QPushButton(self)
        self.editButton.setText("&Edit...")
        self.editButton.setEnabled(False)
        self.editButton.clicked.connect(self.onEditCurrentProfile)

        self.removeButton = QtWidgets.QPushButton(self)
        self.removeButton.setText("&Remove")
        self.removeButton.setEnabled(False)
        self.removeButton.clicked.connect(self.onRemoveCurrentProfile)

        # Dialog button box

        self.dialogButtonBox = QtWidgets.QDialogButtonBox(self)
        self.dialogButtonBox.addButton(QtWidgets.QDialogButtonBox.Close)
        self.dialogButtonBox.accepted.connect(self.accept)
        self.dialogButtonBox.rejected.connect(self.reject)

        # Layout

        uiGridLayout = QtWidgets.QGridLayout()
        uiGridLayout.addWidget(self.profilesTreeWidget, 0, 0, 4, 1)
        uiGridLayout.addWidget(self.addButton, 0, 1, 1, 1)
        uiGridLayout.addWidget(self.editButton, 1, 1, 1, 1)
        uiGridLayout.addWidget(self.removeButton, 2, 1, 1, 1)
        uiGridLayout.setRowStretch(3, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(uiGridLayout)
        layout.addWidget(self.dialogButtonBox)

    def readSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("ProfilesDialog")
        geometry = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)
        if not self.restoreGeometry(geometry):
            self.resize(320, 240)
        count = settings.beginReadArray("profiles")
        for index in range(count):
            settings.setArrayIndex(index)
            item = ProfileTreeItem()
            item.setName(settings.value("name", "", str))
            item.setPadfile(settings.value("padfile", "", str))
            item.setSequence(settings.value("sequence", "", str))
            self.profilesTreeWidget.addTopLevelItem(item)
        self.profilesTreeWidget.resizeColumnToContents(1)
        self.profilesTreeWidget.resizeColumnToContents(2)
        settings.endArray()
        settings.endGroup()

    def syncSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("ProfilesDialog")
        settings.setValue("geometry", self.saveGeometry())
        settings.beginWriteArray("profiles")
        for index in range(self.profilesTreeWidget.topLevelItemCount()):
            item = self.profilesTreeWidget.topLevelItem(index)
            if isinstance(item, ProfileTreeItem):
                settings.setArrayIndex(index)
                settings.setValue("name", item.name())
                settings.setValue("padfile", item.padfile())
                settings.setValue("sequence", item.sequence())
        settings.endArray()
        settings.endGroup()

    @QtCore.pyqtSlot()
    def onUpdateButtons(self) -> None:
        item = self.profilesTreeWidget.currentItem()
        if item is None:
            self.editButton.setEnabled(False)
            self.removeButton.setEnabled(False)
        else:
            self.editButton.setEnabled(True)
            self.removeButton.setEnabled(True)

    @QtCore.pyqtSlot()
    def onAddProfile(self) -> None:
        dialog = ProfileDialog(self)
        dialog.setWindowTitle("Add Profile")
        dialog.readSettings()
        dialog.exec()
        dialog.syncSettings()
        if dialog.result() == ProfileDialog.Accepted:
            item = ProfileTreeItem()
            item.setName(dialog.profileName())
            item.setPadfile(dialog.padfile())
            item.setSequence(dialog.sequence())
            self.profilesTreeWidget.addTopLevelItem(item)
            self.profilesTreeWidget.setCurrentItem(item)
            self.profilesTreeWidget.resizeColumnToContents(1)
            self.profilesTreeWidget.resizeColumnToContents(2)

    @QtCore.pyqtSlot()
    def onEditCurrentProfile(self) -> None:
        item = self.profilesTreeWidget.currentItem()
        if isinstance(item, ProfileTreeItem):
            dialog = ProfileDialog(self)
            dialog.setWindowTitle("Edit Profile")
            dialog.setProfileName(item.name())
            dialog.setPadfile(item.padfile())
            dialog.setSequence(item.sequence())
            dialog.readSettings()
            dialog.exec()
            dialog.syncSettings()
            if dialog.result() == ProfileDialog.Accepted:
                item.setName(dialog.profileName())
                item.setPadfile(dialog.padfile())
                item.setSequence(dialog.sequence())

    @QtCore.pyqtSlot()
    def onRemoveCurrentProfile(self) -> None:
        item = self.profilesTreeWidget.currentItem()
        if isinstance(item, ProfileTreeItem):
            name = item.name()
            title = "Remove Profile"
            text = f"Permanently remove profile \"{name}\"?"
            result = QtWidgets.QMessageBox.question(self, title, text)
            if result == QtWidgets.QMessageBox.Yes:
                index = self.profilesTreeWidget.indexOfTopLevelItem(item)
                self.profilesTreeWidget.takeTopLevelItem(index)
