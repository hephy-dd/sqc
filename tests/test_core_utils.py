import pytest

from sqc.core.utils import (
    tokenize,
    cv_inverse_square,
    extract_slice,
    create_slices,
    normalize_strip_expression,
    parse_strip_expression,
    parse_strips
)


class TestUtils:

    def test_tokenize(self):
        assert list(tokenize("", ";")) == []
        assert list(tokenize(";", ";")) == []
        assert list(tokenize("A", ";")) == ["A"]
        assert list(tokenize("A; B ;C;;", ";")) == ["A", "B", "C"]

    def test_cv_inverse_square(self):
        assert cv_inverse_square(0, 0) == (0., 0.)
        assert cv_inverse_square(1, 1) == (1., 1.)
        assert cv_inverse_square(2, 2) == (2, .25)
        assert cv_inverse_square(3, 4) == (3., .0625)

    def test_extract_slice(self):
        names = ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]
        assert extract_slice(names, "P1", "P1") == ["P1"]
        assert extract_slice(names, "P7", "P7") == ["P7"]
        assert extract_slice(names, "P1", "P7") == ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]
        assert extract_slice(names, "P1", "P2") == ["P1", "P2"]
        assert extract_slice(names, "P1", "P3") == ["P1", "P2", "P3"]
        assert extract_slice(names, "P3", "P6") == ["P3", "P4", "P5", "P6"]
        with pytest.raises(ValueError):
            extract_slice(names, "P2", "P1")

    def test_create_slices(self):
        ...

    def test_normalize_strip_expression(self):
        assert normalize_strip_expression(" 4 ,2,8  - 16  , 42 ") == "4, 2, 8-16, 42"

    def test_parse_strip_expression(self):
        assert list(parse_strip_expression("")) == []
        assert list(parse_strip_expression("P1")) == [("P1", "P1")]
        assert list(parse_strip_expression("P1, P1")) == [("P1", "P1"), ("P1", "P1")]
        assert list(parse_strip_expression("P1-P4")) == [("P1", "P4")]
        assert list(parse_strip_expression("P1, P3-P4")) == [("P1", "P1"), ("P3", "P4")]
        assert list(parse_strip_expression("P1, P3-P4, P7")) == [("P1", "P1"), ("P3", "P4"), ("P7", "P7")]

    def test_parse_strips(self):
        names = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"]
        assert parse_strips(names, "") == []
        assert parse_strips(names, "P1") == ["P1"]
        assert parse_strips(names, "P2, P2") == ["P2"]
        assert parse_strips(names, "P1, P2") == ["P1", "P2"]
        assert parse_strips(names, "P1, P3, P2, P1, P2") == ["P1", "P2", "P3"]
        assert parse_strips(names, "P1, P3, P2, P1, P2, P1-P3") == ["P1", "P2", "P3"]
        assert parse_strips(names, "P1-P2") == ["P1", "P2"]
        assert parse_strips(names, "P1-P3, P8-P10") == ["P1", "P2", "P3", "P8", "P9", "P10"]
        assert parse_strips(names, "P8-P10, P1-P2, P1-P3, P3") == ["P1", "P2", "P3", "P8", "P9", "P10"]
        assert parse_strips(names, "P1-P3, P2-P5") == ["P1", "P2", "P3", "P4", "P5"]
        with pytest.raises(ValueError):
            parse_strips(names, "P3-P1")
        with pytest.raises(ValueError):
            parse_strips(names, "P42")
