import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

from PyQt5 import QtCore, QtWidgets
from schema import Schema, And, Use, SchemaError

from comet.utils import ureg


def ensure_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return int(default)


def ensure_float(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return float(default)


def safe_float(text: str) -> float:
    try:
        return float(text)
    except Exception:
        return 0.0


def compress_strips(strips: list) -> str:
    if not len(strips):
        return ""
    values = sorted(strips)
    ranges = []
    start = values[0]
    end = values[0]
    for i in range(1, len(values)):
        if values[i] == end + 1:
            end = values[i]
        else:
            if start == end:
                ranges.append(f"{start}")
            else:
                ranges.append(f"{start}-{end}")
            start = end = values[i]
    ranges.append(f"{start}" if start == end else f"{start}-{end}")
    return ", ".join(ranges)


class BoundingBoxItem(QtWidgets.QTreeWidgetItem):
    def __init__(self) -> None:
        super().__init__()
        self.setFlags(self.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsUserCheckable)
        self.setEnabled(True)
        self.setFirstStrip(0)
        self.setLastStrip(0)
        self.setMinimumValue(0)
        self.setMaximumValue(0)

    def isEnabled(self) -> bool:
        return self.checkState(0) == QtCore.Qt.Checked

    def setEnabled(self, enabled: bool) -> None:
        self.setCheckState(0, QtCore.Qt.Checked if enabled else QtCore.Qt.Unchecked)

    def typename(self) -> str:
        return self.text(0)

    def setTypename(self, typename: str) -> None:
        self.setText(0, typename)

    def firstStrip(self) -> int:
        return int(self.text(1) or "0")

    def setFirstStrip(self, strip: int) -> None:
        return self.setText(1, format(strip))

    def lastStrip(self) -> int:
        return int(self.text(2) or "0")

    def setLastStrip(self, strip: int) -> None:
        return self.setText(2, format(strip))

    def minimumValue(self) -> float:
        return float(self.text(3) or "0")

    def setMinimumValue(self, value: float) -> None:
        return self.setText(3, format(value))

    def maximumValue(self) -> float:
        return float(self.text(4) or "0")

    def setMaximumValue(self, value: float) -> None:
        return self.setText(4, format(value))

    def unit(self) -> str:
        return self.text(5)

    def setUnit(self, unit: str) -> None:
        return self.setText(5, unit)


class ComboBoxDelegate(QtWidgets.QStyledItemDelegate):
    typeChanged = QtCore.pyqtSignal(object)

    def __init__(self, units, parent=None):
        super().__init__(parent)
        self.units = units

    def createEditor(self, parent, option, index) -> QtWidgets.QWidget:
        combo = QtWidgets.QComboBox(parent)
        combo.addItems(list(self.units.keys()))
        return combo

    def setEditorData(self, editor, index) -> None:
        value = index.data(QtCore.Qt.DisplayRole)
        editor.setCurrentText(value)

    def setModelData(self, editor, model, index) -> None:
        model.setData(index, editor.currentText(), QtCore.Qt.EditRole)
        self.typeChanged.emit(index)


class SpinBoxDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(self, parent, option, index) -> QtWidgets.QWidget:
        spinbox = QtWidgets.QSpinBox(parent)
        spinbox.setRange(0, 10000000)
        return spinbox

    def setEditorData(self, editor, index) -> None:
        value = int(float(index.data(QtCore.Qt.DisplayRole)))
        editor.setValue(value)

    def setModelData(self, editor, model, index) -> None:
        model.setData(index, format(editor.value()), QtCore.Qt.EditRole)


class DoubleSpinBoxDelegate(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index) -> QtWidgets.QWidget:
        spinbox = QtWidgets.QDoubleSpinBox(parent)
        spinbox.setDecimals(3)
        spinbox.setRange(-1e12, 1e12)
        return spinbox

    def setEditorData(self, editor, index) -> None:
        value = float(index.data(QtCore.Qt.DisplayRole))
        editor.setValue(value)

    def setModelData(self, editor, model, index) -> None:
        model.setData(index, format(editor.value()), QtCore.Qt.EditRole)


class UnitDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, units: dict, parent=None):
        super().__init__(parent)
        self.units = units

    def createEditor(self, parent, option, index) -> QtWidgets.QWidget:
        return QtWidgets.QComboBox(parent)

    def setEditorData(self, editor, index) -> None:
        type_ = index.sibling(index.row(), 0).data(QtCore.Qt.DisplayRole)
        units = self.units.get(type_, [])
        editor.addItems(units)
        value = index.data(QtCore.Qt.DisplayRole)
        editor.setCurrentText(value)

    def setModelData(self, editor, model, index) -> None:
        model.setData(index, editor.currentText(), QtCore.Qt.EditRole)


class BadStripSelectDialog(QtWidgets.QDialog):
    boxesChanged = QtCore.pyqtSignal(list)  # list[BoundingBox]
    markersChanged = QtCore.pyqtSignal(list)  # list[Marker]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self._data: dict = {}
        self.units: dict = {}
        self.fields: dict = {}

        self.setObjectName("BadStripSelectDialog")
        self.setWindowTitle("Select Bad Strips")

        self.boxesLabel = QtWidgets.QLabel(self)
        self.boxesLabel.setText("Bounding Boxes")

        self.boxesTreeWidget = QtWidgets.QTreeWidget()
        self.boxesTreeWidget.setRootIsDecorated(False)
        self.boxesTreeWidget.setHeaderLabels(["Type", "First Strip", "Last Strip", "Minimum", "Maximum", "Unit"])
        self.boxesTreeWidget.setSortingEnabled(True)
        self.boxesTreeWidget.sortByColumn(0, QtCore.Qt.AscendingOrder)

        typeDelegate = ComboBoxDelegate(self.units, self.boxesTreeWidget)
        typeDelegate.typeChanged.connect(self.updateType)

        self.boxesTreeWidget.setItemDelegateForColumn(0, typeDelegate)
        self.boxesTreeWidget.setItemDelegateForColumn(1, SpinBoxDelegate(self.boxesTreeWidget))
        self.boxesTreeWidget.setItemDelegateForColumn(2, SpinBoxDelegate(self.boxesTreeWidget))
        self.boxesTreeWidget.setItemDelegateForColumn(3, DoubleSpinBoxDelegate(self.boxesTreeWidget))
        self.boxesTreeWidget.setItemDelegateForColumn(4, DoubleSpinBoxDelegate(self.boxesTreeWidget))
        self.boxesTreeWidget.setItemDelegateForColumn(5, UnitDelegate(self.units, self.boxesTreeWidget))

        self.boxesTreeWidget.itemChanged.connect(self.updateBoxes)

        self.addBoxButton = QtWidgets.QPushButton()
        self.addBoxButton.setText("&Add")
        self.addBoxButton.clicked.connect(self.newBox)

        self.removeBoxButton = QtWidgets.QPushButton()
        self.removeBoxButton.setText("&Remove")
        self.removeBoxButton.clicked.connect(self.removeCurrentBox)

        self.importButton = QtWidgets.QPushButton()
        self.importButton.setText("&Import...")
        self.importButton.clicked.connect(self.importFile)

        self.exportButton = QtWidgets.QPushButton()
        self.exportButton.setText("&Export...")
        self.exportButton.clicked.connect(self.exportFile)

        self.previewLabel = QtWidgets.QLabel(self)
        self.previewLabel.setText("Selected Strips")

        self.previewLineEdit = QtWidgets.QLineEdit(self)
        self.previewLineEdit.setReadOnly(True)

        self.buttonBox = QtWidgets.QDialogButtonBox(self)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.boxesLayout = QtWidgets.QGridLayout()
        self.boxesLayout.addWidget(self.boxesTreeWidget, 0, 0, 5, 1)
        self.boxesLayout.addWidget(self.addBoxButton, 0, 1, 1, 1)
        self.boxesLayout.addWidget(self.removeBoxButton, 1, 1, 1, 1)
        self.boxesLayout.addWidget(self.importButton, 3, 1, 1, 1)
        self.boxesLayout.addWidget(self.exportButton, 4, 1, 1, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.boxesLabel)
        layout.addLayout(self.boxesLayout)
        layout.addWidget(self.previewLabel)
        layout.addWidget(self.previewLineEdit)
        layout.addWidget(self.buttonBox)
        layout.setStretch(1, 1)

    def addType(self, type: str, field: str, units: list[str]) -> None:
        self.units[type] = units
        self.fields[type] = field

    def setData(self, data: dict) -> None:
        self._data = data

    def updateType(self, index) -> None:
        item = self.boxesTreeWidget.itemFromIndex(index)
        if item:
            type_ = item.text(0)
            unit = self.units.get(type_, [""])[0]
            item.setText(3, "0")
            item.setText(4, "0")
            item.setText(5, unit)

    def newBox(self) -> None:
        for typename, units in self.units.items():
            if units:
                item = BoundingBoxItem()
                item.setEnabled(True)
                item.setTypename(typename)
                item.setUnit(units[0])
                self.addBoundingBox(item)
                self.boxesTreeWidget.setCurrentItem(item)
            break

    def removeCurrentBox(self) -> None:
        item = self.boxesTreeWidget.currentItem()
        if item is not None:
            index = self.boxesTreeWidget.indexOfTopLevelItem(item)
            self.boxesTreeWidget.takeTopLevelItem(index)

    def importFile(self) -> None:
        # Define the schema for validation
        bounding_box_schema = Schema({
            "enabled": bool,
            "type": str,
            "first_strip": And(Use(int), lambda n: n >= 0),
            "last_strip": And(Use(int), lambda n: n >= 0),
            "minimum_value": Use(float),
            "maximum_value": Use(float),
            "unit": str,
        })

        data_schema = Schema({
            "bounding_boxes": [bounding_box_schema],
        })

        # Open file dialog for selecting a JSON file
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import JSON",
            os.path.expanduser("~"),
            "JSON (*.json)"
        )

        # If a file is selected
        if filename:
            try:
                # Open the selected file and load the JSON data
                with open(filename, "rt") as fp:
                    data = json.load(fp)

                # Validate the data structure using schema
                validated_data = data_schema.validate(data)

                # Extract validated bounding boxes
                bounding_boxes = validated_data["bounding_boxes"]

                self.clearBoundingBoxes()
                for box in bounding_boxes:
                    item = BoundingBoxItem()
                    item.setEnabled(box["enabled"]),
                    item.setTypename(box["type"])
                    item.setFirstStrip(box["first_strip"])
                    item.setLastStrip(box["last_strip"])
                    item.setMinimumValue(box["minimum_value"])
                    item.setMaximumValue(box["maximum_value"])
                    item.setUnit(box["unit"]),
                    self.addBoundingBox(item)
                self.updateBoxes()

            except (json.JSONDecodeError, SchemaError) as e:
                # Handle JSON decoding and schema validation errors
                logging.error(f"Failed to import file: {str(e)}")
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to import file: {str(e)}")
            except Exception as exc:
                # Log any other unexpected exceptions
                logging.exception(exc)
                QtWidgets.QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(exc)}")

    def exportFile(self) -> None:
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export JSON",
            os.path.expanduser("~"),
            "JSON (*.json)",
        )
        if filename:
            # Add .json extension if not already present
            if not filename.endswith(".json"):
                filename = f"{filename}.json"
            try:
                boundingBoxes: list = []
                for item in self.boundingBoxes():
                    boundingBoxes.append({
                        "enabled": item.isEnabled(),
                        "type": item.typename(),
                        "first_strip": item.firstStrip(),
                        "last_strip": item.lastStrip(),
                        "minimum_value": item.minimumValue(),
                        "maximum_value": item.maximumValue(),
                        "unit": item.unit(),
                    })
                data = {
                    "bounding_boxes": boundingBoxes,
                }
                with open(filename, "wt") as fp:
                    json.dump(data, fp)
            except Exception as exc:
                logging.exception(exc)
                QtWidgets.QMessageBox.critical(self, "Error", f"An unexpected error occurred: {exc}")

    def updateBoxes(self) -> None:
        boundingBoxes: list = []
        markers: list = []
        strips: set = set()
        for index in range(self.boxesTreeWidget.topLevelItemCount()):
            item = self.boxesTreeWidget.topLevelItem(index)
            if isinstance(item, BoundingBoxItem):
                if not item.isEnabled():
                    continue
                unit = ureg(item.unit())
                minimumValue = (item.minimumValue() * unit).to_base_units().m
                maximumValue = (item.maximumValue() * unit).to_base_units().m
                topLeft = QtCore.QPointF(item.firstStrip(), maximumValue)
                bottomRight = QtCore.QPointF(item.lastStrip(), minimumValue)
                boundingBoxes.append((item.typename(), QtCore.QRectF(topLeft, bottomRight)))
        self.boxesChanged.emit(boundingBoxes)
        for type_ in self.fields:
            for badStrip in self.filterBadStrips(type_):
                strip, value = badStrip
                strips.add(strip)
                markers.append((type_, QtCore.QPointF(strip - 1, value)))  # HACK lazy: strip -> strip_index
        self.markersChanged.emit(markers)
        self.updatePreview(list(strips))

    def addBoundingBox(self, item: BoundingBoxItem) -> None:
        self.boxesTreeWidget.addTopLevelItem(item)

    def clearBoundingBoxes(self) -> None:
        while self.boxesTreeWidget.topLevelItemCount():
            self.boxesTreeWidget.takeTopLevelItem(0)

    def boundingBoxes(self) -> list[BoundingBoxItem]:
        boundingBoxes = []
        for index in range(self.boxesTreeWidget.topLevelItemCount()):
            item = self.boxesTreeWidget.topLevelItem(index)
            if isinstance(item, BoundingBoxItem):
                boundingBoxes.append(item)
        return boundingBoxes

    def readSettings(self, namespace: str) -> None:
        hashedNamespace = hashlib.sha256(namespace.encode()).hexdigest()
        settings = QtCore.QSettings()
        settings.beginGroup(self.objectName())
        geometry = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)
        settings.beginGroup("boundingBoxes")
        size = settings.beginReadArray(hashedNamespace)
        self.clearBoundingBoxes()
        for index in range(size):
            settings.setArrayIndex(index)
            item = BoundingBoxItem()
            item.setEnabled(settings.value("enabled", True, bool))
            item.setTypename(settings.value("type", "", str))
            item.setFirstStrip(settings.value("firstStrip", 0, int))
            item.setLastStrip(settings.value("lastStrip", 0, int))
            item.setMinimumValue(settings.value("minimumValue", 0, float))
            item.setMaximumValue(settings.value("maximumValue", 0, float))
            item.setUnit(settings.value("unit", "", str))
            self.addBoundingBox(item)
        settings.endArray()
        settings.endGroup()
        settings.endGroup()
        self.restoreGeometry(geometry)
        self.updateBoxes()

    def writeSettings(self, namespace: str) -> None:
        boundingBoxes = self.boundingBoxes()
        hashedNamespace = hashlib.sha256(namespace.encode()).hexdigest()
        settings = QtCore.QSettings()
        settings.beginGroup(self.objectName())
        settings.setValue("geometry", self.saveGeometry())
        settings.beginGroup("boundingBoxes")
        settings.beginWriteArray(hashedNamespace, len(boundingBoxes))
        for index, item in enumerate(boundingBoxes):
            settings.setArrayIndex(index)
            settings.setValue("enabled", item.isEnabled())
            settings.setValue("type", item.typename())
            settings.setValue("firstStrip", item.firstStrip())
            settings.setValue("lastStrip", item.lastStrip())
            settings.setValue("minimumValue", item.minimumValue())
            settings.setValue("maximumValue", item.maximumValue())
            settings.setValue("unit", item.unit())
        settings.endArray()
        settings.endGroup()
        settings.endGroup()

    def selectedStrips(self) -> str:
        return self.previewLineEdit.text()

    def updatePreview(self, strips: list) -> None:
        self.previewLineEdit.setText(compress_strips(strips))
        self.previewLineEdit.setCursorPosition(0)

    def filterBadStrips(self, typename: str) -> list[tuple]:
        badStrips: list[tuple] = []
        boxes: list = []
        try:
            for item in self.boundingBoxes():
                if item.isEnabled() and item.typename() == typename:
                    unit = ureg(item.unit())
                    boxes.append((
                        item.firstStrip(),
                        item.lastStrip(),
                        (item.minimumValue() * unit).to_base_units().m,
                        (item.maximumValue() * unit).to_base_units().m,
                    ))
            field = self.fields.get(typename)
            for name, items in self._data.get(typename, {}).items():
                for item in items:
                    strip = int(item.get("strip"))
                    value = item.get(field)
                    if strip is None or value is None:
                        continue
                    found_match = False
                    found_box = False
                    for first_strip, last_strip, minimum_value, maximum_value in boxes:
                        if first_strip <= strip <= last_strip:
                            found_box = True
                            if minimum_value <= value <= maximum_value:
                                found_match = True
                                break
                    if found_box and not found_match:
                        badStrips.append((strip, value))
        except Exception as exc:
            logging.exception(exc)
        return badStrips
