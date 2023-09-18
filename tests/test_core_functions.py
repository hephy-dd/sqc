import random

from sqc.core.functions import steady_state_check


def steady_source():
    return random.uniform(4.2e-12, 4.2e-13)


def test_steady_state_check():
    assert steady_state_check(steady_source) is True
