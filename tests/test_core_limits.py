import math

from sqc.core.limits import LimitsAggregator


def test_limits_aggregator():
    limits = LimitsAggregator()
    assert limits.limits == (math.nan, math.nan, math.nan, math.nan)
    assert limits.is_valid is False
    limits.add([(2, 7)])
    assert limits.limits == (2, 7, 2, 7)
    assert limits.is_valid is True
    limits.add([(2, 3)])
    assert limits.limits == (2, 3, 2, 7)
    assert limits.is_valid is True
    limits.add([(3, 4)])
    assert limits.limits == (2, 3, 3, 7)
    assert limits.is_valid is True
    limits.add([(-2, 9)])
    assert limits.limits == (-2, 3, 3, 9)
    assert limits.is_valid is True
    limits.add([(2, 3)])
    assert limits.limits == (-2, 3, 3, 9)
    assert limits.is_valid is True
