import pytest
from datetime import datetime, timezone, timedelta
from app.services.news_blocker import is_in_news_window


def now():
    return datetime.now(timezone.utc)


def event(offset_minutes: int, impact: str = "HIGH") -> dict:
    return {
        "time":   (now() + timedelta(minutes=offset_minutes)).isoformat(),
        "name":   f"Test Event @{offset_minutes}m",
        "impact": impact,
    }


class TestNewsBlocker:
    def test_blocks_event_15_min_ahead(self):
        blocked, names = is_in_news_window([event(15)])
        assert blocked is True
        assert len(names) == 1

    def test_blocks_event_15_min_behind(self):
        blocked, _ = is_in_news_window([event(-15)])
        assert blocked is True

    def test_allows_event_31_min_ahead(self):
        blocked, _ = is_in_news_window([event(31)])
        assert blocked is False

    def test_allows_event_31_min_behind(self):
        blocked, _ = is_in_news_window([event(-31)])
        assert blocked is False

    def test_boundary_exactly_30(self):
        blocked, _ = is_in_news_window([event(30)])
        assert blocked is True

    def test_ignores_medium_impact(self):
        blocked, _ = is_in_news_window([event(5, impact="MEDIUM")])
        assert blocked is False

    def test_ignores_low_impact(self):
        blocked, _ = is_in_news_window([event(5, impact="LOW")])
        assert blocked is False

    def test_empty_event_list(self):
        blocked, names = is_in_news_window([])
        assert blocked is False
        assert names == []

    def test_multiple_events_one_blocking(self):
        events = [event(-60), event(10)]  # old event + upcoming
        blocked, names = is_in_news_window(events)
        assert blocked is True
        assert len(names) == 1

    def test_custom_window(self):
        blocked, _ = is_in_news_window([event(45)], window_minutes=60)
        assert blocked is True

    def test_names_returned(self):
        e = event(5)
        e["name"] = "FOMC Minutes"
        _, names = is_in_news_window([e])
        assert "FOMC Minutes" in names
