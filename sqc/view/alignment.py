import logging
import random
import threading
import os
import sys
import time
import subprocess
from functools import partial
from typing import Iterable, List, Optional, Tuple, Optional

import numpy as np

from comet.utils import ureg, make_iso, safe_filename

from PyQt5 import QtCore, QtGui, QtWidgets

from ..controller.needle import NeedleController
from ..controller.table import TableController
from ..core.camera import camera_registry
from ..core.geometry import Pad, Padfile, NeedlesGeometry
from ..core.geometry import load as load_padfile
from ..core.transformation import affine_transformation, transform
from ..core.utils import alternate_traversal
from ..settings import Settings

from .calibration import TableCalibrationDialog, NeedlesCalibrationDialog
from .cameraview import CameraScene, CameraView

__all__ = ["AlignmentDialog"]

logger = logging.getLogger(__name__)


Position = Tuple[float, float, float]


def open_directory(path='.'):
    try:
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':
            subprocess.check_call(['open', '--', path])
        else:  # 'linux' and possibly 'freebsd' etc.
            subprocess.check_call(['xdg-open', path])
    except Exception as e:
        print(f"Error opening directory: {e}")


def generate_noise_with_exposure(height, width, exposure=1.0):
    """
    Generate random noise in RGB format and adjust its brightness based on exposure.

    Parameters:
    - height: The height of the image.
    - width: The width of the image.
    - exposure: Exposure setting (multiplier to adjust brightness).
                > 1.0 makes the image brighter, < 1.0 makes it darker.

    Returns:
    - A numpy array representing the noise image with adjusted brightness.
    """

    # Generate random values between 0 and 255 for an RGB image
    noise_image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8).astype(np.float32)

    # Adjust the brightness based on the exposure setting (in-place operation)
    np.multiply(noise_image, exposure, out=noise_image)

    # Clip values to be within the [0, 255] range and convert to uint8 (in-place when possible)
    return np.clip(noise_image, 0, 255, out=noise_image).astype(np.uint8)



def exposure_to_multiplier(exposure):
    """
    Convert an exposure value in the range [0, 250] to a brightness multiplier.

    Parameters:
    - exposure: Exposure value in the range [0, 250]

    Returns:
    - Brightness multiplier.
    """
    # Define the minimum and maximum multipliers
    min_multiplier = 0.5
    max_multiplier = 2.0

    # Linearly interpolate between the minimum and maximum multipliers
    multiplier = min_multiplier + (exposure/250.0) * (max_multiplier - min_multiplier)

    return multiplier


class DummyCamera:

    def __init__(self, config):
        self.frame_handlers = []
        self.free_running = False
        self.frame_thread = None
        self.exposure = 30

    def start(self):
        self.free_running = True
        self.frame_thread = threading.Thread(target=self.capture)
        self.frame_thread.start()

    def stop(self):
        self.free_running = False

    def set_exposure(self, exposure):
        self.exposure = exposure

    def add_frame_handler(self, handler):
        self.frame_handlers.append(handler)

    def shutdown(self):
        self.free_running = False
        if self.frame_thread:
            self.frame_thread.join()

    def capture(self):
        try:
            while self.free_running:
                t = time.monotonic()
                width = 768*4
                height = 512*4
                exposure = exposure_to_multiplier(self.exposure)
                image_data = generate_noise_with_exposure(height, width, exposure)
                for handler in self.frame_handlers:
                    handler(image_data)
                waiting_time = max((1/20.) - (time.monotonic() - t), 0)
                time.sleep(waiting_time)
        except Exception as exc:
            logging.exception(exc)


class ReferenceItem(QtWidgets.QTreeWidgetItem):

    PadRole: int = 0x2000
    PositionRole: int = 0x2001

    def __init__(self, pad: Pad) -> None:
        super().__init__()
        self.setData(0, type(self).PadRole, pad)
        self.setData(0, type(self).PositionRole, None)
        self.setText(0, format(pad.name))
        self.setText(1, format(pad.x))
        self.setText(2, format(pad.y))
        self.setText(3, format(pad.z))
        self.setText(4, "")
        self.reset()

    def reset(self) -> None:
        self.setData(0, type(self).PositionRole, None)
        self.setText(4, "not assigned")

    def pad(self) -> Pad:
        return self.data(0, type(self).PadRole)

    def position(self) -> Optional[Position]:
        return self.data(0, type(self).PositionRole)

    def setPosition(self, position: Position) -> None:
        self.setData(0, type(self).PositionRole, position)
        self.setText(4, format(position))


class SelectPadDialog(QtWidgets.QDialog):

    PadRole: int = 0x2000

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Pad")

        self.filterLineEdit = QtWidgets.QLineEdit(self)
        self.filterLineEdit.setPlaceholderText("Filter...")
        self.filterLineEdit.setClearButtonEnabled(True)
        self.filterLineEdit.textChanged.connect(self.filterList)

        self.listWidget = QtWidgets.QListWidget(self)
        self.listWidget.itemSelectionChanged.connect(self.updateButtonBox)
        self.listWidget.doubleClicked.connect(self.accept)

        self.buttonBox = QtWidgets.QDialogButtonBox(self)
        self.acceptButton = self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Ok)
        self.acceptButton.setEnabled(False)
        self.buttonBox.addButton(self.buttonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.filterLineEdit)
        layout.addWidget(self.listWidget)
        layout.addWidget(self.buttonBox)

    def addPad(self, pad: Pad) -> None:
        item = QtWidgets.QListWidgetItem()
        item.setText(pad.name)
        item.setData(type(self).PadRole, pad)
        self.listWidget.addItem(item)

    def setPads(self, pads: Iterable[Pad]) -> None:
        self.listWidget.clear()
        for pad in pads:
            self.addPad(pad)

    def currentPad(self):
        item = self.listWidget.currentItem()
        if item:
            return item.data(type(self).PadRole)
        return None

    def updateButtonBox(self) -> None:
        item = self.listWidget.currentItem()
        self.acceptButton.setEnabled(item is not None)

    def filterList(self) -> None:
        needle = self.filterLineEdit.text().strip().lower()
        currentItem = self.listWidget.currentItem()
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item:
                hidden = needle not in item.text().lower()
                item.setHidden(hidden)
        if currentItem:
            if not currentItem.isHidden():
                self.listWidget.scrollToItem(currentItem)
            else:
                self.listWidget.setCurrentItem(None)


class AlignmentController:

    def __init__(self, items):
        self.items = items
        self._transform = None

    def reset(self):
        self._transform = None
        for item in self.items:
            item.reset()

    def isAligned(self) -> bool:
        for item in self.items:
            if item.position() is None:
                return False
        return True

    def assignPosition(self, item, position: Position):
        x, y, z = position
        if item in self.items:
            item.setPosition((x, y, z))

    def assignedItems(self):
        items = []
        for item in self.items:
            if item.position() is not None:
                items.append(item)
        return items

    def nextItem(self):
        """Return next item to be alligned or None."""
        for item in self.items:
            if item.position() is None:
                return item
        return None

    def position(self, item: ReferenceItem) -> Optional[Position]:
        """Return assigned position or position relative to other assigned item."""
        if item.position():
            return item.position()
        for ref in self.assignedItems():
            a, b, c = ref.pad().position
            d, e, f = item.pad().position
            g, h, i = a+d, b+e, c+f
            x, y, z = ref.position()
            return x+g, y+h, z+i
        return None

    def calculateMatrix(self):
        """Calculate transformattion matrix from reference points."""
        items = self.assignedItems()
        if len(items) >= 3:
            s1 = items[0].pad().position
            s2 = items[1].pad().position
            s3 = items[2].pad().position
            t1 = items[0].position()
            t2 = items[1].position()
            t3 = items[2].position()
            T, V0 = affine_transformation(s1, s2, s3, t1, t2, t3)
            logger.info("Calculated transformation: %s %s", T, V0)
            self._transform = partial(transform, T, V0)

    def transform(self, position: Position) -> Position:
        if not self._transform:
            raise RuntimeError("No transformation matrix assigned.")
        return self._transform(position)


class ControlWidget(QtWidgets.QTabWidget):

    lockedStateChanged = QtCore.pyqtSignal(bool)

    def __init__(self, context, scene, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.context = context
        self.scene = scene

        self.setCurrentPosition((0, 0, 0))

        self.tableController = TableController(context.station, self)
        self.tableController.positionChanged.connect(self.updatePosition)
        self.tableController.movementFinished.connect(self.finishMove)
        self.tableController.failed.connect(self.showException)
        self.tableController.start()

        self.needleController = NeedleController(context.station)
        # self.needleController.positionChanged.connect(self.updateNeedlesPosition)
        self.needleController.movementFinished.connect(self.finishMove)
        self.needleController.failed.connect(self.showException)
        self.needleController.start()

        self.alignmentController = AlignmentController([])

        self.controlWidget = QtWidgets.QWidget(self)

        self.optionsWidget = OptionsWidget(self)

        self.optionsScrollArea = QtWidgets.QScrollArea(self)
        self.optionsScrollArea.setWidget(self.optionsWidget)

        self.addTab(self.controlWidget, "Controls")
        self.addTab(self.optionsScrollArea, "Options")

        self.moveLeftButton = QtWidgets.QPushButton("-X")
        self.moveLeftButton.setFixedSize(32, 32)
        self.moveLeftButton.setDefault(True)
        self.moveLeftButton.clicked.connect(self.moveLeft)

        self.moveRightButton = QtWidgets.QPushButton("+X")
        self.moveRightButton.setFixedSize(32, 32)
        self.moveRightButton.clicked.connect(self.moveRight)

        self.moveTopButton = QtWidgets.QPushButton("+Y")
        self.moveTopButton.setFixedSize(32, 32)
        self.moveTopButton.clicked.connect(self.moveTop)

        self.moveBottomButton = QtWidgets.QPushButton("-Y")
        self.moveBottomButton.setFixedSize(32, 32)
        self.moveBottomButton.clicked.connect(self.moveBottom)

        self.spacerWidget = QtWidgets.QWidget()
        self.spacerWidget.setFixedSize(32, 32)

        self.moveUpButton = QtWidgets.QPushButton("+Z")
        self.moveUpButton.setFixedSize(32, 32)
        self.moveUpButton.clicked.connect(self.moveUp)

        self.moveDownButton = QtWidgets.QPushButton("-Z")
        self.moveDownButton.setFixedSize(32, 32)
        self.moveDownButton.clicked.connect(self.moveDown)

        self.joystickCheckBox = QtWidgets.QCheckBox("Enable Joystick", self)
        self.joystickCheckBox.setChecked(False)
        self.joystickCheckBox.toggled.connect(self.toggleJoystick)

        self.stepButtonGroup = QtWidgets.QButtonGroup(self.controlWidget)

        self.stepButtonGroup.buttonClicked.connect(self.updateStep)

        self.alignmentTreeWidget = QtWidgets.QTreeWidget()
        headerItem = QtWidgets.QTreeWidgetItem()
        headerItem.setText(0, "Reference Pad")
        headerItem.setText(1, "X")
        headerItem.setText(2, "Y")
        headerItem.setText(3, "Z")
        headerItem.setText(4, "Position")
        self.alignmentTreeWidget.setHeaderItem(headerItem)
        self.alignmentTreeWidget.setRootIsDecorated(False)
        self.alignmentTreeWidget.itemSelectionChanged.connect(self.alignmentItemChanged)

        self.moveMeasureButton = QtWidgets.QPushButton("Measure Position")
        self.moveMeasureButton.clicked.connect(self.moveMeasurePosition)

        self.moveLoadButton = QtWidgets.QPushButton("Load Position")
        self.moveLoadButton.clicked.connect(self.moveLoadPosition)

        self.needlesUpButton = QtWidgets.QPushButton("Up")
        self.needlesUpButton.clicked.connect(self.moveNeedlesUp)

        self.needlesDownButton = QtWidgets.QPushButton("Down")
        self.needlesDownButton.clicked.connect(self.moveNeedlesDown)

        self.lightButton = QtWidgets.QPushButton("Light")
        self.lightButton.setCheckable(True)
        self.lightButton.setChecked(True)

        # Contact pads

        self.contactButton = QtWidgets.QPushButton("Contact &Pad...")
        self.contactButton.setToolTip("Contact a pad with needles")
        self.contactButton.setEnabled(False)
        self.contactButton.clicked.connect(self.moveToPad)

        # Inspect pads

        self.inspectButton = QtWidgets.QPushButton("&Inspect Pad...")
        self.inspectButton.setToolTip("Inspect a pad without contacting")
        self.inspectButton.setEnabled(False)
        self.inspectButton.clicked.connect(self.moveToInspectPad)

        # Alignment

        self.inspectReferenceButton = QtWidgets.QPushButton("&Inspect")
        self.inspectReferenceButton.setEnabled(False)
        self.inspectReferenceButton.clicked.connect(self.moveToReference)

        self.assignButton = QtWidgets.QPushButton("&Assign")
        self.assignButton.setEnabled(False)
        self.assignButton.clicked.connect(self.assignItem)

        self.resetButton = QtWidgets.QPushButton("Reset")
        self.resetButton.clicked.connect(self.resetAlignment)

        self.saveButton = QtWidgets.QPushButton("Save")
        self.saveButton.setEnabled(False)
        self.saveButton.clicked.connect(self.saveAlignment)

        self.showInspectDialogButton = QtWidgets.QPushButton("Inspection")
        self.showInspectDialogButton.setEnabled(False)
        self.showInspectDialogButton.clicked.connect(self.showInspectDialog)

        self.commandsGroupBox = QtWidgets.QGroupBox()
        self.commandsGroupBox.setTitle("Commands")

        self.needlesGroupBox = QtWidgets.QGroupBox()
        self.needlesGroupBox.setTitle("Needles")

        self.boxGroupBox = QtWidgets.QGroupBox()
        self.boxGroupBox.setTitle("Box")
        self.boxGroupBox.setHidden(True)

        buttonsLayout = QtWidgets.QVBoxLayout(self.commandsGroupBox)
        buttonsLayout.addWidget(self.moveMeasureButton)
        buttonsLayout.addWidget(self.contactButton)
        buttonsLayout.addWidget(self.inspectButton)
        buttonsLayout.addWidget(self.moveLoadButton)

        needlesLayout = QtWidgets.QVBoxLayout(self.needlesGroupBox)
        needlesLayout.addWidget(self.needlesUpButton)
        needlesLayout.addWidget(self.needlesDownButton)

        boxLayout = QtWidgets.QVBoxLayout(self.boxGroupBox)
        boxLayout.addWidget(self.lightButton)

        self.dialGroupBox = QtWidgets.QGroupBox()
        self.dialGroupBox.setTitle("Control")

        dialLayout = QtWidgets.QGridLayout(self.dialGroupBox)
        dialLayout.addWidget(self.moveLeftButton, 1, 1)
        dialLayout.addWidget(self.moveRightButton, 1, 3)
        dialLayout.addWidget(self.moveTopButton, 0, 2)
        dialLayout.addWidget(self.moveBottomButton, 2, 2)
        dialLayout.addWidget(self.moveUpButton, 0, 5)
        dialLayout.addWidget(self.moveDownButton, 2, 5)
        dialLayout.setRowStretch(4, 1)

        self.stepGroupBox = QtWidgets.QGroupBox()
        self.stepGroupBox.setTitle("Step Width")

        self.stepLayout = QtWidgets.QVBoxLayout(self.stepGroupBox)

        self.alignmentGroupBox = QtWidgets.QGroupBox()
        self.alignmentGroupBox.setTitle("Alignment")

        self.nextButton = QtWidgets.QPushButton("Next")
        self.nextButton.setEnabled(False)
        self.nextButton.clicked.connect(self.nextAlignment)

        self.alignmentHintLabel = QtWidgets.QLabel("Click <b>Reset</b> to begin a new alignment.")

        alignmentLeftLayout = QtWidgets.QVBoxLayout()
        alignmentLeftLayout.addWidget(self.assignButton)
        alignmentLeftLayout.addWidget(self.nextButton)
        alignmentLeftLayout.addWidget(self.saveButton)
        alignmentLeftLayout.addWidget(self.showInspectDialogButton)
        alignmentLeftLayout.addStretch()

        alignmentCenterLayout = QtWidgets.QVBoxLayout()
        alignmentCenterLayout.addWidget(self.alignmentTreeWidget)
        alignmentCenterLayout.addWidget(self.alignmentHintLabel)

        alignmentRightLayout = QtWidgets.QVBoxLayout()
        alignmentRightLayout.addWidget(self.inspectReferenceButton)
        alignmentRightLayout.addWidget(self.resetButton)
        alignmentRightLayout.addStretch()

        alignmentLayout = QtWidgets.QHBoxLayout(self.alignmentGroupBox)
        alignmentLayout.addLayout(alignmentLeftLayout)
        alignmentLayout.addLayout(alignmentCenterLayout)
        alignmentLayout.addLayout(alignmentRightLayout)

        # Table position

        self.tableGroupBox = QtWidgets.QGroupBox(self)
        self.tableGroupBox.setTitle("Table Position")

        self.tableXLabel = QtWidgets.QLabel(self)
        self.tableXLabel.setAlignment(QtCore.Qt.AlignRight)

        self.tableYLabel = QtWidgets.QLabel(self)
        self.tableYLabel.setAlignment(QtCore.Qt.AlignRight)

        self.tableZLabel = QtWidgets.QLabel(self)
        self.tableZLabel.setAlignment(QtCore.Qt.AlignRight)

        tableLayout = QtWidgets.QFormLayout(self.tableGroupBox)
        tableLayout.addRow("X", self.tableXLabel)
        tableLayout.addRow("Y", self.tableYLabel)
        tableLayout.addRow("Z", self.tableZLabel)

        # self.tableCalibrationGroupBox = QtWidgets.QGroupBox(self)
        # self.tableCalibrationGroupBox.setTitle("Table Calibration")

        # tableCalibrationLayout = QtWidgets.QFormLayout(self.tableCalibrationGroupBox)

        # self.needlesPositionGroupBox = QtWidgets.QGroupBox(self)
        # self.needlesPositionGroupBox.setTitle("TANGO Position")

        # self.needlesXLabel = QtWidgets.QLabel(self)
        # self.needlesXLabel.setAlignment(QtCore.Qt.AlignRight)

        # needlesLayout = QtWidgets.QFormLayout(self.needlesPositionGroupBox)
        # needlesLayout.addRow("X", self.needlesXLabel)

        # self.needlesCalibrationGroupBox = QtWidgets.QGroupBox(self)
        # self.needlesCalibrationGroupBox.setTitle("TANGO Calibration")

        # needlesCalibrationLayout = QtWidgets.QFormLayout(self.needlesCalibrationGroupBox)

        rightLayout = QtWidgets.QVBoxLayout()
        rightLayout.addWidget(self.tableGroupBox)
        # rightLayout.addWidget(self.tableCalibrationGroupBox)
        # rightLayout.addWidget(self.needlesPositionGroupBox)
        # rightLayout.addWidget(self.needlesCalibrationGroupBox)
        # rightLayout.setStretch(3, 1)

        leftCommandsLayout = QtWidgets.QVBoxLayout()
        leftCommandsLayout.addWidget(self.commandsGroupBox)
        leftCommandsLayout.addWidget(self.needlesGroupBox)
        leftCommandsLayout.addWidget(self.boxGroupBox)
        leftCommandsLayout.addWidget(self.joystickCheckBox)
        leftCommandsLayout.addStretch()

        controlLayout = QtWidgets.QHBoxLayout(self.controlWidget)
        controlLayout.addLayout(leftCommandsLayout)
        controlLayout.addWidget(self.dialGroupBox)
        controlLayout.addWidget(self.stepGroupBox)
        controlLayout.addWidget(self.alignmentGroupBox)
        controlLayout.addLayout(rightLayout)

        QtCore.QTimer.singleShot(500, self.requestPosition)

        self.updateAlignmentButtons()

        self.createStepButtons()

        self.optionsWidget.stepsChanged.connect(self.createStepButtons)

    def shutdown(self) -> None:
        self.tableController.shutdown()
        self.needleController.shutdown()

    def setLocked(self, locked: bool) -> None:
        self.commandsGroupBox.setEnabled(not locked)
        self.needlesGroupBox.setEnabled(not locked)
        self.boxGroupBox.setEnabled(not locked)
        self.dialGroupBox.setEnabled(not locked)
        self.stepGroupBox.setEnabled(not locked)
        self.alignmentGroupBox.setEnabled(not locked)
        self.optionsWidget.setEnabled(not locked)
        if self.joystickCheckBox.isChecked():
            self.joystickCheckBox.setEnabled(True)
        else:
            self.joystickCheckBox.setEnabled(not locked)
        self.lockedStateChanged.emit(locked)

    def clearStepButtons(self) -> None:
        while self.stepLayout.count():
            self.stepLayout.takeAt(0)
        buttons = self.stepButtonGroup.buttons()
        for button in buttons:
            self.stepButtonGroup.removeButton(button)
            button.setParent(None)  # type: ignore
            button.deleteLater()

    def createStepButtons(self) -> None:
        self.clearStepButtons()
        for step in self.optionsWidget.steps():
            button = QtWidgets.QPushButton(self)
            button.setText(f"{step} um")
            button.setProperty("stepWidth", step)
            button.setCheckable(True)
            if not self.stepButtonGroup.buttons():
                button.setChecked(True)
            self.stepButtonGroup.addButton(button)
            self.stepLayout.addWidget(button)
        self.stepLayout.addStretch()

    def currentPosition(self) -> Tuple[int, int, int]:
        return self.property("currentPosition")

    def setCurrentPosition(self, position: Tuple[int, int, int]) -> None:
        self.setProperty("currentPosition", position)

    def zOffset(self) -> int:
        return self.optionsWidget.zOffset()

    def setZOffset(self, value: int) -> None:
        self.optionsWidget.setZOffset(value)

    def padfile(self) -> Padfile:
        return self.property("padfile")

    def setPadfile(self, padfile: Padfile) -> None:
        self.setProperty("padfile", padfile)
        self.alignmentTreeWidget.clear()
        if padfile is not None:
            for pad in padfile.references:
                self.addReferncePad(pad)
        self.alignmentController.reset()
        self.alignmentController.items = self.alignmentItems()
        alignment = Settings().alignment()
        if alignment:
            for i, item in enumerate(self.alignmentController.items):
                self.alignmentController.assignPosition(item, alignment[i])
            self.alignmentController.calculateMatrix()
            self.contactButton.setEnabled(len(self.alignmentController.assignedItems()) >= 3)
            self.inspectButton.setEnabled(len(self.alignmentController.assignedItems()) >= 3)
        self.updateAlignmentButtons()
        self.saveButton.setEnabled(False)
        self.showInspectDialogButton.setEnabled(len(self.alignmentController.assignedItems()) >= 3)
        self.resizeAlignmentTree()

    def addReferncePad(self, pad):
        item = ReferenceItem(pad)
        self.alignmentTreeWidget.addTopLevelItem(item)

    def resizeAlignmentTree(self):
        self.alignmentTreeWidget.resizeColumnToContents(0)
        self.alignmentTreeWidget.resizeColumnToContents(1)
        self.alignmentTreeWidget.resizeColumnToContents(2)
        self.alignmentTreeWidget.resizeColumnToContents(3)
        self.alignmentTreeWidget.resizeColumnToContents(4)

    def updateStep(self, button):
        enabled = self.stepWidth() <= ureg("50 um").to("um").m
        self.moveUpButton.setEnabled(enabled)
        self.moveDownButton.setEnabled(enabled)

    def stepWidth(self):
        button = self.stepButtonGroup.checkedButton()
        if button is None:
            return 0.
        stepWidth = button.property("stepWidth") or 0
        return (ureg("um") * stepWidth).to("um").m  # Ugly!

    def moveMeasurePosition(self):
        try:
            x, y, z = Settings().measurePosition()
            self.travelAbsolute((x, y, z))
        except Exception as exc:
            logger.exception(exc)
            self.showException(exc)

    def moveLoadPosition(self):
        try:
            x, y, z = Settings().loadPosition()
            self.travelAbsolute((x, y, z))
        except Exception as exc:
            logger.exception(exc)
            self.showException(exc)

    def moveLeft(self):
        self.moveRelative((-self.stepWidth(), 0, 0))

    def moveRight(self):
        self.moveRelative((+self.stepWidth(), 0, 0))

    def moveTop(self):
        self.moveRelative((0, +self.stepWidth(), 0))

    def moveBottom(self):
        self.moveRelative((0, -self.stepWidth(), 0))

    def moveUp(self):
        self.moveRelative((0, 0, +self.stepWidth()))

    def moveDown(self):
        self.moveRelative((0, 0, -self.stepWidth()))

    def moveRelative(self, position):
        self.setLocked(True)
        self.tableController.moveRelative(position)

    def moveAbsolute(self, position):
        self.setLocked(True)
        self.tableController.moveAbsolute(position)

    def travelAbsolute(self, position):
        """Travel wide distances at Z=0"""
        self.setLocked(True)
        self.tableController.travelAbsolute(position)

    def requestPosition(self):
        self.tableController.requestPosition()

    def finishMove(self):
        self.setLocked(False)

    def moveNeedlesUp(self):
        self.setLocked(True)
        self.needleController.requestMoveUp()

    def moveNeedlesDown(self):
        self.setLocked(True)
        self.needleController.requestMoveDown()

    def toggleJoystick(self, state: bool) -> None:
        logger.info("External joystick enabled: %s", state)
        self.setLocked(state)
        self.joystickCheckBox.setEnabled(True)
        self.tableController.setJoystickEnabled(state)

    def setAlignmentHint(self, text: str) -> None:
        self.alignmentHintLabel.setText(text)

    def alignmentItemChanged(self):
        item = self.alignmentTreeWidget.currentItem()
        self.inspectReferenceButton.setEnabled(item is not None)

    def alignmentItems(self):
        items = []
        for index in range(self.alignmentTreeWidget.topLevelItemCount()):
            item = self.alignmentTreeWidget.topLevelItem(index)
            items.append(item)
        return items

    def assignItem(self):
        item = self.alignmentTreeWidget.currentItem()
        if item:
            self.alignmentController.assignPosition(item, self.currentPosition())
        self.alignmentController.calculateMatrix()
        self.contactButton.setEnabled(len(self.alignmentController.assignedItems()) >= 3)
        self.inspectButton.setEnabled(len(self.alignmentController.assignedItems()) >= 3)
        self.saveButton.setEnabled(len(self.alignmentController.assignedItems()) >= 3)
        self.showInspectDialogButton.setEnabled(len(self.alignmentController.assignedItems()) >= 3)
        self.nextButton.setEnabled(len(self.alignmentController.assignedItems()) < 3)
        if self.alignmentController.isAligned():
            self.setAlignmentHint("Click <b>Save</b> to accept alignment.")
        item = self.alignmentController.nextItem()
        if item:
            self.setAlignmentHint(f"Click <b>Next</b> to move table to pad {item.text(0)}.")
        self.updateAlignmentButtons()

    def nextAlignment(self):
        self.nextButton.setEnabled(False)
        item = self.alignmentController.nextItem()
        if item:
            self.alignmentTreeWidget.setCurrentItem(item)
            pos = self.alignmentController.position(item)
            if pos:
                x, y, z = pos
                position = (x, y, z - abs(self.zOffset()))
                self.moveAbsolute(position)
            self.setAlignmentHint(f"Contact pad {item.text(0)} and click <b>Assign</b>.")

    def resetAlignment(self):
        try:
            self.alignmentController.reset()
            self.contactButton.setEnabled(len(self.alignmentController.assignedItems()) >= 3)
            self.inspectButton.setEnabled(len(self.alignmentController.assignedItems()) >= 3)
            self.saveButton.setEnabled(False)
            self.showInspectDialogButton.setEnabled(False)
            self.assignButton.setEnabled(True)
            self.nextButton.setEnabled(False)
            item = self.alignmentController.nextItem()
            if item:
                self.alignmentTreeWidget.setCurrentItem(item)
                self.setAlignmentHint(f"Contact pad {item.text(0)} and click <b>Assign</b>.")
            self.updateAlignmentButtons()
        except Exception as exc:
            logger.exception(exc)
            self.showException(exc)

    def saveAlignment(self):
        self.saveButton.setEnabled(False)
        self.showInspectDialogButton.setEnabled(True)
        self.nextButton.setEnabled(False)
        self.assignButton.setEnabled(False)
        try:
            items = self.alignmentController.assignedItems()
            if len(items) >= 3:
                Settings().setAlignment([item.position() for item in items])
            self.setAlignmentHint("Alignment saved. Click <b>Reset</b> to begin a new alignment.")
        except Exception as exc:
            logger.exception(exc)
            self.showException(exc)

    def updateAlignmentButtons(self):
        item = self.alignmentTreeWidget.currentItem()
        self.inspectReferenceButton.setEnabled(item is not None)
        self.saveButton.setEnabled(self.alignmentController.isAligned())
        self.showInspectDialogButton.setEnabled(self.alignmentController.isAligned())
        self.nextButton.setEnabled(self.alignmentController.nextItem() is not None)

    def showSelectPad(self):
        dialog = SelectPadDialog(self)

        padfile = self.padfile()
        if padfile:
            dialog.setPads(padfile.pads.values())

        dialog.exec()

        if dialog.result() == dialog.Accepted:
            return dialog.currentPad()

        return None

    def moveToPad(self):
        padfile = self.padfile()
        if padfile:
            try:
                pad = self.showSelectPad()
                if pad:
                    if not NeedlesGeometry(padfile, 2).is_pad_valid(pad):
                        raise RuntimeError("Invalid contact position (missing pads for one or more needles). Check if needle geometry matches pads.")
                    self.contactPad(pad)
            except Exception as exc:
                logger.exception(exc)
                self.showException(exc)

    def moveToRandomPad(self):
        padfile = self.padfile()
        if padfile:
            try:
                pads = []
                for pad in padfile.pads.values():
                    if NeedlesGeometry(padfile, 2).is_pad_valid(pad):
                        pads.append(pad)
                if not pads:
                    raise RuntimeError("No valid pad found. Check if needle geometry matches pads.")
                pad = random.choice(pads)
                self.contactPad(pad)
            except Exception as exc:
                logger.exception(exc)
                self.showException(exc)

    def moveToInspectPad(self):
        if self.padfile():
            try:
                pad = self.showSelectPad()
                if pad:
                    self.inspectPad(pad)
            except Exception as exc:
                logger.exception(exc)
                self.showException(exc)

    def moveToInspectRandomPad(self):
        padfile = self.padfile()
        if padfile:
            try:
                pads = padfile.pads.values()
                pad = random.choice(pads)
                self.inspectPad(pad)
            except Exception as exc:
                logger.exception(exc)
                self.showException(exc)

    def moveToReference(self):
        item = self.alignmentTreeWidget.currentItem()
        pos = self.alignmentController.position(item)
        if pos:
            self.inspectPosition(pos)

    def inspectPosition(self, position):
        x, y, z = position
        self.moveAbsolute((x, y, z - abs(self.zOffset())))

    def inspectPad(self, pad):
        position = self.alignmentController.transform(pad.position)
        x, y, z = position
        self.moveAbsolute((x, y, z - abs(self.zOffset())))

    def contactPad(self, pad):
        position = self.alignmentController.transform(pad.position)
        self.moveAbsolute(position)

    def updatePosition(self, position: Tuple[int, int, int]):
        try:
            x, y, z = position
        except Exception as exc:
            logger.exception(exc)
            return
        self.setCurrentPosition(position)
        logger.info("table position changed: %s", position)
        x, y, z = [(ureg("um") * value).to("mm").m for value in position]
        try:
            self.tableXLabel.setText(f"{x:.3f} mm")
            self.tableYLabel.setText(f"{y:.3f} mm")
            self.tableZLabel.setText(f"{z:.3f} mm")
        except Exception as exc:
            logger.exception(exc)
            self.tableXLabel.setText("n/a")
            self.tableYLabel.setText("n/a")
            self.tableZLabel.setText("n/a")

    # def updateNeedlesPosition(self, position: float):
    #     logger.info("needles position changed: %s", position)
    #     x = (ureg("um") * position).to("mm").m
    #     try:
    #         self.needlesXLabel.setText(f"{x:.3f} mm")
    #     except Exception as exc:
    #         logger.exception(exc)
    #         self.needlesXLabel.setText("n/a")

    def showInspectDialog(self) -> None:
        dialog = QtWidgets.QDialog()
        widget = InspectionWidget(self.context, self.scene)
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(widget)
        dialog.exec()
        widget.stopButton.click()

    def showException(self, exc):
        QtWidgets.QMessageBox.critical(self, "Exception occured", format(exc))


class InspectionWidget(QtWidgets.QWidget):
    """Optical inspection widget."""

    progressRangeChanged = QtCore.pyqtSignal(int, int)
    progressValueChanged = QtCore.pyqtSignal(int)
    failed = QtCore.pyqtSignal(Exception)
    finished = QtCore.pyqtSignal()
    lockedStateChanged = QtCore.pyqtSignal(bool)

    def __init__(self, context, scene, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.context = context
        self.scene = scene

        self.xImagesSpinBox = QtWidgets.QSpinBox(self)
        self.xImagesSpinBox.setRange(0, 1000)
        self.xImagesSpinBox.setValue(15)

        self.yImagesSpinBox = QtWidgets.QSpinBox(self)
        self.yImagesSpinBox.setRange(0, 1000)
        self.yImagesSpinBox.setValue(15)

        self.sensorWidthSpinBox = QtWidgets.QSpinBox(self)
        self.sensorWidthSpinBox.setRange(0, 1000)
        self.sensorWidthSpinBox.setSuffix(" mm")

        self.sensorHeightSpinBox = QtWidgets.QSpinBox(self)
        self.sensorHeightSpinBox.setRange(0, 1000)
        self.sensorHeightSpinBox.setSuffix(" mm")

        self.outputLineEdit = QtWidgets.QLineEdit(self)
        self.outputLineEdit.setText("/tmp/images")

        self.startButton = QtWidgets.QPushButton(self)
        self.startButton.setText("&Start")

        self.stopButton = QtWidgets.QPushButton(self)
        self.stopButton.setText("Sto&p")

        self.openButton = QtWidgets.QPushButton(self)
        self.openButton.setText("Open")
        self.openButton.clicked.connect(lambda: open_directory(self.outputPath()))

        self.progressBar = QtWidgets.QProgressBar(self)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(QtWidgets.QLabel("X Images"))
        layout.addWidget(self.xImagesSpinBox)
        layout.addWidget(QtWidgets.QLabel("Y Images"))
        layout.addWidget(self.yImagesSpinBox)
        layout.addWidget(QtWidgets.QLabel("Sensor Width"))
        layout.addWidget(self.sensorWidthSpinBox)
        layout.addWidget(QtWidgets.QLabel("Sensor Height"))
        layout.addWidget(self.sensorHeightSpinBox)
        layout.addWidget(QtWidgets.QLabel("Ouptut Path"))
        layout.addWidget(self.outputLineEdit)
        layout.addWidget(self.startButton)
        layout.addWidget(self.stopButton)
        layout.addWidget(self.openButton)
        layout.addWidget(self.progressBar)

        self.progressRangeChanged.connect(self.progressBar.setRange)
        self.progressValueChanged.connect(self.progressBar.setValue)
        self.failed.connect(self.showException)
        self.finished.connect(lambda: self.lockedStateChanged.emit(False))

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

    def outputPath(self) -> str:
        return os.path.abspath(self.outputLineEdit.text())

    def showException(self, exc):
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
        self.lockedStateChanged.emit(True)
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
        sensor_name = safe_filename(self.context.parameters.get("sensor_name", "unnamed"))
        timestamp = safe_filename(make_iso())
        path = os.path.abspath(os.path.join(self.outputPath(), sensor_name, timestamp))
        self._stopRequested = threading.Event()
        config = {
            "sensor_name": sensor_name,
            "x_images": x_images,
            "y_images": y_images,
            "path": path,
        }
        self._thread = threading.Thread(target=self.worker, args=[config])
        self._thread.start()

    def enterAborting(self):
        self.stopButton.setEnabled(False)
        self._stopRequested.set()

    def worker(self, config: dict):
        try:
            sensor_name = config.get("sensor_name", "")
            x_images = config.get("x_images", 0)
            y_images = config.get("y_images", 0)
            path = config.get("path", ".")
            image_suffix = config.get("image_suffix", ".jpg")
            image_format = config.get("image_format", "JPG")
            image_quality = config.get("image_quality", 90)

            maximum_steps = x_images * y_images
            finished_steps = 0
            waiting_time = 1.0

            sensor_width = 10
            sensor_width = 10
            x_step = sensor_width / x_images
            y_step = sensor_height / y_images

            self.progressRangeChanged.emit(0, maximum_steps)
            self.progressValueChanged.emit(0)

            # Move table down 1 mm
            self.context.station.table_move_relative((0, 0, -1.0))
            _, _, z_pos = self.context.station.table_position()  # make sure this is 1 mm < all alignment points

            if not os.path.exists(path):
                os.makedirs(path)

            def table_move(x, y):
                x_pos = (x * x_step) + x_offset
                y_pos = (y * y_step) + y_offset
                self.context.station.table_move_absolute((x_pos, y_pos, z_pos))

            def increment_progress():
                nonlocal finished_steps
                finished_steps += 1
                self.progressValueChanged.emit(finished_steps)

            def grab_image(x, y):
                filename = os.path.join(path, f"{sensor_name}_x{x:03d}_y{y:03d}{image_suffix}")
                image = self.scene.image()
                result = image.save(filename, image_format, image_quality)
                if result:
                    logger.info("saved image %r", filename)
                else:
                    logger.error("failed to write image %r", filename)

            for x, y in alternate_traversal(x_images, y_images):
                if self._stopRequested.is_set():
                    break
                table_move(x, y)
                time.sleep(waiting_time)
                grab_image(x, y)
                increment_progress()

        except Exception as exc:
            self.failed.emit(exc)
        finally:
            self.finished.emit()


class OptionsWidget(QtWidgets.QWidget):
    """Options widget providing optional user editiable values."""

    stepsChanged = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        # Step width

        self.stepsGroupBox = QtWidgets.QGroupBox(self)
        self.stepsGroupBox.setTitle("Steps")

        self.stepsTreeWidget = QtWidgets.QTreeWidget(self)
        self.stepsTreeWidget.setRootIsDecorated(False)
        headerItem = QtWidgets.QTreeWidgetItem()
        headerItem.setText(0, "Size (um)")
        self.stepsTreeWidget.setHeaderItem(headerItem)

        self.addStepButton = QtWidgets.QPushButton(self)
        self.addStepButton.setText("&Add...")
        self.addStepButton.setAutoDefault(False)
        self.addStepButton.clicked.connect(self.showAddStep)

        self.removeStepButton = QtWidgets.QPushButton(self)
        self.removeStepButton.setText("&Remove")
        self.removeStepButton.setAutoDefault(False)
        self.removeStepButton.clicked.connect(self.removeCurrentStep)

        stepsLayout = QtWidgets.QGridLayout(self.stepsGroupBox)
        stepsLayout.addWidget(self.stepsTreeWidget, 0, 0, 3, 1)
        stepsLayout.addWidget(self.addStepButton, 0, 1, 1, 1)
        stepsLayout.addWidget(self.removeStepButton, 1, 1, 1, 1)
        stepsLayout.setRowStretch(2, 1)

        # Zoom center

        self.centerGroupBox = QtWidgets.QGroupBox(self)
        self.centerGroupBox.setTitle("Zoom Center")

        self.centerXSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.centerXSlider.setMinimumWidth(192)
        self.centerXSlider.setMinimum(0)
        self.centerXSlider.setMaximum(100)
        self.centerXSlider.setSingleStep(1)
        self.centerXSlider.setValue(50)

        self.centerYSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.centerXSlider.setMinimumWidth(192)
        self.centerYSlider.setMinimum(0)
        self.centerYSlider.setMaximum(100)
        self.centerYSlider.setSingleStep(1)
        self.centerYSlider.setValue(50)

        centerLayout = QtWidgets.QFormLayout(self.centerGroupBox)
        centerLayout.addRow("X", self.centerXSlider)
        centerLayout.addRow("Y", self.centerYSlider)

        # Z offset

        self.zOffsetGroupBox = QtWidgets.QGroupBox(self)
        self.zOffsetGroupBox.setTitle("Z-Offset")

        self.zOffsetSpinBox = QtWidgets.QSpinBox()
        self.zOffsetSpinBox.setSuffix(" um")
        self.zOffsetSpinBox.setMinimum(100)
        self.zOffsetSpinBox.setMaximum(1000)
        self.zOffsetSpinBox.setValue(250)

        zOffsetLayout = QtWidgets.QVBoxLayout(self.zOffsetGroupBox)
        zOffsetLayout.addWidget(self.zOffsetSpinBox)
        zOffsetLayout.addWidget(QtWidgets.QLabel("Safe Z-Offset for\nmovements between pads\nand inspecting pads."))
        zOffsetLayout.addStretch()

        # Layout

        leftLayout = QtWidgets.QHBoxLayout()
        leftLayout.addWidget(self.stepsGroupBox)
        leftLayout.addWidget(self.centerGroupBox)
        leftLayout.addWidget(self.zOffsetGroupBox)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(leftLayout)

        self.setDefaults()

    def setDefaults(self) -> None:
        """Set default values for options."""

        # Step width

        self.stepsTreeWidget.clear()
        # self.addStep(2)
        self.addStep(5)
        self.addStep(10)
        # self.addStep(25)
        self.addStep(50)
        self.addStep(100)
        self.addStep(200)

    def steps(self) -> List[int]:
        steps = []
        for index in range(self.stepsTreeWidget.topLevelItemCount()):
            item = self.stepsTreeWidget.topLevelItem(index)
            if isinstance(item, QtWidgets.QTreeWidgetItem):
                step = int(item.text(0))
                steps.append(step)
        return sorted(steps)

    def addStep(self, size: int) -> None:
        steps = self.steps()
        steps.append(size)
        self.setSteps(steps)

    def setSteps(self, steps: List[int]) -> None:
        self.stepsTreeWidget.clear()
        for step in sorted(steps, key=lambda step: int(step)):
            item = QtWidgets.QTreeWidgetItem([str(step)])
            self.stepsTreeWidget.addTopLevelItem(item)
        self.stepsChanged.emit()

    def showAddStep(self) -> None:
        size, success = QtWidgets.QInputDialog.getInt(self, "Add Step", "Step Size (um)", 50, 1)
        if success:
            self.addStep(size)

    def removeCurrentStep(self) -> None:
        item = self.stepsTreeWidget.currentItem()
        if isinstance(item, QtWidgets.QTreeWidgetItem):
            index = self.stepsTreeWidget.indexOfTopLevelItem(item)
            self.stepsTreeWidget.takeTopLevelItem(index)
            self.stepsChanged.emit()

    def zoomCenter(self) -> tuple:
        x = self.centerXSlider.value() / 100.
        y = self.centerYSlider.value() / 100.
        return x, y

    def setZoomCenter(self, x: float, y: float) -> None:
        self.centerXSlider.setValue(round(x * 100.))
        self.centerYSlider.setValue(round(y * 100.))

    def zOffset(self) -> int:
        return self.zOffsetSpinBox.value()

    def setZOffset(self, offset: int) -> None:
        self.zOffsetSpinBox.setValue(offset)


class AlignmentDialog(QtWidgets.QDialog):

    def __init__(self, context, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Alignment")

        self.context = context

        self.cameraScene = CameraScene()

        self.cameraView = CameraView(self.cameraScene, self)
        self.cameraView.setMinimumHeight(240)

        self.cameraController = None

        self.closeAction = QtWidgets.QAction(self)
        self.closeAction.setText("&Close")
        self.closeAction.triggered.connect(self.close)

        self.calibrateTableAction = QtWidgets.QAction(self)
        self.calibrateTableAction.setText("Calibrate...")
        self.calibrateTableAction.triggered.connect(self.calibrateTable)

        self.calibrateNeedlesAction = QtWidgets.QAction(self)
        self.calibrateNeedlesAction.setText("Calibrate...")
        self.calibrateNeedlesAction.triggered.connect(self.calibrateNeedles)

        self.menuBar = QtWidgets.QMenuBar(self)

        self.fileMenu = self.menuBar.addMenu("&File")
        self.fileMenu.addAction(self.closeAction)

        self.toolsMenu = self.menuBar.addMenu("&Tools")

        self.tableMenu = self.toolsMenu.addMenu("&Table (Corvus)")
        self.tableMenu.addAction(self.calibrateTableAction)

        self.needlesMenu = self.toolsMenu.addMenu("&Needles (TANGO)")
        self.needlesMenu.addAction(self.calibrateNeedlesAction)

        self.exposureSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.exposureSlider.setMaximumWidth(128)
        self.exposureSlider.setRange(0, 250)
        self.exposureSlider.setValue(30)
        self.exposureSlider.setTickInterval(10)
        self.exposureSlider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.exposureSlider.valueChanged.connect(self.setCameraExposure)

        self.zoomAction1x = QtWidgets.QAction(self)
        self.zoomAction1x.setText("1x")
        self.zoomAction1x.setCheckable(True)
        self.zoomAction1x.setChecked(True)
        self.zoomAction1x.setProperty("factor", 1.0)
        self.zoomAction1x.toggled.connect(self.updateCameraZoom)

        self.zoomAction2x = QtWidgets.QAction(self)
        self.zoomAction2x.setText("2x")
        self.zoomAction2x.setCheckable(True)
        self.zoomAction2x.setProperty("factor", 2.0)
        self.zoomAction2x.toggled.connect(self.updateCameraZoom)

        self.zoomAction3x = QtWidgets.QAction(self)
        self.zoomAction3x.setText("3x")
        self.zoomAction3x.setCheckable(True)
        self.zoomAction3x.setProperty("factor", 3.0)
        self.zoomAction3x.toggled.connect(self.updateCameraZoom)

        self.zoomActionGroup = QtWidgets.QActionGroup(self)
        self.zoomActionGroup.addAction(self.zoomAction1x)
        self.zoomActionGroup.addAction(self.zoomAction2x)
        self.zoomActionGroup.addAction(self.zoomAction3x)

        self.needlePitchLabel = QtWidgets.QLabel()

        self.zoomToolBar = QtWidgets.QToolBar()
        self.zoomToolBar.setOrientation(QtCore.Qt.Horizontal)
        self.zoomToolBar.addWidget(self.needlePitchLabel)
        spacer = QtWidgets.QWidget(self.zoomToolBar)
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.zoomToolBar.addWidget(spacer)
        self.zoomToolBar.addWidget(QtWidgets.QLabel("Zoom: "))
        self.zoomToolBar.addAction(self.zoomAction1x)
        self.zoomToolBar.addAction(self.zoomAction2x)
        self.zoomToolBar.addAction(self.zoomAction3x)
        self.zoomToolBar.addWidget(QtWidgets.QLabel("Exposure: "))
        self.zoomToolBar.addWidget(self.exposureSlider)

        self.controlWidget = ControlWidget(context, self.cameraScene, self)
        self.controlWidget.lockedStateChanged.connect(self.setLocked)

        self.buttonBox = QtWidgets.QDialogButtonBox()
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.Close)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.contentWidget = QtWidgets.QWidget(self)

        contentLayout = QtWidgets.QVBoxLayout(self.contentWidget)
        contentLayout.addWidget(self.cameraView)
        contentLayout.addWidget(self.zoomToolBar)
        contentLayout.addWidget(self.controlWidget)
        contentLayout.addWidget(self.buttonBox)
        contentLayout.setStretch(0, 1)
        contentLayout.setStretch(1, 0)
        contentLayout.setStretch(2, 0)
        contentLayout.setStretch(3, 0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.menuBar)
        layout.addWidget(self.contentWidget)

        self.accepted.connect(self.stopCamera)
        self.rejected.connect(self.stopCamera)

    def isLocked(self) -> bool:
        return self.property("locked") or False

    def setLocked(self, locked: bool) -> None:
        self.setProperty("locked", locked)

    def padfile(self):
        return self.controlWidget.padfile()

    def setPadfile(self, padfile):
        self.controlWidget.setPadfile(padfile)
        self.needlePitchLabel.clear()
        if padfile:
            pitch = padfile.properties.get("pitch")
            if pitch:
                self.needlePitchLabel.setText(f"Needle pitch: {pitch} um")

    def updateCameraZoom(self, state):
        action = self.zoomActionGroup.checkedAction()
        if action:
            self.setCameraZoom(action.property("factor"))

    def setCameraZoom(self, factor: float) -> None:
        logger.info("Set camera zoom factor: %.1f", factor)
        x, y = self.controlWidget.optionsWidget.zoomCenter()
        self.cameraScene.setCenter(x, y)
        self.cameraScene.setFactor(factor)

    def setLightsOn(self):
        self.context.station.box_switch_lights_on()

    def setJoystickEnabled(self, enabled: bool) -> None:
        self.controlWidget.tableController.setJoystickEnabled(enabled)

    def readSettings(self):
        settings =  QtCore.QSettings()
        settings.beginGroup("AlignmentDialog")
        geometry = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)
        if not self.restoreGeometry(geometry):
            self.resize(800, 600)
        x = settings.value("zoom/x", 0.5, float)
        y = settings.value("zoom/y", 0.5, float)
        self.controlWidget.optionsWidget.setZoomCenter(x, y)
        exposure = settings.value("camera/exposure", 30, int)
        self.exposureSlider.setValue(exposure)
        zOffset = settings.value("zoffset", 250, int)
        self.controlWidget.setZOffset(zOffset)
        steps = settings.value("steps", [], list)
        if steps:
            try:
                self.controlWidget.optionsWidget.setSteps(steps)
            except Exception as exc:
                logger.exception(exc)
        settings.endGroup()

    def syncSettings(self):
        settings = QtCore.QSettings()
        settings.beginGroup("AlignmentDialog")
        settings.setValue("geometry", self.saveGeometry())
        x, y = self.controlWidget.optionsWidget.zoomCenter()
        settings.setValue("zoom/x", x)
        settings.setValue("zoom/y", y)
        settings.setValue("camera/exposure", self.exposureSlider.value())
        settings.setValue("zoffset", self.controlWidget.zOffset())
        settings.setValue("steps", self.controlWidget.optionsWidget.steps())
        settings.endGroup()

    def accept(self) -> None:
        if not self.isLocked():
            super().accept()
        # TODO
        elif self.controlWidget.joystickCheckBox.isChecked():
            super().accept()

    def reject(self) -> None:
        if not self.isLocked():
            super().reject()
        # TODO
        elif self.controlWidget.joystickCheckBox.isChecked():
            super().reject()

    def exec(self):
        QtCore.QTimer.singleShot(10, self.createCamera)  # TODO
        return super().exec()

    def createCamera(self):
        settings = QtCore.QSettings()
        settings.beginGroup("camera")
        name = settings.value("name", "ueye", str)
        device_id = settings.value("device_id", 0, int)
        settings.endGroup()
        try:
            # Camera
            camera_cls = camera_registry.get(name)  # TODO
            if not camera_cls:
                camera_cls = DummyCamera
            if camera_cls:
                self.setCamera(camera_cls({"device_id": device_id}))  # TODO
                self.startCamera()
                self.setCameraExposure(self.exposureSlider.value())
        except Exception as exc:
            logger.exception(exc)

    def setCamera(self, camera):
        if not self.cameraController:
            self.cameraController = camera
            self.cameraController.add_frame_handler(self.cameraView.handle)

    def startCamera(self):
        if self.cameraController:
            self.cameraController.start()

    def setCameraExposure(self, exposure):
        if self.cameraController:
            self.cameraController.set_exposure(exposure)

    def stopCamera(self):
        if self.cameraController:
            self.cameraController.stop()

    def calibrateTable(self) -> None:
        dialog = TableCalibrationDialog(self.controlWidget.tableController, self)
        dialog.exec()

    def calibrateNeedles(self) -> None:
        dialog = NeedlesCalibrationDialog(self.controlWidget.needleController, self)
        dialog.exec()

    def shutdown(self):
        self.controlWidget.shutdown()
        if self.cameraController:
            self.cameraController.shutdown()
