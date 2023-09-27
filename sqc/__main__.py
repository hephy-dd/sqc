import argparse
import logging
import os
import sys
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler
from typing import List, Type, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from . import __version__
from .context import Context
from .station import Station

from .view.mainwindow import MainWindow

from .plugins import Plugin
from .plugins.json_writer import JSONWriterPlugin
from .plugins.legacy_writer import LegacyWriterPlugin
from .plugins.ueye_camera import UEyeCameraPlugin

__all__ = ["main"]

PACKAGE_PATH: str = os.path.dirname(__file__)
ASSETS_PATH: str = os.path.join(PACKAGE_PATH, "assets")
LOG_FILENAME: str = os.path.expanduser("~/sqc.log")
CONTENTS_URL: str = "https://github.com/hephy-dd/sqc"

ENABLED_PLUGINS: List[Type[Plugin]] = [
    JSONWriterPlugin,
    LegacyWriterPlugin,
    UEyeCameraPlugin
]

logger = logging.getLogger()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="sqc", description="Sensor Quality Control (SQC) for CMS Outer Tracker.")
    parser.add_argument('--debug-no-table', action='store_true', help="disable sequence table movements")
    parser.add_argument('--debug-no-tango', action='store_true', help="disable sequence tango movements")
    parser.add_argument('--debug', action='store_true', help="show debug messages")
    parser.add_argument('--logfile', metavar="<file>", default=LOG_FILENAME, help="write to custom logfile")
    parser.add_argument('--hidpi', action='store_true', help="run in HiDPI mode")
    parser.add_argument('--version', action='version', version=f"%(prog)s {__version__}")
    return parser.parse_args()


def add_stream_handler(logger: logging.Logger) -> None:
    formatter = Formatter(
        "%(asctime)s::%(name)s::%(levelname)s::%(message)s",
        "%Y-%m-%dT%H:%M:%S"
    )
    handler = StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def add_rotating_file_handle(logger: logging.Logger, filename: str) -> None:
    file_formatter = logging.Formatter(
        fmt='%(asctime)s:%(name)s:%(levelname)s:%(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    file_handler = RotatingFileHandler(
        filename=filename,
        maxBytes=10485760,
        backupCount=10
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)


def configure_logger(logger: logging.Logger, debug: bool = False, filename: Optional[str] = None) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)

    add_stream_handler(logger)

    if filename:
        add_rotating_file_handle(logger, filename)


def main() -> None:
    args = parse_args()

    configure_logger(logger, debug=args.debug, filename=args.logfile)

    QtCore.QDir.addSearchPath("icons", os.path.join(ASSETS_PATH, "icons"))

    # Enable HiDPI support
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, args.hidpi)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("sqc")
    app.setApplicationVersion(__version__)
    app.setApplicationDisplayName(f"SQC {__version__}")
    app.setOrganizationName("HEPHY")
    app.setOrganizationDomain("hephy.at")
    app.setWindowIcon(QtGui.QIcon("icons:sqc.ico"))
    app.setProperty("ContentsUrl", CONTENTS_URL)

    logger.info("Creating station...")
    station = Station()

    logger.info("Creating context...")
    context = Context(station)
    context.parameters.update({
        "option_debug_no_table": args.debug_no_table,
        "option_debug_no_tango": args.debug_no_tango,
        "option_debug": args.debug
    })

    window = MainWindow(context)
    window.addLogger(logger)

    logging.info("SQC version %s", __version__)

    logger.info("Installing plugins...")

    for plugin in ENABLED_PLUGINS:
        try:
            window.installPlugin(plugin())
        except Exception as exc:
            logger.exception(exc)
            logger.error("Failed to install plugin: %r", plugin)

    window.readSettings()
    window.show()

    app.exec()

    window.syncSettings()
    window.shutdown()

    station.shutdown()


if __name__ == "__main__":
    main()
