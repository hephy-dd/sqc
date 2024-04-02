import logging
import threading

from PyQt5 import QtCore, QtWidgets

logger = logging.getLogger(__name__)


class RecoverDialog(QtWidgets.QProgressDialog):

    started = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()
    progressRisized = QtCore.pyqtSignal(int)
    progressChanged = QtCore.pyqtSignal(int)
    textChanged = QtCore.pyqtSignal(str)

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self._locked = True
        self.context = context
        self.setWindowTitle("Recover Station")
        self.setCancelButton(None)
        self.setLabelText("Recover station instruments...")
        self.started.connect(self.exec)
        self.finished.connect(self.close)
        self.progressRisized.connect(self.setMaximum)
        self.progressChanged.connect(self.setValue)
        self.textChanged.connect(self.setLabelText)
        self.destroyed.connect(lambda: logger.debug("Deleted progress dialog."))

    def closeEvent(self, event):
        if self._locked:
            event.ignore()
        else:
            event.accept()

    def target(self):
        try:
            self.started.emit()
            self.runTasks()
        except Exception as exc:
            logger.exception(exc)
            self.context.handle_exception(exc)
        finally:
            self._locked = False
            self.finished.emit()

    def runTasks(self):
        try:
            station = self.context.station
            station.open_resources()
            tasks = [
                (station.clear_visa_bus, "Clearing VISA bus..."),
                (station.safe_recover_smu, "Recovering SMU2..."),
                (station.safe_recover_bias_smu, "Recovering bias SMU..."),
                (station.hv_switch_release, "Recovering HV switch..."),
                (station.lv_switch_release, "Recovering LV switch..."),
                (station.safe_discharge, "Discarge decoupling..."),
            ]
            self.progressRisized.emit(len(tasks))
            for index, task in enumerate(tasks):
                task, text = task
                self.textChanged.emit(text)
                task()
                self.progressChanged.emit(index + 1)
        finally:
            station.close_resources()

    def run(self):
        self._thread = threading.Thread(target=self.target)
        self._thread.start()
