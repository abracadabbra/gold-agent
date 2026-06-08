"""财经日历单元测试 — calendar.py"""

from unittest.mock import patch

import pandas as pd

from gold_agent.data.calendar import fetch_calendar, get_next_major_event, get_upcoming_events


class TestFetchCalendar:
    """测试 fetch_calendar"""

    def test_returns_dataframe(self):
        df = fetch_calendar()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_expected_columns(self):
        df = fetch_calendar()
        for col in ["date", "event", "importance", "type", "color", "type_label"]:
            assert col in df.columns

    def test_filters_by_start_date(self):
        df = fetch_calendar(start_date="2026-09-01")
        assert (df["date"] >= pd.Timestamp("2026-09-01")).all()

    def test_filters_by_end_date(self):
        df = fetch_calendar(end_date="2026-06-01")
        assert (df["date"] <= pd.Timestamp("2026-06-01")).all()

    def test_date_range_filter(self):
        df = fetch_calendar(start_date="2026-06-01", end_date="2026-06-30")
        assert len(df) > 0
        assert (df["date"] >= pd.Timestamp("2026-06-01")).all()
        assert (df["date"] <= pd.Timestamp("2026-06-30")).all()

    def test_sorted_by_date(self):
        df = fetch_calendar()
        assert df["date"].is_monotonic_increasing

    def test_importance_colors(self):
        df = fetch_calendar()
        assert df["color"].notna().all()

    def test_type_labels(self):
        df = fetch_calendar()
        assert df["type_label"].notna().all()


class TestGetUpcomingEvents:
    """测试 get_upcoming_events"""

    def test_returns_recent_future_events(self):
        df = get_upcoming_events(90)
        assert isinstance(df, pd.DataFrame)
        today = pd.Timestamp.now().normalize()
        assert (df["date"] >= today).all()

    def test_longer_days_returns_more(self):
        short = get_upcoming_events(7)
        long = get_upcoming_events(90)
        assert len(short) <= len(long)


class TestGetNextMajorEvent:
    """测试 get_next_major_event"""

    def test_returns_dict_or_none(self):
        event = get_next_major_event()
        if event is not None:
            assert isinstance(event, dict)
            assert "date" in event
            assert "event" in event
            assert "importance" in event

    def test_event_has_expected_keys(self):
        event = get_next_major_event()
        if event is not None:
            for key in ["date", "event", "type", "type_label", "importance", "color"]:
                assert key in event

    def test_no_upcoming_events_returns_none(self):
        """无即将发生的事件时返回 None（覆盖 line 83）"""
        with patch("gold_agent.data.calendar.get_upcoming_events",
                   return_value=pd.DataFrame()):
            event = get_next_major_event()
            assert event is None
