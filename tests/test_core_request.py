import pytest

from sqc.core.request import Request, RequestTimeout


def test_request():
    r = Request(lambda: 42)
    r()
    assert r.get(timeout=.025) == 42


def test_request_exception():
    r = Request(lambda: 1 / 0)
    r()
    with pytest.raises(ZeroDivisionError):
        r.get(timeout=.025)


def test_request_timeout():
    r = Request(lambda: None)
    with pytest.raises(RequestTimeout):
        r.get(timeout=.025)
