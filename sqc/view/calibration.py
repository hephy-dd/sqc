import logging
import random
from functools import partial
from typing import Iterable, List, Optional, Tuple, Optional

from comet.utils import ureg
from PyQt5 import QtCore, QtWidgets


__all__ = ["TableCalibrationDialog", "NeedlesCalibrationDialog", "NeedlesDiagnoseDialog"]

logger = logging.getLogger(__name__)


class TaskListWidget(QtWidgets.QWidget):

    stateChanged = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.taskWidgets: List[QtWidgets.QAbstractButton] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

    def addTask(self, text: str) -> None:
        widget = QtWidgets.QCheckBox(self)
        widget.setText(text)
        widget.stateChanged.connect(self.stateChanged)
        self.stateChanged.emit()
        self.taskWidgets.append(widget)
        self.layout().addWidget(widget)

    def clear(self) -> None:
        for widget in self.taskWidgets:
            widget.setChecked(False)

    def isFinished(self) -> bool:
        for widget in self.taskWidgets:
            if not widget.isChecked():
                return False
        return True


class CalibrationDialog(QtWidgets.QDialog):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("locked", False)

        self.noticeLabel = QtWidgets.QLabel(self)
        self.noticeLabel.setText("<b>Important:</b> this is a maintainance operation. Make sure to double check<br/> following conditions to prevent damage to the equipment!")

        self.taskListWidget = TaskListWidget()
        self.taskListWidget.stateChanged.connect(self.updateState)

        self.progressBar = QtWidgets.QProgressBar(self)
        self.progressBar.setVisible(False)

        self.buttonBox = QtWidgets.QDialogButtonBox()
        self.okButton = self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.cancelButton = self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.abortButton = self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Abort)
        self.abortButton.setVisible(False)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.noticeLabel)
        layout.addWidget(self.taskListWidget)
        layout.addStretch()
        layout.addWidget(self.progressBar)
        layout.addWidget(self.buttonBox)

        self.updateState()

    def isLocked(self) -> bool:
        return self.property("locked")

    def setLocked(self, locked: bool) -> None:
        self.setProperty("locked", locked)
        self.taskListWidget.setEnabled(not locked)
        self.progressBar.setVisible(locked)
        self.okButton.setVisible(not locked)
        self.cancelButton.setVisible(not locked)
        self.abortButton.setVisible(locked)

    def addTask(self, text: str) -> None:
        self.taskListWidget.addTask(text)

    def setProgress(self, value: int, maximum: int) -> None:
        self.progressBar.setRange(0, maximum)
        self.progressBar.setValue(value)

    def updateState(self):
        enabled = self.taskListWidget.isFinished()
        self.okButton.setEnabled(enabled)

    def calibrate(self) -> None:
        ...

    def abort(self) -> None:
        ...

    def accept(self):
        self.setLocked(True)
        self.calibrate()

    def reject(self):
        if not self.isLocked():
            super().reject()
        else:
            self.abort()


class TableCalibrationDialog(CalibrationDialog):

    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Calibrate Corvus")

        self.addTask("Microscope moved to back")
        self.addTask("Positioners moved up (Z-screw)")
        self.addTask("Positioners moved away from table")

        self.controller = controller
        self.controller.progressChanged.connect(self.setProgress)
        self.controller.movementFinished.connect(lambda: self.setLocked(False))
        self.controller.movementFinished.connect(lambda: self.close())

    def calibrate(self) -> None:
        self.controller.requestCalibrate()

    def abort(self) -> None:
        self.controller.requestAbort()


class NeedlesCalibrationDialog(CalibrationDialog):

    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(f"Calibrate TANGO")

        self.addTask("Positioners moved up (Z-screw)")
        self.addTask("Positioners moved away from table")

        self.controller = controller
        self.controller.progressChanged.connect(self.setProgress)
        self.controller.movementFinished.connect(lambda: self.setLocked(False))
        self.controller.movementFinished.connect(lambda: self.close())

    def calibrate(self) -> None:
        self.controller.requestCalibrate()

    def abort(self) -> None:
        self.controller.requestAbort()


class TextDialog(QtWidgets.QDialog):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.textEdit = QtWidgets.QPlainTextEdit(self)
        self.textEdit.setReadOnly(True)

        self.buttonBox = QtWidgets.QDialogButtonBox()
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Close)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.textEdit)
        layout.addWidget(self.buttonBox)

    def text(self) -> str:
        return self.textEdit.toPlainText()

    def setText(self, text: str) -> None:
        self.textEdit.setPlainText(text)


class NeedlesDiagnoseDialog(TextDialog):

    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("TANGO diagnosis")
        self.setEnabled(False)

        self.controller = controller

    def diagnose(self) -> None:
        try:
            text = self.controller.diagnose()
        except Exception as exc:
            logger.exception(exc)
            QtWidgets.QMessageBox.critical(self, "Exception occured", format(exc))
        else:
            self.setText(text)
        finally:
            self.setEnabled(True)
