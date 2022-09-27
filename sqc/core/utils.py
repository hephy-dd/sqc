import re
from typing import Generator, List, Tuple

from comet.utils import inverse_square

__all__ = [
    "tokenize",
    "cv_inverse_square",
    "extract_slice",
    "create_slices",
    "normalize_strip_expression",
    "parse_strip_expression",
    "parse_strips",
    "verify_position",
]


def tokenize(expression: str, separator: str) -> Generator[str, None, None]:
    """Tokenize expression using separator, empty tokens are omitted."""
    return (t.strip() for t in expression.split(separator) if t.strip())


def cv_inverse_square(x: float, y: float) -> Tuple[float, float]:
    """Safe inverse square transformation for CV plots."""
    return x, inverse_square(y) if y else 0.  # prevent division by zero


def extract_slice(names: List[str], start: str, end: str) -> List[str]:
    """Extract a slice from list of names."""
    start_index: int = names.index(start)
    end_index: int = names.index(end)
    if not start_index <= end_index:
        raise ValueError(f"invalid pad slice: {start}, {end}")
    return names[start_index:end_index + 1]


def create_slices(all: List[str], selected: List[str]) -> List[List[str]]:
    """Create continuous slices of selected names."""
    slices: List[List[str]] = []
    keys: List[str] = []
    for key in all:
        if key in selected:
            keys.append(key)
        else:
            if keys:
                slices.append(keys)
            keys = []
    if keys:
        slices.append(keys)
    return slices


def normalize_strip_expression(expression: str) -> str:
    """Return normalized version of strip expression."""
    return re.sub(r"\s*", "", expression).strip().replace(",", ", ")


def parse_strip_expression(expression: str) -> Generator[Tuple[str, str], None, None]:
    """Return list of tuples representing a slice of names."""
    tokens = [token for token in re.split(r"\s*\,\s*", expression) if token]
    for token in tokens:
        result = token.split("-", 1)
        yield result[0], result[-1]


def parse_strips(names: List[str], expression: str) -> List[str]:
    """Return expanded list of names specified by expression."""
    unsorted_names = set()
    for start, end in parse_strip_expression(expression):
        unsorted_names.update(extract_slice(names, start, end))
    return sorted(unsorted_names, key=names.index)


def verify_position(reference: Tuple[float, float, float], position: Tuple[float, float, float], threshold: float) -> bool:
    """Return True if both coordinates match within given threshold for values."""
    for a, b in zip(reference, position):
        if abs(a - b) > abs(threshold):
            return False
    return True
