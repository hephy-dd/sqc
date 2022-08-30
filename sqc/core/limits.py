import math
from typing import Iterable, Tuple

__all__ = ["LimitsAggregator"]


class LimitsAggregator:

    def __init__(self) -> None:
        self.xmin: float = math.nan
        self.ymin: float = math.nan
        self.xmax: float = math.nan
        self.ymax: float = math.nan

    @property
    def limits(self) -> Tuple[float, float, float, float]:
        return self.xmin, self.ymin, self.xmax, self.ymax

    @property
    def is_valid(self) -> bool:
        for value in self.limits:
            if not math.isfinite(value):
                return False
        return True

    def add(self, points: Iterable) -> None:
        """Aggregate limits from series of points."""
        for x, y in points:
            self.xmin = float(min(x, self.xmin))
            self.ymin = float(min(y, self.ymin))
            self.xmax = float(max(x, self.xmax))
            self.ymax = float(max(y, self.ymax))
