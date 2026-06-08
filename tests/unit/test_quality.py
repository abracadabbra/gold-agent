"""Data quality metadata helper tests."""

from datetime import UTC, datetime

import pandas as pd

from gold_agent.data.quality import (
    align_series_as_of,
    dataframe_meta,
    with_alignment_info,
)


class TestDataframeMeta:
    def test_dataframe_meta_for_non_empty_df(self):
        fetched_at = datetime(2024, 2, 1, 8, 30, tzinfo=UTC)
        cached_at = datetime(2024, 2, 1, 8, 0, tzinfo=UTC)
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "close": [2000.0, None, 2010.0],
            "volume": [100.0, 101.0, None],
        })

        meta = dataframe_meta(
            df,
            max_stale_days=9999,
            source_status="cache",
            fetched_at=fetched_at,
            cached_at=cached_at,
            expected_frequency="daily",
        )

        assert meta["as_of"] == "2024-01-03T00:00:00"
        assert meta["latest_date"] == "2024-01-03T00:00:00"
        assert meta["fetched_at"] == fetched_at.isoformat()
        assert meta["cached_at"] == cached_at.isoformat()
        assert meta["row_count"] == 3
        assert meta["stale"] is False
        assert meta["source_status"] == "cache"
        assert meta["missing_rate"] == 0.2222
        assert meta["quality_score"] == 78
        assert meta["expected_frequency"] == "daily"

    def test_dataframe_meta_for_empty_df(self):
        meta = dataframe_meta(
            pd.DataFrame(),
            source_status="unavailable",
            expected_frequency="weekly",
        )

        assert meta["as_of"] is None
        assert meta["latest_date"] is None
        assert meta["cached_at"] is None
        assert meta["row_count"] == 0
        assert meta["stale"] is False
        assert meta["source_status"] == "unavailable"
        assert meta["missing_rate"] == 0.0
        assert meta["quality_score"] == 0
        assert meta["expected_frequency"] == "weekly"

    def test_dataframe_meta_marks_stale_data(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2020-01-01"]),
            "close": [1800.0],
        })

        meta = dataframe_meta(df, max_stale_days=1)

        assert meta["stale"] is True
        assert meta["quality_score"] == 70


class TestAlignSeriesAsOf:
    def test_align_series_as_of_returns_latest_row_before_anchor(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-05"]),
            "tips_yield": [1.2, 1.4, 1.6],
        })

        aligned = align_series_as_of(
            df,
            anchor_date="2024-01-04",
            required_cols=["tips_yield"],
        )

        assert aligned is not None
        assert float(aligned["row"]["tips_yield"]) == 1.4
        assert aligned["aligned_as_of"] == "2024-01-03T00:00:00"
        assert aligned["lag_days"] == 1

    def test_align_series_as_of_returns_none_when_no_eligible_rows(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-05"]),
            "tips_yield": [1.6],
        })

        aligned = align_series_as_of(
            df,
            anchor_date="2024-01-04",
            required_cols=["tips_yield"],
        )

        assert aligned is None


class TestWithAlignmentInfo:
    def test_with_alignment_info_merges_fields(self):
        payload = {"tips_yield": 1.4}
        aligned = {
            "aligned_as_of": "2024-01-03T00:00:00",
            "lag_days": 1,
        }

        result = with_alignment_info(payload, aligned)

        assert result == {
            "tips_yield": 1.4,
            "aligned_as_of": "2024-01-03T00:00:00",
            "lag_days": 1,
        }
