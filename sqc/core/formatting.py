from typing import List

from comet.utils import auto_scale

__all__ = ["format_metric", "format_switch", "format_channels"]


def format_metric(value: float, unit: str, decimals: int = 3) -> str:
    """Pretty format metric units.
    >>> format_metric(.0042, "A")
    '4.200 mA'
    """
    if value is None:
        return "---"
    scale, prefix, _ = auto_scale(value)
    return f"{value * (1. / scale):.{decimals}f} {prefix}{unit}"


def format_switch(value: bool) -> str:
    """Pretty format for instrument output states.
    >>> format_switch(False)
    'OFF'
    """
    return {False: "OFF", True: "ON"}.get(value) or "N/A"


def format_channels(channels: List[str]) -> str:
    """Pretty format for switching matrix channels.
    >>> format_channels(["A1", "B1", "C2"])
    'A1, B1, C2'
    """
    return ", ".join(sorted([format(channel).strip() for channel in channels]))
