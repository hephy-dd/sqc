import math
import os
import re
from typing import Any, Dict, Generator, List, Optional, TextIO, Tuple

from .utils import extract_slice

__all__ = ["Pad", "Padfile", "NeedlesGeometry", "load", "dump"]


# Python < 3.8
# See https://docs.python.org/3/library/math.html#math.dist
if not hasattr(math, "dist"):
    math.dist = lambda p, q: math.sqrt(sum((px - qx) ** 2.0 for px, qx in zip(p, q)))  # type: ignore

Position = Tuple[int, int, int]


class Pad:
    """Pad represents a single contact pad on a silicon sensor.

    Argument `name` is the name of the pad, arguments `x`, `y` and `z` represent the
    relative position of the pad on the sensor.
    """

    def __init__(self, name: str, x: int, y: int, z: int) -> None:
        self.name: str = name
        self.x: int = x
        self.y: int = y
        self.z: int = z

    @property
    def position(self) -> Position:
        return self.x, self.y, self.z

    def distance(self, other: "Pad") -> float:
        """Retrun the relative distance to the `other` pad."""
        return math.dist(self.position, other.position)  # type: ignore

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pad):
            raise NotImplementedError
        return (self.name, self.position) == (other.name, other.position)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(\'{self.name}\', {self.x}, {self.y}, {self.z})"


class Padfile:

    def __init__(self) -> None:
        self.properties: Dict[str, Any] = {}
        self.pads: Dict[str, Pad] = {}
        self.references: List[Pad] = []

    def set_property(self, name: str, value: Any) -> None:
        self.properties[name] = value

    def add_pad(self, name: str, x: int, y: int, z: int) -> None:
        if name in self.pads:
            raise KeyError(f"Pad already exists: {name}")
        self.pads[name] = Pad(name, x, y, z)

    def set_reference(self, name: str) -> None:
        pad = self.pads.get(name)
        if pad is None:
            raise KeyError(f"No such reference pad: {name}")
        if pad not in self.references:
            self.references.append(pad)

    def index(self, name: str) -> int:
        """Return pad index for name."""
        return list(self.pads.keys()).index(name)

    def slice(self, start: str, end: str) -> List[Optional[Pad]]:
        """Return slice of pads beginning with `start` up to `end`."""
        sorted_keys = extract_slice(list(self.pads.keys()), start, end)
        return [self.pads.get(key) for key in sorted_keys]

    def find_pad(self, position: Position) -> Optional[Pad]:
        """Return pad at position or `None` if no pad at position found."""
        for pad in self.pads.values():
            if pad.position == position:
                return pad
        return None


class NeedlesGeometry:

    def __init__(self, padfile: Padfile, count: int) -> None:
        self.padfile = padfile
        self.count = count

    def geometry(self) -> List[Position]:
        pitch: int = abs(int(self.padfile.properties.get("pitch", 0)))
        positions: List[Position] = [(0, 0, 0)]
        if pitch:
            for _ in range(self.count):
                positions.append((0, -pitch, 0))
        return positions

    def is_pad_valid(self, pad: Pad) -> bool:
        x, y, z = pad.position
        for a, b, c in self.geometry():
            position = x + a, y + b, z + c
            result = self.padfile.find_pad(position)
            if result is None:
                return False
        return True


regex_comment = re.compile(r'^#')
regex_property = re.compile(r'^([^\:]+)\:(.*)$')
regex_header = re.compile(r'^strip\s+x\s+y\s+z$')
regex_pad = re.compile(r'^(\w+)\s+([+-]?\d+)\s+([+-]?\d+)\s+([+-]?\d+)$')


def sanitize_property_name(name: str) -> str:
    return name.strip().replace(" ", "_").lower()


def sanitize_property_value(value: str) -> str:
    return value.strip()


def sanitize_pad_name(name: str) -> str:
    return name.strip()


def read_property(line: str) -> Optional[Tuple[str, str]]:
    match = regex_property.match(line)
    if match:
        name, value = match.groups()
        return sanitize_property_name(name), sanitize_property_value(value)
    return None


def read_pad(line: str) -> Optional[Tuple[str, int, int, int]]:
    match = regex_pad.match(line)
    if match:
        name = sanitize_pad_name(match.group(1))
        x = int(match.group(2))
        y = int(match.group(3))
        z = int(match.group(4))
        return name, x, y, z
    return None


def load(fp: TextIO) -> Padfile:
    padfile: Padfile = Padfile()
    references: List[str] = []
    for line in fp:
        line = line.strip()
        if not line:
            continue
        if regex_comment.match(line):
            continue
        if regex_header.match(line):
            continue
        # Properties
        prop = read_property(line)
        if prop is not None:
            name, value = prop
            if name == "reference_pad":
                references.append(value)
            else:
                padfile.set_property(name, value)
            continue
        # Pads
        pad = read_pad(line)
        if pad is not None:
            name, x, y, z = pad
            padfile.add_pad(name, x, y, z)
            continue
        raise ValueError(line)
    # Set reference pads
    for name in references:
        padfile.set_reference(name)
    return padfile


def dump(padfile: Padfile, fp: TextIO) -> None:
    # Properties
    for key, value in padfile.properties.items():
        fp.write(f"{key}: {value}{os.linesep}")
    if padfile.properties:
        fp.write(os.linesep)
    # References
    for pad in padfile.references:
        fp.write(f"reference pad: {pad.name}{os.linesep}")
    if padfile.references:
        fp.write(os.linesep)
    # Pads
    fp.write(f"strip\tx\ty\tz{os.linesep}")
    for pad in padfile.pads.values():
        fp.write(f"{pad.name}\t{pad.x:d}\t{pad.y:d}\t{pad.z:d}{os.linesep}")
