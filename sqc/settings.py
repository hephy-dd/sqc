import os
from pathlib import Path
from typing import List, Tuple

from PyQt5 import QtCore

from .core.resource import Resource

__all__ = ["Settings"]

ROOT_PATH = os.path.dirname(os.path.dirname(__file__))

Position = Tuple[float, float, float]

DEFAULT_LOAD_POSITION = 0.0, 193309.0, 0.0

DEFAULT_MEASUREMENT_POSITION = 19585.0, 187568.0, 9700.0

DEFAULT_RESOURCES = {
    "bias_smu": {"model": "K2657A", "models": ["K2657A", "K2410", "K2470"]},
    "smu": {"model": "K2410", "models": ["K2657A", "K2410", "K2470"]},
    "lcr": {"model": "E4980A", "models": ["E4980A"]},
    "elm": {"model": "K6517B", "models": ["K6514", "K6517B"]},
    "hv_switch": {"model": "BrandBox", "models": ["BrandBox"]},
    "lv_switch": {"model": "K708B", "models": ["K708B"]},
    "environ": {"model": "EnvironBox", "models": ["EnvironBox"]},
    "table": {"model": "Venus1", "models": ["Venus1"]},
    "tango": {"model": "TANGO", "models": ["TANGO"]},
}


def load_padfiles() -> List[str]:
    padfiles = []
    path = os.path.join(ROOT_PATH, "config", "pads")
    for filename in list(Path(path).glob("**/*.txt")):
        padfiles.append(format(filename))
    return padfiles


def load_sequences() -> List[str]:
    sequences = []
    path = os.path.join(ROOT_PATH, "config", "sequences")
    for filename in list(Path(path).glob("*.yaml")):
        sequences.append(format(filename))
    return sequences


class Settings:

    def settings(self):
        return QtCore.QSettings()

    def alignment(self) -> list:
        settings = self.settings()
        settings.beginGroup("alignment")
        count = settings.beginReadArray("points")
        points = []
        for index in range(count):
            settings.setArrayIndex(index)
            x = settings.value("x", 0, float)
            y = settings.value("y", 0, float)
            z = settings.value("z", 0, float)
            points.append((x, y, z))
        settings.endArray()
        settings.endGroup()
        return points

    def setAlignment(self, points: list) -> None:
        settings = self.settings()
        settings.beginGroup("alignment")
        settings.beginWriteArray("points")
        for index, point in enumerate(points):
            x, y, z = point
            settings.setArrayIndex(index)
            settings.setValue("x", float(x))
            settings.setValue("y", float(y))
            settings.setValue("z", float(z))
        settings.endArray()
        settings.endGroup()

    def loadPosition(self) -> Position:
        position = self.settings().value("alignment/loadPosition", DEFAULT_LOAD_POSITION, tuple)
        return float(position[0]), float(position[1]), float(position[2])

    def setLoadPosition(self, position: Position) -> None:
        self.settings().setValue("alignment/loadPosition", position)

    def measurePosition(self) -> Position:
        position = self.settings().value("alignment/measurePosition", DEFAULT_MEASUREMENT_POSITION, tuple)
        return float(position[0]), float(position[1]), float(position[2])

    def setMeasurePosition(self, position: Position) -> None:
        self.settings().setValue("alignment/measurePosition", position)

    def resources(self) -> dict:
        settings = self.settings()
        count = settings.beginReadArray("resources")
        for index in range(count):
            settings.setArrayIndex(index)
            name = settings.value("name")
            if name:
                values = DEFAULT_RESOURCES.setdefault(name, {})
                values["model"] = settings.value("model", "") or values.get("model", "")
                values["address"] = settings.value("address", "")
                values["termination"] = settings.value("termination", "\n")
                values["timeout"] = settings.value("timeout", 4.0, float)
        settings.endArray()
        return DEFAULT_RESOURCES

    def setResources(self, resources: dict) -> None:
        settings = self.settings()
        settings.beginWriteArray("resources")
        for index, resource in enumerate(resources.items()):
            name, values = resource
            settings.setArrayIndex(index)
            settings.setValue("name", name)
            settings.setValue("model", values.get("model", ""))
            settings.setValue("address", values.get("address", ""))
            settings.setValue("termination", values.get("termination", "\n"))
            settings.setValue("timeout", float(values.get("timeout", 4.0)))
        settings.endArray()

    def createResource(self, name: str) -> Resource:
        resource = Settings().resources().get(name, {})
        return Resource(
            model=resource.get("model"),
            address=resource.get("address"),
            termination=resource.get("termination", "\r\n"),
            timeout=resource.get("timeout", 8.0),
        )
