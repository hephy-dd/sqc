import io
import os

import pytest

from sqc.core import geometry
from sqc.core.geometry import Pad, Padfile
from sqc.core.geometry import read_property, read_pad


def test_pad():
    p = Pad("P", 1, 2, 3)
    assert p.name == "P"
    assert p.x == 1
    assert p.y == 2
    assert p.z == 3
    assert p.position == (1, 2, 3)
    assert (p == Pad("P", 1, 2, 3)) is True
    assert (p == Pad("A", 1, 2, 3)) is False
    assert (p == Pad("P", 1, 1, 3)) is False
    assert p.distance(p) == 0


def test_pad_distance():
    p = Pad("P", 1, 2, 3)
    q = Pad("Q", 4, -5, 6)
    assert p.distance(q) == 8.18535277187245


def test_pad_distance_null():
    p = Pad("P", 1, 2, 3)
    q = Pad("Q", 1, 2, 3)
    assert p.distance(q) == 0


def test_pads():
    pp = Padfile()
    assert pp.properties == {}
    assert pp.pads == {}
    assert pp.references == []
    pp.set_property("foo", 42)
    pp.add_pad("P", 1, 2, 3)
    assert pp.properties == {"foo": 42}
    assert pp.pads == {"P": Pad("P", 1, 2, 3)}
    assert pp.references == []


def test_pads_index():
    pp = Padfile()
    pp.add_pad("A1", 1, 2, 3)
    pp.add_pad("B2", 1, 4, 3)
    pp.add_pad("C3", 1, 5, 3)
    assert pp.index("A1") == 0
    assert pp.index("B2") == 1
    assert pp.index("C3") == 2
    with pytest.raises(ValueError):
        pp.index("B1")


def test_pads_slice():
    pp = Padfile()
    pp.add_pad("P1", 1, 2, 3)
    pp.add_pad("P2", 1, 4, 3)
    pp.add_pad("P3", 1, 5, 3)
    pp.add_pad("P4", 1, 6, 3)
    pp.add_pad("P5", 1, 7, 3)
    assert pp.slice("P1", "P5") == list(pp.pads.values())
    assert pp.slice("P3", "P3") == [pp.pads["P3"]]
    assert pp.slice("P1", "P3") == [pp.pads["P1"], pp.pads["P2"], pp.pads["P3"]]
    with pytest.raises(ValueError):
        pp.slice("P3", "P1")
    with pytest.raises(ValueError):
        pp.slice("A1", "P2")


def test_read_property():
    assert read_property("") is None
    assert read_property(":") is None
    assert read_property("foo") is None
    assert read_property(" foo:") == ("foo", "")
    assert read_property("foo: 42 ") == ("foo", "42")
    assert read_property(" foo: b:ar ") == ("foo", "b:ar")
    assert read_property("Foo Bar: 42") == ("foo_bar", "42")


def test_read_pad():
    assert read_pad("") is None
    assert read_pad("P") is None
    assert read_pad("P 1 2") is None
    assert read_pad("P 1 2 3") == ("P", 1, 2, 3)
    assert read_pad("P 1 2 3 4") is None


def test_load():
    ref_pads = {
        "A": Pad("A", 1, 0, -1),
        "B": Pad("B", -1, 0, 1),
        "C": Pad("C", 1, 0, 2)
    }
    data = io.StringIO(os.linesep.join([
        "name: test",
        "",
        "reference pad: A",
        "reference pad: C",
        "",
        "strip\tx\ty\tz",
        "A\t1\t0\t-1",
        "B\t-1\t0\t+1",
        "C\t1\t0\t2",
    ]))
    pp = geometry.load(data)
    assert pp.properties == {"name": "test"}
    assert pp.pads == ref_pads
    assert pp.references == [ref_pads.get("A"), ref_pads.get("C")]


def test_dump():
    pp = geometry.Padfile()
    pp.set_property("name", "test")
    pp.add_pad("A", 0, -1, 0)
    pp.add_pad("B", 0, 0, 0)
    pp.add_pad("C", -1, 1, 0)
    pp.set_reference("A")
    pp.set_reference("C")
    fp = io.StringIO()
    geometry.dump(pp, fp)
    ref = os.linesep.join([
        "name: test",
        "",
        "reference pad: A",
        "reference pad: C",
        "",
        "strip\tx\ty\tz",
        "A\t0\t-1\t0",
        "B\t0\t0\t0",
        "C\t-1\t1\t0",
        "",
    ])
    fp.seek(0)
    assert fp.read() == ref
