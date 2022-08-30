import logging
from typing import Dict

import pyvisa
from comet.driver import Driver

logger = logging.getLogger(__name__)

driver_registry: Dict[str, Driver] = {}


def create_driver(model: str) -> Driver:
    if model not in driver_registry:
        raise ValueError(f"No such model: {model}")
    return driver_registry.get(model)


def to_millisec(seconds: float) -> int:
    return int(seconds * 1e3)


def format_exception(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def format_resource(resource: "Resource") -> str:
    return f"{resource.model} ({resource.address})"


class ResourceError(Exception):
    ...


class Resource:

    def __init__(self, model: str, address: str, termination: str, timeout: float):
        self.visa_library: str = "@py"
        self.model: str = model
        self.address: str = address
        self.termination: str = termination
        self.timeout: float = timeout
        self._resource = None

    def __enter__(self):
        options = {
            "resource_name": self.address,
            "read_termination": self.termination,
            "write_termination": self.termination,
            "timeout": to_millisec(self.timeout)
        }
        rm = pyvisa.ResourceManager(self.visa_library)
        try:
            self._resource = rm.open_resource(**options)
        except Exception as exc:
            error_message = f"Failed to open resource: {format_resource(self)}: {format_exception(exc)}"
            raise ResourceError(error_message) from exc
        return self

    def __exit__(self, *args):
        try:
            self._resource.close()
        except Exception as exc:
            error_message = f"Failed to close resource: {format_resource(self)}: {format_exception(exc)}"
            raise ResourceError(error_message) from exc
        finally:
            self._resource = None
        return False

    def query(self, message: str) -> str:
        try:
            return self._resource.query(message)
        except Exception as exc:
            error_message = f"Failed to query from resource: {format_resource(self)}: {format_exception(exc)}"
            raise ResourceError(error_message) from exc

    def read(self) -> str:
        try:
            return self._resource.read()
        except Exception as exc:
            error_message = f"Failed to read from resource: {format_resource(self)}: {format_exception(exc)}"
            raise ResourceError(error_message) from exc

    def write(self, message: str) -> int:
        try:
            return self._resource.write(message)
        except Exception as exc:
            error_message = f"Failed to write to resource: {format_resource(self)}: {format_exception(exc)}"
            raise ResourceError(error_message) from exc

    def clear(self):
        self._resource.clear()
