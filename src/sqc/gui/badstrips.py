import logging
from typing import Dict, Optional

from PyQt5 import QtCore, QtWidgets

from comet.utils import ureg


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
        value = int(float(index.data(QtCore.Qt.DisplayRole).split()[0].strip()))
        editor.setValue(value)

    def setModelData(self, editor, model, index) -> None:
        model.setData(index, f"{editor.value()}", QtCore.Qt.EditRole)


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
        model.setData(index, f"{editor.value():.3f}", QtCore.Qt.EditRole)


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

        self.previewLabel = QtWidgets.QLabel(self)
        self.previewLabel.setText("Preview")

        self.previewLineEdit = QtWidgets.QLineEdit(self)
        self.previewLineEdit.setReadOnly(True)

        self.buttonBox = QtWidgets.QDialogButtonBox(self)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.boxesLayout = QtWidgets.QGridLayout()
        self.boxesLayout.addWidget(self.boxesTreeWidget, 0, 0, 3, 1)
        self.boxesLayout.addWidget(self.addBoxButton, 0, 1, 1, 1)
        self.boxesLayout.addWidget(self.removeBoxButton, 1, 1, 1, 1)

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
        for type_, units in self.units.items():
            if units:
                self.addBoundingBox(True, type_, 0, 0, 0, 0, units[0])
            break

    def removeCurrentBox(self) -> None:
        item = self.boxesTreeWidget.currentItem()
        if item:
            index = self.boxesTreeWidget.indexOfTopLevelItem(item)
            self.boxesTreeWidget.takeTopLevelItem(index)

    def updateBoxes(self) -> None:
        boundingBoxes: list = []
        markers: list = []
        strips: set = set()
        for index in range(self.boxesTreeWidget.topLevelItemCount()):
            item = self.boxesTreeWidget.topLevelItem(index)
            if item and item.checkState(0) == QtCore.Qt.Checked:
                type_ = item.text(0)
                unit = item.text(5)
                first_strip = int(safe_float(item.text(1)))
                last_strip = int(safe_float(item.text(2)))
                minimum_value = (safe_float(item.text(3)) * ureg(unit)).to_base_units().m
                maximum_value = (safe_float(item.text(4)) * ureg(unit)).to_base_units().m
                topLeft = QtCore.QPointF(first_strip, maximum_value)
                bottomRight = QtCore.QPointF(last_strip, minimum_value)
                boundingBoxes.append((type_, QtCore.QRectF(topLeft, bottomRight)))
        self.boxesChanged.emit(boundingBoxes)
        for type_ in self.fields:
            for badStrip in self.filterBadStrips(type_):
                strip, value = badStrip
                strips.add(strip)
                markers.append((type_, QtCore.QPointF(strip - 1, value)))  # HACK lazy: strip -> strip_index
        self.markersChanged.emit(markers)
        self.updatePreview(list(strips))

    def addBoundingBox(self, enabled: bool, type: str, first_strip: int, last_strip: int, minimum_value: float, maximum_value: float, unit: str) -> None:
        item = QtWidgets.QTreeWidgetItem(self.boxesTreeWidget)
        item.setText(0, str(type))
        item.setText(1, str(first_strip))
        item.setText(2, str(last_strip))
        item.setText(3, str(minimum_value))
        item.setText(4, str(maximum_value))
        item.setText(5, str(unit))
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
                    "first_strip": int(safe_float(item.text(1))),
                    "last_strip": int(safe_float(item.text(2))),
                    "minimum_value": safe_float(item.text(3)),
                    "maximum_value": safe_float(item.text(4)),
                    "unit": item.text(5),
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
                    type_ = boundingBox.get("type")
                    if type_ is None:
                        continue
                    unit = boundingBox.get("unit")
                    if unit is None:
                        continue
                    if unit in self.units.get(type_, []):
                        self.addBoundingBox(
                            enabled=boundingBox.get("enabled", True),
                            type=type_,
                            first_strip=int(safe_float(boundingBox.get("first_strip", 0))),
                            last_strip=int(safe_float(boundingBox.get("last_strip", 0))),
                            minimum_value=safe_float(boundingBox.get("minimum_value", 0.0)),
                            maximum_value=safe_float(boundingBox.get("maximum_value", 0.0)),
                            unit=unit,
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
        return self.previewLineEdit.text()

    def updatePreview(self, strips: list) -> None:
        self.previewLineEdit.setText(compress_strips(strips))

    def filterBadStrips(self, type_: str) -> list[tuple]:
        badStrips: list[tuple] = []
        boxes: list = []
        try:
            for box in self.boundingBoxes():
                if box.get("enabled") and box.get("type") == type_:
                    boxes.append((
                        box.get("first_strip"),
                        box.get("last_strip"),
                        (box.get("minimum_value") * ureg(box.get("unit"))).to_base_units().m,
                        (box.get("maximum_value") * ureg(box.get("unit"))).to_base_units().m,
                    ))
            field = self.fields.get(type_)
            for name, items in self._data.get(type_, {}).items():
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
