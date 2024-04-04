import logging
import time
import os
import json

from comet.utils import make_iso, safe_filename

from sqc import __version__

__all__ = ["JSONWriterPlugin"]


logger = logging.getLogger(__name__)


class JSONWriterPlugin:

    def install(self, window) -> None:
        context = window.context
        context.add_writer(JSONWriter(context))

    def uninstall(self, window) -> None:
        ...


class JSONWriter:

    def __init__(self, context):
        self.context = context

    def __call__(self, namespace: str, parameters: dict, data: dict) -> None:
        timestamp = parameters.get("timestamp", time.time())
        sensor_name = parameters.get("sensor_name", "")
        output_path = os.path.realpath(parameters.get("output_path", os.getcwd()))
        output_path = os.path.join(output_path, safe_filename(sensor_name))

        prefix = "SQC_"
        suffix = make_iso(timestamp)
        if namespace:
            suffix = f"{suffix}_{namespace}"
        basename = safe_filename(f"{prefix}{sensor_name}-{suffix}.json")
        filename = os.path.join(output_path, basename)

        path = os.path.dirname(filename)
        if not os.path.exists(path):
            logger.info("Creating directory: %s", path)
            os.makedirs(path)

        header = {}
        header["sqc_version"] = __version__
        header.update(parameters)
        content = {
            "version": "1.0",
            "header": header,
            "data": data
        }

        logger.info("Writing to %s...", filename)
        with open(filename, "w") as fp:
            json.dump(content, fp)
