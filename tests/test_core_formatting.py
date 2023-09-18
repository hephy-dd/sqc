from sqc.core import formatting


def test_format_metric():
    assert formatting.format_metric(42, "V") == "42.000 V"
    assert formatting.format_metric(42, "V", 1) == "42.0 V"
    assert formatting.format_metric(42, "V", 0) == "42 V"
    assert formatting.format_metric(42_000, "V") == "42.000 kV"
    assert formatting.format_metric(4.2e-11, "A", 1) == "42.0 pA"


def test_format_switch():
    assert formatting.format_switch(False) == "OFF"
    assert formatting.format_switch(True) == "ON"
    assert formatting.format_switch(0) == "OFF"
    assert formatting.format_switch(1) == "ON"
    assert formatting.format_switch(2) == "N/A"
    assert formatting.format_switch(None) == "N/A"


def test_format_channels():
    assert formatting.format_channels([]) == ""
    assert formatting.format_channels(["A1"]) == "A1"
    assert formatting.format_channels(["A1", "B2"]) == "A1, B2"
    assert formatting.format_channels(["A1", "B2"]) == "A1, B2"
    assert formatting.format_channels(["A1", "B2 ", " CX"]) == "A1, B2, CX"
