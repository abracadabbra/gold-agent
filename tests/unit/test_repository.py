"""数据仓库单元测试 — repository.py"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gold_agent.db.models import Base
from gold_agent.db.repository import (
    _df_to_records,
    get_data_fetch_runs_overview,
    save_data_fetch_run,
    save_gold_prices,
    save_macro_data,
    save_news_articles,
    save_technical_indicators,
    save_trade_signal,
)


class TestDfToRecords:
    """测试 _df_to_records 内部函数"""

    def test_normal_df(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0]})
        result = _df_to_records(df)
        assert result == [{"a": 1, "b": 3.0}, {"a": 2, "b": 4.0}]

    def test_na_treated_as_none(self):
        import numpy as np
        df = pd.DataFrame({"a": [1.0, np.nan], "b": ["x", None]})
        result = _df_to_records(df)
        assert result[1]["a"] is None
        assert result[1]["b"] is None

    def test_nat_treated_as_none(self):
        df = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", None])})
        result = _df_to_records(df)
        assert result[0]["date"] is not None
        assert result[1]["date"] is None


class TestSaveGoldPrices:
    """测试 save_gold_prices"""

    def test_saves_new_records(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1
        records = [{"date": "2024-01-01", "source": "xauusd", "close": 2000.0, "open": 1990.0}]
        saved = save_gold_prices(db, records)
        assert saved == 1
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_skips_duplicates(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 0
        records = [{"date": "2024-01-01", "source": "xauusd", "close": 2000.0}]
        saved = save_gold_prices(db, records)
        assert saved == 0
        db.execute.assert_called_once()

    def test_partial_dedup(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1
        records = [
            {"date": "2024-01-01", "source": "xauusd", "close": 2000.0},
            {"date": "2024-01-02", "source": "xauusd", "close": 2010.0},
        ]
        saved = save_gold_prices(db, records)
        assert saved == 1

    def test_save_gold_prices_uses_postgresql_dialect_when_available(self):
        db = MagicMock()
        db.bind.dialect.name = "postgresql"
        db.execute.return_value.rowcount = 1

        saved = save_gold_prices(
            db,
            [{"date": "2024-01-01", "source": "xauusd", "close": 2000.0}],
        )

        assert saved == 1
        db.execute.assert_called_once()

    def test_upserts_existing_record(self):
        session = TestGetDataFetchRunsOverview._session()
        try:
            from gold_agent.db.models import GoldPrice

            save_gold_prices(
                session,
                [{"date": "2024-01-01", "source": "xauusd", "close": 2000.0}],
            )
            saved = save_gold_prices(
                session,
                [{"date": "2024-01-01", "source": "xauusd", "close": 2010.0}],
            )

            rows = session.query(GoldPrice).all()
            assert saved == 1
            assert len(rows) == 1
            assert rows[0].close == 2010.0
        finally:
            session.close()


class TestSaveTechnicalIndicators:
    """测试 save_technical_indicators"""

    def test_saves_new_records(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1
        records = [{"date": "2024-01-01", "source": "xauusd", "rsi14": 55.0, "ma5": 2000.0}]
        saved = save_technical_indicators(db, records)
        assert saved == 1
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_skips_duplicates(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 0
        records = [{"date": "2024-01-01", "source": "xauusd", "rsi14": 55.0}]
        saved = save_technical_indicators(db, records)
        assert saved == 0
        db.execute.assert_called_once()

    def test_maps_legacy_indicator_keys(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1

        saved = save_technical_indicators(
            db,
            [
                {
                    "date": "2024-01-01",
                    "source": "xauusd",
                    "macd_histogram": 1.2,
                    "bb_middle": 2001.0,
                    "supertrend_direction": 1,
                }
            ],
        )

        assert saved == 1
        stmt = db.execute.call_args.args[0]
        row = stmt.compile().params
        assert row["macd_hist_m0"] == 1.2
        assert row["bb_mid_m0"] == 2001.0
        assert row["supertrend_dir_m0"] == 1

    def test_upserts_existing_record(self):
        session = TestGetDataFetchRunsOverview._session()
        try:
            from gold_agent.db.models import TechnicalIndicator

            save_technical_indicators(
                session,
                [{"date": "2024-01-01", "source": "xauusd", "rsi14": 55.0}],
            )
            saved = save_technical_indicators(
                session,
                [{"date": "2024-01-01", "source": "xauusd", "rsi14": 60.0}],
            )

            rows = session.query(TechnicalIndicator).all()
            assert saved == 1
            assert len(rows) == 1
            assert rows[0].rsi14 == 60.0
        finally:
            session.close()


class TestSaveTradeSignal:
    """测试 save_trade_signal"""

    def test_saves_new_signal(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1
        signal = {  # noqa: E501
            "date": "2024-01-01", "source": "xauusd",
            "signal": "buy", "score": 50.0, "confidence": 0.7,
        }
        result = save_trade_signal(db, signal)
        assert result is True
        db.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_skips_existing(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 0
        signal = {"date": "2024-01-01", "source": "xauusd", "signal": "buy"}
        result = save_trade_signal(db, signal)
        assert result is False
        db.execute.assert_called_once()

    def test_default_values(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1
        result = save_trade_signal(db, {"date": "2024-01-01"})
        assert result is True
        stmt = db.execute.call_args.args[0]
        row = stmt.compile().params
        assert row["source_m0"] == "intl"
        assert row["signal_type_m0"] == "neutral"
        assert row["confidence_m0"] == 0.5

    def test_upserts_existing_signal(self):
        session = TestGetDataFetchRunsOverview._session()
        try:
            from gold_agent.db.models import TradeSignal

            save_trade_signal(
                session,
                {
                    "date": "2024-01-01",
                    "source": "xauusd",
                    "signal": "buy",
                    "score": 50.0,
                    "confidence": 0.7,
                },
            )
            saved = save_trade_signal(
                session,
                {
                    "date": "2024-01-01",
                    "source": "xauusd",
                    "signal": "sell",
                    "score": -40.0,
                    "confidence": 0.8,
                },
            )

            rows = session.query(TradeSignal).all()
            assert saved is True
            assert len(rows) == 1
            assert rows[0].signal_type == "sell"
            assert rows[0].score == -40.0
            assert rows[0].confidence == 0.8
        finally:
            session.close()


class TestSaveMacroData:
    """测试 save_macro_data"""

    def test_saves_new_records(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1
        records = [  # noqa: E501
            {"date": "2024-01-01", "indicator": "usd_index", "value": 104.5, "source": "yfinance"},
        ]
        saved = save_macro_data(db, records)
        assert saved == 1
        db.execute.assert_called_once()

    def test_skips_duplicates(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 0
        records = [{"date": "2024-01-01", "indicator": "usd_index", "value": 104.5}]
        saved = save_macro_data(db, records)
        assert saved == 0

    def test_skips_empty_indicator(self):
        db = MagicMock()
        records = [{"date": "2024-01-01", "indicator": "", "value": 104.5}]
        saved = save_macro_data(db, records)
        assert saved == 0
        db.execute.assert_not_called()

    def test_skips_none_value(self):
        db = MagicMock()
        records = [{"date": "2024-01-01", "indicator": "usd_index", "value": None}]
        saved = save_macro_data(db, records)
        assert saved == 0
        db.execute.assert_not_called()

    def test_skips_non_finite_long_value(self):
        db = MagicMock()
        records = [
            {"date": "2024-01-01", "indicator": "usd_index", "value": float("nan")},
            {"date": "2024-01-01", "indicator": "vix", "value": float("inf")},
        ]
        saved = save_macro_data(db, records)
        assert saved == 0
        db.execute.assert_not_called()

    def test_custom_indicator_col(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1
        records = [{"date": "2024-01-01", "custom_key": "vix", "value": 15.0}]
        saved = save_macro_data(db, records, indicator_col="custom_key")
        assert saved == 1

    def test_expands_wide_macro_records(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 2

        saved = save_macro_data(
            db,
            [{"date": "2024-01-01", "usd_index": 104.5, "vix": 15.2}],
            source="yfinance",
        )

        assert saved == 2
        stmt = db.execute.call_args.args[0]
        rows = stmt.compile().params
        assert rows["indicator_m0"] == "usd_index"
        assert rows["source_m0"] == "yfinance"
        assert rows["value_m0"] == 104.5
        assert rows["indicator_m1"] == "vix"
        assert rows["source_m1"] == "yfinance"
        assert rows["value_m1"] == 15.2

    def test_expands_wide_macro_records_skipping_non_finite_values(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1

        saved = save_macro_data(
            db,
            [{
                "date": "2024-01-01",
                "usd_index": 104.5,
                "vix": float("nan"),
                "us_10y": float("inf"),
            }],
            source="yfinance",
        )

        assert saved == 1
        stmt = db.execute.call_args.args[0]
        rows = stmt.compile().params
        assert rows["indicator_m0"] == "usd_index"
        assert rows["value_m0"] == 104.5
        assert "indicator_m1" not in rows

    def test_preserves_zero_value(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1

        saved = save_macro_data(
            db,
            [{"date": "2024-01-01", "indicator": "fed_rate", "value": 0.0}],
        )

        assert saved == 1
        stmt = db.execute.call_args.args[0]
        row = stmt.compile().params
        assert row["value_m0"] == 0.0

    def test_upserts_by_source_indicator_date(self):
        session = TestGetDataFetchRunsOverview._session()
        try:
            first = save_macro_data(
                session,
                [
                    {
                        "date": "2024-01-01",
                        "indicator": "tips_yield",
                        "value": 1.2,
                        "source": "fred",
                    }
                ],
            )
            updated = save_macro_data(
                session,
                [
                    {
                        "date": "2024-01-01",
                        "indicator": "tips_yield",
                        "value": 1.3,
                        "source": "fred",
                    }
                ],
            )
            other_source = save_macro_data(
                session,
                [
                    {
                        "date": "2024-01-01",
                        "indicator": "tips_yield",
                        "value": 1.4,
                        "source": "yfinance",
                    }
                ],
            )

            from gold_agent.db.models import MacroData

            rows = session.query(MacroData).order_by(MacroData.source).all()

            assert first == 1
            assert updated == 1
            assert other_source == 1
            assert len(rows) == 2
            assert {row.source: row.value for row in rows} == {"fred": 1.3, "yfinance": 1.4}
        finally:
            session.close()


class TestSaveNewsArticles:
    """测试 save_news_articles"""

    def test_saves_new_article(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1
        records = [  # noqa: E501
            {"title": "金价上涨", "link": "http://example.com",
             "source": "google_news", "sentiment_score": 0.5, "sentiment_label": "bullish"},
        ]
        saved = save_news_articles(db, records)
        assert saved == 1
        db.execute.assert_called_once()

    def test_skips_empty_title(self):
        db = MagicMock()
        records = [{"title": "", "link": "http://example.com"}]
        saved = save_news_articles(db, records)
        assert saved == 0

    def test_upserts_duplicate_source_link(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1
        records = [{"title": "金价上涨", "link": "http://example.com", "source": "google_news"}]
        saved = save_news_articles(db, records)
        assert saved == 1
        db.execute.assert_called_once()

    def test_published_date_conversion(self):
        db = MagicMock()
        db.execute.return_value.rowcount = 1
        records = [
            {
                "title": "新闻",
                "published": "2024-01-01",
                "link": "http://example.com/1",
                "source": "google_news",
            }
        ]
        saved = save_news_articles(db, records)
        assert saved == 1
        stmt = db.execute.call_args.args[0]
        row = stmt.compile().params
        assert row["published_date_m0"] is not None

    def test_falls_back_to_title_dedup_when_link_missing(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            None
        )
        records = [{"title": "新闻", "source": "google_news"}]
        saved = save_news_articles(db, records)
        assert saved == 1
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_skips_duplicate_title_when_link_missing(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            MagicMock()
        )
        records = [{"title": "新闻", "source": "google_news"}]
        saved = save_news_articles(db, records)
        assert saved == 0
        db.add.assert_not_called()

    def test_updates_existing_linked_article_without_clobbering_nulls(self):
        session = TestGetDataFetchRunsOverview._session()
        try:
            from gold_agent.db.models import NewsArticle

            first = save_news_articles(
                session,
                [
                    {
                        "title": "旧标题",
                        "published": "2024-01-01",
                        "link": "http://example.com/gold",
                        "source": "google_news",
                        "sentiment_score": 0.2,
                        "sentiment_label": "neutral",
                        "bull_hits": ["gold"],
                        "bear_hits": ["rate"],
                    }
                ],
            )
            updated = save_news_articles(
                session,
                [
                    {
                        "title": "新标题",
                        "link": "http://example.com/gold",
                        "source": "google_news",
                        "sentiment_score": 0.6,
                        "sentiment_label": "bullish",
                    }
                ],
            )

            rows = session.query(NewsArticle).all()

            assert first == 1
            assert updated == 1
            assert len(rows) == 1
            assert rows[0].title == "新标题"
            assert rows[0].sentiment_score == 0.6
            assert rows[0].sentiment_label == "bullish"
            assert rows[0].published_date == datetime(2024, 1, 1)
            assert rows[0].bull_hits == ["gold"]
            assert rows[0].bear_hits == ["rate"]
        finally:
            session.close()


class TestSaveDataFetchRun:
    """测试 save_data_fetch_run"""

    def test_saves_run_record(self):
        db = MagicMock()
        run = {
            "cache_key": "gold_intl_1y",
            "fetcher": "fetch_gold_price",
            "status": "success",
            "record_count": 365,
            "duration_ms": 123.4,
            "error_message": None,
            "started_at": pd.Timestamp("2024-01-01T00:00:00Z").to_pydatetime(),
            "finished_at": pd.Timestamp("2024-01-01T00:00:01Z").to_pydatetime(),
        }

        saved = save_data_fetch_run(db, run)

        assert saved.cache_key == "gold_intl_1y"
        assert saved.status == "success"
        assert saved.record_count == 365
        db.add.assert_called_once()
        db.commit.assert_called_once()


class TestGetDataFetchRunsOverview:
    """测试 get_data_fetch_runs_overview"""

    @staticmethod
    def _session():
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        return sessionmaker(bind=engine)()

    def test_returns_recent_runs_and_summary(self):
        session = self._session()
        try:
            base = datetime(2024, 1, 1, tzinfo=UTC)
            save_data_fetch_run(
                session,
                {
                    "cache_key": "gold_intl_1y",
                    "fetcher": "fetch_gold_price",
                    "status": "success",
                    "record_count": 365,
                    "duration_ms": 100.0,
                    "error_message": None,
                    "started_at": base,
                    "finished_at": base + timedelta(seconds=1),
                },
            )
            save_data_fetch_run(
                session,
                {
                    "cache_key": "macro_yfinance_1y",
                    "fetcher": "fetch_macro_yfinance",
                    "status": "success",
                    "record_count": 250,
                    "duration_ms": 80.0,
                    "error_message": None,
                    "started_at": base + timedelta(minutes=1),
                    "finished_at": base + timedelta(minutes=1, seconds=1),
                },
            )
            save_data_fetch_run(
                session,
                {
                    "cache_key": "gold_intl_1y",
                    "fetcher": "fetch_gold_price",
                    "status": "failure",
                    "record_count": 0,
                    "duration_ms": 300.0,
                    "error_message": "timeout",
                    "started_at": base + timedelta(minutes=2),
                    "finished_at": base + timedelta(minutes=2, seconds=2),
                },
            )
            save_data_fetch_run(
                session,
                {
                    "cache_key": "macro_yfinance_1y",
                    "fetcher": "fetch_macro_yfinance",
                    "status": "persist_failure",
                    "record_count": 250,
                    "duration_ms": 120.0,
                    "error_message": "db locked",
                    "started_at": base + timedelta(minutes=3),
                    "finished_at": base + timedelta(minutes=3, seconds=1),
                },
            )

            overview = get_data_fetch_runs_overview(session, limit=2)

            assert [row["cache_key"] for row in overview["recent"]] == [
                "macro_yfinance_1y",
                "gold_intl_1y",
            ]
            assert overview["recent"][0]["status"] == "persist_failure"

            summary = {row["cache_key"]: row for row in overview["summary"]}
            assert set(summary) == {"gold_intl_1y", "macro_yfinance_1y"}
            assert summary["gold_intl_1y"]["total_runs"] == 2
            assert summary["gold_intl_1y"]["success_count"] == 1
            assert summary["gold_intl_1y"]["failure_count"] == 1
            assert summary["gold_intl_1y"]["success_rate"] == 50.0
            assert summary["gold_intl_1y"]["last_status"] == "failure"
            assert summary["gold_intl_1y"]["last_error_message"] == "timeout"
            assert summary["gold_intl_1y"]["last_record_count"] == 0
            assert summary["gold_intl_1y"]["avg_duration_ms"] == 200.0
            assert summary["macro_yfinance_1y"]["success_count"] == 1
            assert summary["macro_yfinance_1y"]["failure_count"] == 1
            assert summary["macro_yfinance_1y"]["success_rate"] == 50.0
            assert summary["macro_yfinance_1y"]["last_status"] == "persist_failure"
            assert summary["macro_yfinance_1y"]["last_error_message"] == "db locked"
        finally:
            session.close()

    def test_filters_by_cache_key(self):
        session = self._session()
        try:
            base = datetime(2024, 1, 1, tzinfo=UTC)
            save_data_fetch_run(
                session,
                {
                    "cache_key": "gold_intl_1y",
                    "fetcher": "fetch_gold_price",
                    "status": "success",
                    "record_count": 365,
                    "duration_ms": 100.0,
                    "error_message": None,
                    "started_at": base,
                    "finished_at": base + timedelta(seconds=1),
                },
            )
            save_data_fetch_run(
                session,
                {
                    "cache_key": "macro_yfinance_1y",
                    "fetcher": "fetch_macro_yfinance",
                    "status": "success",
                    "record_count": 250,
                    "duration_ms": 80.0,
                    "error_message": None,
                    "started_at": base + timedelta(minutes=1),
                    "finished_at": base + timedelta(minutes=1, seconds=1),
                },
            )

            overview = get_data_fetch_runs_overview(
                session,
                limit=10,
                cache_key="gold_intl_1y",
            )

            assert len(overview["recent"]) == 1
            assert overview["recent"][0]["cache_key"] == "gold_intl_1y"
            assert len(overview["summary"]) == 1
            assert overview["summary"][0]["cache_key"] == "gold_intl_1y"
        finally:
            session.close()


class TestGetTableStats:
    """测试 repository.get_table_stats"""

    def test_get_table_stats_delegates(self):
        """委托给 models.get_table_stats（覆盖 lines 171-172）"""
        from gold_agent.db.repository import get_table_stats
        db = MagicMock()
        result = get_table_stats(db)
        # Should return a dict with table names
        assert isinstance(result, dict)
        assert len(result) > 0
