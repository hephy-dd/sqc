import logging
from typing import Dict, Optional

from PyQt5 import QtCore, QtWidgets


def safe_float(text: str) -> float:
    try:
        return float(text)
    except Exception:
        return 0.0


class ComboBoxDelegate(QtWidgets.QStyledItemDelegate):
    typeChanged = QtCore.pyqtSignal(object, str)

    def __init__(self, constraints, parent=None):
        super().__init__(parent)
        self.constraints = constraints

    def createEditor(self, parent, option, index) -> QtWidgets.QWidget:
        combo = QtWidgets.QComboBox(parent)
        combo.addItems(self.constraints)
        return combo

    def setEditorData(self, editor, index) -> None:
        value = index.data(QtCore.Qt.DisplayRole)
        editor.setCurrentText(value)

    def setModelData(self, editor, model, index) -> None:
        model.setData(index, editor.currentText(), QtCore.Qt.EditRole)
        self.typeChanged.emit(index, editor.currentText())


class SpinBoxDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(self, parent, option, index) -> QtWidgets.QWidget:
        spinbox = QtWidgets.QSpinBox(parent)
        spinbox.setRange(0, 10000000)
        return spinbox

    def setEditorData(self, editor, index) -> None:
        value = int(float(index.data(QtCore.Qt.DisplayRole).split()[0].strip()))
        editor.setValue(value)

    def setModelData(self, editor, model, index) -> None:
        model.setData(index, f"{editor.value()}", QtCore.Qt.EditRole)


class DoubleSpinBoxDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.suffix = ""

    def createEditor(self, parent, option, index) -> QtWidgets.QWidget:
        spinbox = QtWidgets.QDoubleSpinBox(parent)
        spinbox.setDecimals(3)
        spinbox.setRange(-1000000, 1000000)
        return spinbox

    def setEditorData(self, editor, index) -> None:
        self.suffix = " " + index.data(QtCore.Qt.DisplayRole).split()[-1].strip()
        editor.setSuffix(self.suffix)
        value = float(index.data(QtCore.Qt.DisplayRole).split()[0].strip())
        editor.setValue(value)

    def setModelData(self, editor, model, index) -> None:
        model.setData(index, f"{editor.value():.3f} {self.suffix}", QtCore.Qt.EditRole)



class BadStripSelectDialog(QtWidgets.QDialog):

    def __init__(self, context, parent: Optional[QtWidgets.QWidget]) -> None:
        super().__init__(parent)

        self.setObjectName("BadStripSelectDialog")
        self.setWindowTitle("Select Bad Strips")

        self.context = context

        self.boxesTreeWidget = QtWidgets.QTreeWidget()
        self.boxesTreeWidget.setHeaderLabels(["Type", "First Strip", "Last Strip", "Minimum", "Maximum"])

        # TODO
        self.constraints = ["rpoly", "istrip", "idiel", "cac", "cint", "rint", "idark", ]

        typeDelegate = ComboBoxDelegate(self.constraints, self.boxesTreeWidget)
        #typeDelegate.typeChanged.connect(self._updateType)
        self.boxesTreeWidget.setItemDelegateForColumn(0, typeDelegate)

        self.boxesTreeWidget.setItemDelegateForColumn(1, SpinBoxDelegate(self.boxesTreeWidget))
        self.boxesTreeWidget.setItemDelegateForColumn(2, SpinBoxDelegate(self.boxesTreeWidget))
        self.boxesTreeWidget.setItemDelegateForColumn(3, DoubleSpinBoxDelegate(self.boxesTreeWidget))
        self.boxesTreeWidget.setItemDelegateForColumn(4, DoubleSpinBoxDelegate(self.boxesTreeWidget))

        self.boxesTreeWidget.itemChanged.connect(self.updateBoxes)

        self.addBoxButton = QtWidgets.QPushButton()
        self.addBoxButton.setText("&Add")
        self.addBoxButton.clicked.connect(self.newBox)

        self.removeBoxButton = QtWidgets.QPushButton()
        self.removeBoxButton.setText("&Remove")
        self.removeBoxButton.clicked.connect(self.removeCurrentBox)

        self.buttonBox = QtWidgets.QDialogButtonBox(self)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        boxesLayout = QtWidgets.QGridLayout()
        boxesLayout.addWidget(self.boxesTreeWidget, 0, 0, 3, 1)
        boxesLayout.addWidget(self.addBoxButton, 0, 1, 1, 1)
        boxesLayout.addWidget(self.removeBoxButton, 1, 1, 1, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Bounding Boxes"))
        layout.addLayout(boxesLayout)
        layout.addWidget(self.buttonBox)
        layout.setStretch(0, 0)
        layout.setStretch(1, 1)
        layout.setStretch(2, 0)

    def newBox(self) -> None:
        item = QtWidgets.QTreeWidgetItem(self.boxesTreeWidget)
        item.setText(0, "")
        item.setText(1, "0")
        item.setText(2, "0")
        item.setText(3, "0")
        item.setText(4, "0")
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(0, QtCore.Qt.Checked)

    def removeCurrentBox(self) -> None:
        item = self.boxesTreeWidget.currentItem()
        if item:
            index = self.boxesTreeWidget.indexOfTopLevelItem(item)
            self.boxesTreeWidget.takeTopLevelItem(index)

    def updateBoxes(self) -> None:
        boxes = []
        for index in range(self.boxesTreeWidget.topLevelItemCount()):
            item = self.boxesTreeWidget.topLevelItem(index)
            if item and item.checkState(0) == QtCore.Qt.Checked:
                type = item.text(0)
                first_strip = safe_float(item.text(1).split()[0])
                last_strip = safe_float(item.text(2).split()[0])
                minimum_value = safe_float(item.text(3).split()[0])
                maximum_value = safe_float(item.text(4).split()[0])
                topLeft = QtCore.QPointF(first_strip, maximum_value)
                bottomRight = QtCore.QPointF(last_strip, minimum_value)
                boxes.append((type, QtCore.QRectF(topLeft, bottomRight)))
        self.context.update_boxes.emit(boxes)

    def addBoundingBox(self, enabled: bool, type: str, first_strip: int, last_strip: int, minimum_value: float, maximum_value: float) -> None:
        item = QtWidgets.QTreeWidgetItem(self.boxesTreeWidget)
        item.setText(0, str(type))
        item.setText(1, str(first_strip))
        item.setText(2, str(last_strip))
        item.setText(3, str(minimum_value))
        item.setText(4, str(maximum_value))
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(0, QtCore.Qt.Checked if enabled else QtCore.Qt.Unchecked)

    def clearBoundingBoxes(self) -> None:
        while self.boxesTreeWidget.topLevelItemCount():
            self.boxesTreeWidget.takeTopLevelItem(0)

    def boundingBoxes(self) -> list[dict]:
        bboxes = []
        for index in range(self.boxesTreeWidget.topLevelItemCount()):
            item = self.boxesTreeWidget.topLevelItem(index)
            if item:
                bboxes.append({
                    "enabled": item.checkState(0) == QtCore.Qt.Checked,
                    "type": item.text(0),
                    "first_strip": int(safe_float(item.text(1).split()[0])),
                    "last_strip": int(safe_float(item.text(2).split()[0])),
                    "minimum_value": safe_float(item.text(3).split()[0]),
                    "maximum_value": safe_float(item.text(4).split()[0]),
                })
        return bboxes

    def readSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup(self.objectName())
        geometry = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)
        boundingBoxes = settings.value("boundingBoxes", [], list)
        settings.endGroup()
        self.restoreGeometry(geometry)
        self.clearBoundingBoxes()
        for boundingBox in boundingBoxes:
            if isinstance(boundingBox, dict):
                try:
                    self.addBoundingBox(
                        enabled=boundingBox.get("enabled", True),
                        type=boundingBox.get("type", ""),
                        first_strip=int(safe_float(boundingBox.get("first_strip", 0))),
                        last_strip=int(safe_float(boundingBox.get("last_strip", 0))),
                        minimum_value=safe_float(boundingBox.get("minimum_value", 0.0)),
                        maximum_value=safe_float(boundingBox.get("maximum_value", 0.0)),
                    )
                except Exception as exc:
                    logging.exception(exc)

    def writeSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup(self.objectName())
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("boundingBoxes", self.boundingBoxes())
        settings.endGroup()

    def selectedStrips(self) -> str:
        return "1-42"  # TODO

    def updatePreview(self) -> None:
        ...
