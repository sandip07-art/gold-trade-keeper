import pytest
from datetime import datetime, timezone
from app.services.session_filter import get_session


def utc(h, m=0):
    return datetime(2024, 6, 10, h, m, tzinfo=timezone.utc)


class TestLondonSession:
    def test_start_boundary(self):   name, ok = get_session(utc(7, 0));   assert ok and name == "LONDON"
    def test_mid_session(self):      name, ok = get_session(utc(8, 30));  assert ok and name == "LONDON"
    def test_end_exclusive(self):    name, ok = get_session(utc(10, 0));  assert not ok
    def test_before_start(self):     name, ok = get_session(utc(6, 59));  assert not ok


class TestNewYorkSession:
    def test_start_boundary(self):   name, ok = get_session(utc(12, 0));  assert ok and name == "NEW_YORK"
    def test_mid_session(self):      name, ok = get_session(utc(14, 0));  assert ok and name == "NEW_YORK"
    def test_end_exclusive(self):    name, ok = get_session(utc(16, 0));  assert not ok
    def test_before_start(self):     name, ok = get_session(utc(11, 59)); assert not ok


class TestOutsideSession:
    def test_early_morning(self):    name, ok = get_session(utc(3, 0));   assert not ok and name == "OUTSIDE"
    def test_evening(self):          name, ok = get_session(utc(20, 0));  assert not ok and name == "OUTSIDE"
    def test_between_sessions(self): name, ok = get_session(utc(10, 30)); assert not ok and name == "OUTSIDE"


def test_defaults_to_utc_now():
    """Should not raise when called without argument."""
    name, ok = get_session()
    assert isinstance(ok, bool)
    assert isinstance(name, str)
