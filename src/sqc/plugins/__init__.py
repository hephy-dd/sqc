from .json_writer import JSONWriterPlugin
from .legacy_writer import LegacyWriterPlugin
from .ueye_camera import UEyeCameraPlugin
from .logger_widget import LoggerWidgetPlugin


def register_plugins(window) -> None:
    window.registerPlugin(JSONWriterPlugin())
    window.registerPlugin(LegacyWriterPlugin())
    window.registerPlugin(UEyeCameraPlugin())
    window.registerPlugin(LoggerWidgetPlugin())
