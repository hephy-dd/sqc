import logging
from typing import Callable, Dict

from comet.parameter import ParameterBase

__all__ = ["Measurement"]

logger = logging.getLogger(__name__)

measurement_registry: Dict[str, "Measurement"] = {}


def register_measurement(key: str) -> Callable:
    def register_measurement(cls: type) -> type:
        measurement_registry[key] = cls
        return cls
    return register_measurement


class Measurement(ParameterBase):

    def __init__(self, context, type: str, name: str, namespace: str, parameters: dict):
        super().__init__(parameters)
        self.context = context
        self.type: str = type
        self.name: str = name
        self.namespace: str = namespace

    def set_message(self, message: str) -> None:
        self.context.set_message(message)

    def set_progress(self, minimum: int, maximum: int, value: int) -> None:
        self.context.set_progress(minimum, maximum, value)

    def insert_data(self, values: dict, sortkey: str) -> None:
        self.context.insert_data(namespace=self.namespace, type=self.type, name=self.name, data=values, sortkey=sortkey)

    def handle_abort(self) -> None:
        self.context.handle_abort()

    def before_sequence(self) -> None:
        ...

    def after_sequence(self) -> None:
        ...

    def before_strip(self) -> None:
        ...

    def after_strip(self) -> None:
        ...

    def initialize(self) -> None:
        ...

    def acquire(self) -> None:
        ...

    def finalize(self) -> None:
        ...
