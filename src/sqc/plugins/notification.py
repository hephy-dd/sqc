import logging
import json
import re
import urllib.request as request
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from PyQt5 import QtCore, QtWidgets

__all__ = ["NotificationPlugin"]

logger = logging.getLogger(__name__)


class NotificationPlugin:

    def beforePreferences(self, dialog) -> None:
        self.preferencesWidget = PreferencesWidget()
        dialog.tabWidget.addTab(self.preferencesWidget, "Notifications")
        self.preferencesWidget.readSettings()

    def afterPreferences(self, dialog) -> None:
        if dialog.result() == dialog.Accepted:
            self.preferencesWidget.writeSettings()
        index = dialog.tabWidget.indexOf(self.preferencesWidget)
        dialog.tabWidget.removeTab(index)

    def sequenceStarted(self, window) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("plugins/notification")
        enabled = settings.value("enabled", False, bool)
        template = settings.value("startedMessage", "Sequence started for {sensor_name} ({sensor_type}).", str)
        settings.endGroup()
        if enabled:
            kwargs = message_kwargs(window.context)
            message = safe_format(template, kwargs)
            publish_message(message)

    def sequenceFinished(self, window) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("plugins/notification")
        enabled = settings.value("enabled", False, bool)
        template = settings.value("finishedMessage", "Sequence finished for {sensor_name} ({sensor_type}).", str)
        settings.endGroup()
        if enabled:
            kwargs = message_kwargs(window.context)
            message = safe_format(template, kwargs)
            publish_message(message)


def message_kwargs(context) -> dict:
    parameters = deepcopy(context.parameters)
    timestamp = parameters.get("timestamp", 0)
    return {
        "sensor_name": parameters.get("sensor_name", ""),
        "sensor_type": parameters.get("sensor_type", ""),
        "operator_name": parameters.get("operator_name", ""),
        "output_path": parameters.get("output_path", ""),
        "utc_timestamp": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
        "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
    }


def safe_format(template: str, kwargs: dict) -> str:
    pattern = re.compile(r'\{(.*?)\}')

    def replacer(match):
        key = match.group(1)
        return kwargs.get(key, match.group(0))

    return pattern.sub(replacer, template)


def publish_message(message: str) -> None:
    settings = QtCore.QSettings()
    settings.beginGroup("plugins/notification")
    slack_webhook_url = settings.value("slackWebhookUrl", "", str)
    settings.endGroup()
    if slack_webhook_url and message:
        response = send_slack_message(slack_webhook_url, message)
        logger.info(response)


def send_slack_message(webhook_url: str, message: str) -> str:
    data = {"text": message}
    body = bytes(json.dumps(data), encoding="utf-8")

    req = request.Request(webhook_url, data=body, headers={"content-type": "application/json"})
    response = request.urlopen(req)

    return response.read().decode("utf8")


class PreferencesWidget(QtWidgets.QWidget):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.enabledCheckBox = QtWidgets.QCheckBox(self)
        self.enabledCheckBox.setText("Enabled")

        self.webhookUrlLabel = QtWidgets.QLabel(self)
        self.webhookUrlLabel.setText("Slack Webhook URL")

        self.webhookUrlLineEdit = QtWidgets.QLineEdit(self)

        self.startedLabel = QtWidgets.QLabel(self)
        self.startedLabel.setText("Message on sequence started")

        self.startedTextEdit = QtWidgets.QTextEdit(self)

        self.finishedLabel = QtWidgets.QLabel(self)
        self.finishedLabel.setText("Message on sequence finished")

        self.finishedTextEdit = QtWidgets.QTextEdit(self)

        self.infoLabel = QtWidgets.QLabel()
        self.infoLabel.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.infoLabel.setWordWrap(True)
        self.infoLabel.setText("Placeholders: {sensor_name}, {sensor_type}, {operator_name}, {output_path}, {utc_timestamp}, {timestamp}.")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.enabledCheckBox)
        layout.addWidget(self.webhookUrlLabel)
        layout.addWidget(self.webhookUrlLineEdit)
        layout.addWidget(self.startedLabel)
        layout.addWidget(self.startedTextEdit)
        layout.addWidget(self.finishedLabel)
        layout.addWidget(self.finishedTextEdit)
        layout.addWidget(self.infoLabel)
        layout.addStretch(1)

    def readSettings(self):
        settings = QtCore.QSettings()
        settings.beginGroup("plugins/notification")
        enabled = settings.value("enabled", False, bool)
        slack_webhook_url = settings.value("slackWebhookUrl", "", str)
        started_message = settings.value("startedMessage", "", str)
        finished_message = settings.value("finishedMessage", "", str)
        settings.endGroup()
        self.enabledCheckBox.setChecked(enabled)
        self.webhookUrlLineEdit.setText(slack_webhook_url)
        self.startedTextEdit.setPlainText(started_message)
        self.finishedTextEdit.setPlainText(finished_message)

    def writeSettings(self):
        enabled = self.enabledCheckBox.isChecked()
        slack_webhook_url = self.webhookUrlLineEdit.text()
        started_message = self.startedTextEdit.toPlainText()
        finished_message = self.finishedTextEdit.toPlainText()
        settings = QtCore.QSettings()
        settings.beginGroup("plugins/notification")
        settings.setValue("enabled", enabled)
        settings.setValue("slackWebhookUrl", slack_webhook_url)
        settings.setValue("startedMessage", started_message)
        settings.setValue("finishedMessage", finished_message)
        settings.endGroup()
