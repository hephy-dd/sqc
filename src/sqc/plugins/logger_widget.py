import logging
import threading
import os
from typing import Callable, Iterable, List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

__all__ = ["LoggerWidgetPlugin"]


class LoggerWidgetPlugin:

    def install(self, window) -> None:
        self.window = window

        self.loggerWidget = QueuedLoggerWidget()
        self.loggerWidget.addLogger(logging.getLogger())

        self.openAction = QtWidgets.QAction()
        self.openAction.setText("&Open Logfile")
        self.openAction.setIcon(QtGui.QIcon.fromTheme("icons:open-logfile.svg"))
        self.openAction.setStatusTip("Open current Logfile in default Text Editor.")
        self.openAction.triggered.connect(self.openCurrentLogile)

        self.toolBar = QtWidgets.QToolBar()
        self.toolBar.setOrientation(QtCore.Qt.Vertical)
        self.toolBar.addAction(self.openAction)

        self.widget = QtWidgets.QWidget()

        layout = QtWidgets.QGridLayout(self.widget)
        layout.addWidget(self.loggerWidget, 0, 0)
        layout.addWidget(self.toolBar, 0, 1)
        layout.setColumnStretch(0, 1)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(0)

        self.loggerDockWidget = QtWidgets.QDockWidget()
        self.loggerDockWidget.setObjectName("logger")
        self.loggerDockWidget.setWindowTitle("Logger")
        self.loggerDockWidget.setFloating(False)
        self.loggerDockWidget.setFeatures(QtWidgets.QDockWidget.DockWidgetClosable)
        self.loggerDockWidget.setWidget(self.widget)
        window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.loggerDockWidget)

        self.loggerAction = self.loggerDockWidget.toggleViewAction()
        self.loggerAction.setIcon(QtGui.QIcon("icons:view-logger.svg"))
        self.loggerAction.setChecked(False)

        window.viewMenu.addAction(self.loggerAction)

    def uninstall(self, window) -> None:
        self.loggerWidget.removeLogger(logging.getLogger())
        window.removeDockWidget(self.loggerDockWidget)
        window.viewMenu.removeAction(self.loggerAction)

    def openCurrentLogile(self) -> None:
        filename = self.window.context.parameters.get("logfile")
        if filename:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(filename))


class Handler(logging.Handler):

    def __init__(self, callback: Callable) -> None:
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        self.callback(record)


class LoggerWidget(QtWidgets.QTextEdit):

    MaximumEntries: int = 1024 * 1024
    """Maximum number of visible log entries."""

    received = QtCore.pyqtSignal(logging.LogRecord)
    """Received is emitted when a new log record is appended by a logger."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(type(self).MaximumEntries)

        self.handler = Handler(self.received.emit)
        self.setLevel(logging.INFO)
        self.received.connect(self.appendRecord)

        self.recordFormats = {}

        errorFormat = QtGui.QTextCharFormat()
        errorFormat.setForeground(QtGui.QColor("red"))
        self.recordFormats[logging.ERROR] = errorFormat

        warningFormat = QtGui.QTextCharFormat()
        warningFormat.setForeground(QtGui.QColor("orange"))
        self.recordFormats[logging.WARNING] = warningFormat

        infoFormat = QtGui.QTextCharFormat()
        infoFormat.setForeground(QtGui.QColor())
        self.recordFormats[logging.INFO] = infoFormat

        debugFormat = QtGui.QTextCharFormat()
        debugFormat.setForeground(QtGui.QColor("grey"))
        self.recordFormats[logging.DEBUG] = debugFormat

    def setLevel(self, level: int) -> None:
        """Set log level of widget."""
        self.handler.setLevel(level)

    def addLogger(self, logger: logging.Logger) -> None:
        """Add logger to widget."""
        logger.addHandler(self.handler)

    def removeLogger(self, logger: logging.Logger) -> None:
        """Remove logger from widget."""
        logger.removeHandler(self.handler)

    def appendRecords(self, records: Iterable[logging.LogRecord]) -> None:
        """Append log records and auto scroll to bottom."""
        # Get current scrollbar position
        scrollbar = self.verticalScrollBar()
        position = scrollbar.value()
        # Lock to current position or to bottom
        lock = position + 1 >= scrollbar.maximum()
        # Append formatted log messages
        for record in records:
            text = self.formatRecord(record)
            textCharFormat = self.recordTextCharFormat(record)
            textCursor = QtGui.QTextCursor(self.document())
            textCursor.movePosition(QtGui.QTextCursor.End)
            # Insert newline except for first entry
            if not self.textCursor().atStart():
                textCursor.insertText(os.linesep)
            textCursor.insertText(text, textCharFormat)
        # Scroll to bottom
        if lock:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(position)

    def appendRecord(self, record: logging.LogRecord) -> None:
        """Append log record and auto scroll to bottom."""
        self.appendRecords([record])

    def recordTextCharFormat(self, record: logging.LogRecord) -> QtGui.QTextCharFormat:
        """Return text character format for record."""
        for level, textCharFormat in self.recordFormats.items():
            if record.levelno >= level:
                return textCharFormat
        return QtGui.QTextCharFormat()

    def showRecentRecords(self) -> None:
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @classmethod
    def formatTime(cls, seconds: float) -> str:
        """Format timestamp for log record."""
        dt = QtCore.QDateTime.fromMSecsSinceEpoch(int(seconds * 1e3))
        return dt.toString("yyyy-MM-dd hh:mm:ss")

    @classmethod
    def formatRecord(cls, record: logging.LogRecord) -> str:
        """Format log record."""
        timestamp = cls.formatTime(record.created)
        return "{}\t{}\t{}".format(timestamp, record.levelname, record.message)


class RecordsQueue:

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.records: List[logging.LogRecord] = []

    def append(self, record: logging.LogRecord) -> None:
        with self.lock:
            self.records.append(record)

    def fetch(self) -> List[logging.LogRecord]:
        with self.lock:
            records = self.records[:]
            self.records.clear()
            return records


class QueuedLoggerWidget(LoggerWidget):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.recordsQueue = RecordsQueue()

        self.updateInterval = 250

        self.updateTimer = QtCore.QTimer(self)
        self.updateTimer.timeout.connect(self.applyQueuedRecords)
        self.updateTimer.start(self.updateInterval)

    def appendRecord(self, record: logging.LogRecord) -> None:
        """Append log record to queue."""
        self.recordsQueue.append(record)

    def applyQueuedRecords(self) -> None:
        """Append records from queue to log widget."""
        records = self.recordsQueue.fetch()
        if records:
            super().appendRecords(records)
