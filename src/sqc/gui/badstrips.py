from typing import Dict, Optional

from PyQt5 import QtCore, QtWidgets


class BadStripSelectDialog(QtWidgets.QDialog):

    def __init__(self, parent: Optional[QtWidgets.QWidget]) -> None:
        super().__init__(parent)

        self.setObjectName("BadStripSelectDialog")
        self.setWindowTitle("Select Bad Strips")

        self.statistics = None

        self.remeasureCountSpinBox = QtWidgets.QSpinBox(self)
        self.remeasureCountSpinBox.setRange(1, 99)
        self.remeasureCountSpinBox.valueChanged.connect(self.updatePreview)

        self.previewTreeWidget = QtWidgets.QTreeWidget(self)
        self.previewTreeWidget.setHeaderLabels(["Strip", "Count"])
        self.previewTreeWidget.setRootIsDecorated(False)

        self.buttonBox = QtWidgets.QDialogButtonBox(self)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Minimal Re-Measure Count"))
        layout.addWidget(self.remeasureCountSpinBox)
        layout.addWidget(QtWidgets.QLabel("Preview"))
        layout.addWidget(self.previewTreeWidget)
        layout.addWidget(self.buttonBox)

    def readSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup(self.objectName())
        geometry = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)
        remeasureCount = settings.value("remeasureCount", 1, int)
        settings.endGroup()
        self.restoreGeometry(geometry)
        self.setRemeasureCount(remeasureCount)

    def writeSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup(self.objectName())
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("remeasureCount", self.remeasureCount())
        settings.endGroup()

    def setRemeasureCount(self, count: int) -> None:
        self.remeasureCountSpinBox.setValue(count)

    def remeasureCount(self) -> int:
        return self.remeasureCountSpinBox.value()

    def setStatistics(self, statistics) -> None:
        self.statistics = statistics
        self.updatePreview()

    def selectedStrips(self) -> str:
        threshold = self.remeasureCount()
        strips = self.filterStrips(threshold).keys()
        return ", ".join([format(strip) for strip in strips])

    def updatePreview(self) -> None:
        threshold = self.remeasureCount()
        self.previewTreeWidget.clear()
        root = self.previewTreeWidget.invisibleRootItem()
        for strip, count in self.filterStrips(threshold).items():
            item = QtWidgets.QTreeWidgetItem([str(strip), str(count)])
            root.addChild(item)

    def filterStrips(self, threshold: int) -> Dict[str, int]:
        strips: Dict[str, int] = {}
        if self.statistics is not None:
            for strip, counter in self.statistics.remeasure_counter.items():
                values = counter.values()
                max_value = max(values or [0])
                if max_value >= threshold:
                    strips[strip] = max_value
        return strips
