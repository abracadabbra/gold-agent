"""分析接口单元测试 — /api/analysis/*"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from gold_agent.data.gold_price import gold_cache_key
from gold_agent.data.macro import macro_fred_cache_key, macro_yfinance_cache_key
from gold_agent.main import app

client = TestClient(app)


def _meta(row_count: int, source_status: str = "cache") -> dict:
    return {
        "as_of": "2024-01-10T00:00:00",
        "latest_date": "2024-01-10T00:00:00",
        "fetched_at": "2024-01-10T08:00:00+00:00",
        "row_count": row_count,
        "stale": False,
        "source_status": source_status,
        "missing_rate": 0.0,
        "quality_score": 100,
        "expected_frequency": "daily",
    }


def _fake_ohlcv():
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "open": [2000.0] * 10,
        "high": [2010.0] * 10,
        "low": [1990.0] * 10,
        "close": [2005.0] * 10,
        "volume": [10000] * 10,
    })


def _fake_macro():
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=5, freq="D"),
        "usd_index": [104.0] * 5,
        "vix": [15.0] * 5,
        "us_10y": [4.2] * 5,
    })


def _fake_macro_with_future():
    return pd.DataFrame({
        "date": pd.to_datetime([
            "2024-01-08",
            "2024-01-09",
            "2024-01-10",
            "2024-01-11",
            "2024-01-12",
        ]),
        "usd_index": [104.0, 104.1, 104.2, 104.3, 104.4],
        "vix": [15.0, 15.1, 15.2, 15.3, 15.4],
        "us_10y": [4.2, 4.21, 4.22, 4.23, 4.24],
    })


def _fake_news():
    return pd.DataFrame({
        "title": ["Gold prices surge", "Rate cut expected"],
        "sentiment_score": [0.5, -0.1],
        "sentiment_label": ["bullish", "slight_bearish"],
        "url": ["http://example.com/1", "http://example.com/2"],
    })


def _fake_prediction():
    forecast = pd.DataFrame({
        "date": pd.date_range("2024-04-01", periods=7, freq="D"),
        "predicted": [2010.0] * 7,
        "lower_bound": [1990.0] * 7,
        "upper_bound": [2030.0] * 7,
    })
    return {
        "forecast": forecast,
        "trend": 2008.0,
        "trend_direction": "up",
        "changepoints": ["2024-03-01"],
        "components": {"trend": 2008.0},
    }


# ============================================================
# /api/analysis/gold
# ============================================================


class TestAnalysisGold:
    """金价数据端点"""

    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_gold_price_success(self, mock_cache_get_with_meta):
        mock_cache_get_with_meta.return_value = (_fake_ohlcv(), _meta(10))

        resp = client.get("/api/analysis/gold?source=intl&period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "intl"
        assert data["records"] == 10
        assert data["latest_price"] == 2005.0
        assert len(data["data"]) == 10
        assert data["meta"]["row_count"] == 10
        assert data["meta"]["source_status"] == "cache"
        mock_cache_get_with_meta.assert_called_once()
        _, kwargs = mock_cache_get_with_meta.call_args
        assert kwargs["key"] == "gold_intl_1y"
        assert kwargs["period"] == "1y"
        assert kwargs["months"] == 12

    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_gold_price_period_specific_cache_key(self, mock_cache_get_with_meta):
        mock_cache_get_with_meta.return_value = (_fake_ohlcv(), _meta(10))

        resp = client.get("/api/analysis/gold?source=intl&period=1mo")

        assert resp.status_code == 200
        _, kwargs = mock_cache_get_with_meta.call_args
        assert kwargs["key"] == "gold_intl_1mo"
        assert kwargs["period"] == "1mo"
        assert kwargs["months"] == 1

    @patch("gold_agent.api.analysis._load_gold_from_db", return_value=(pd.DataFrame(), None))
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_gold_price_error(self, mock_cache_get_with_meta, mock_load_gold_from_db):
        mock_cache_get_with_meta.side_effect = ValueError("data source unavailable")

        resp = client.get("/api/analysis/gold?source=intl&period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "intl"
        assert data["records"] == 0
        assert data["latest_price"] is None
        assert data["meta"]["source_status"] == "unavailable"
        assert data["meta"]["quality_score"] == 0
        assert mock_cache_get_with_meta.call_count == 2
        assert mock_load_gold_from_db.call_count == 2

    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_gold_price_primary_error_uses_fallback(self, mock_cache_get_with_meta):
        def side_effect(key, **kwargs):
            if key == gold_cache_key("intl", "1y"):
                raise ValueError("intl unavailable")
            if key == gold_cache_key("shfe", "1y"):
                return _fake_ohlcv(), _meta(10, source_status="live")
            raise AssertionError(f"unexpected key: {key}")

        mock_cache_get_with_meta.side_effect = side_effect

        resp = client.get("/api/analysis/gold?source=intl&period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "shfe"
        assert data["records"] == 10
        assert data["meta"]["source_status"] == "live"

    @patch("gold_agent.api.analysis._load_gold_from_db")
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_gold_price_db_fallback_meta_uses_db_timestamp(
        self,
        mock_cache_get_with_meta,
        mock_load_gold_from_db,
    ):
        mock_cache_get_with_meta.return_value = (pd.DataFrame(), _meta(0, "unavailable"))
        db_cached_at = datetime(2024, 1, 11, 9, 15, tzinfo=UTC)
        mock_load_gold_from_db.return_value = (_fake_ohlcv(), db_cached_at)

        resp = client.get("/api/analysis/gold?source=intl&period=1y")

        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["source_status"] == "db_fallback"
        assert data["meta"]["fetched_at"] == db_cached_at.isoformat()
        assert data["meta"]["cached_at"] == db_cached_at.isoformat()


# ============================================================
# /api/analysis/indicators
# ============================================================


class TestAnalysisIndicators:
    """技术指标端点"""

    @patch("gold_agent.api.analysis.get_indicator_summary", return_value="indicator summary text")
    @patch("gold_agent.api.analysis.compute_indicators")
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_indicators_success(
        self, mock_cache_get_with_meta, mock_compute, mock_summary,
    ):
        mock_cache_get_with_meta.return_value = (_fake_ohlcv(), _meta(10))
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"ma20": 2000.0, "rsi14": 55.0}
        mock_compute.return_value = mock_result

        resp = client.get("/api/analysis/indicators?source=intl&period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["price"] == 2005.0
        assert data["indicators"] == {"ma20": 2000.0, "rsi14": 55.0}
        assert data["summary"] == "indicator summary text"
        assert data["meta"]["row_count"] == 10
        assert data["indicator_meta"]["row_count"] == 1
        assert data["indicator_meta"]["available_indicators"] == 2
        assert data["indicator_meta"]["warmup_required_days"] == 60
        assert data["indicator_meta"]["warmup_satisfied"] is False


# ============================================================
# /api/analysis/signal
# ============================================================


class TestAnalysisSignal:
    """交易信号端点"""

    @patch("gold_agent.api.analysis.get_signal_summary", return_value="signal summary text")
    @patch("gold_agent.api.analysis.generate_signal")
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_signal_success(
        self,
        mock_cache_get_with_meta,
        mock_generate,
        mock_summary,
    ):
        mock_cache_get_with_meta.side_effect = [
            (_fake_ohlcv(), _meta(10)),
            (pd.DataFrame(), _meta(0, "unavailable")),
        ]
        mock_signal = MagicMock()
        mock_signal.to_dict.return_value = {
            "signal": "neutral", "score": 0.0, "confidence": 0.5,
            "reasons": ["test reason"], "stop_loss": 1900.0, "take_profit": 2100.0,
        }
        mock_generate.return_value = mock_signal

        resp = client.get("/api/analysis/signal?source=intl&period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["signal"]["signal"] == "neutral"
        assert data["summary"] == "signal summary text"
        assert data["meta"]["row_count"] == 10
        assert data["macro_factors_meta"]["source_status"] == "unavailable"
        assert data["evaluation"]["sample_size"] == 0
        assert data["evaluation"]["hit_rate"] is None
        assert data["evaluation_meta"]["row_count"] == 0
        assert data["evaluation_meta"]["sample_satisfied"] is False
        assert data["evaluation_meta"]["directional_satisfied"] is False
        assert data["evaluation_meta"]["quality_score"] == 50

    @patch("gold_agent.api.analysis.get_signal_summary", return_value="signal summary text")
    @patch("gold_agent.api.analysis.generate_signal")
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_signal_with_macro_factors(
        self, mock_cache_get_with_meta, mock_generate, mock_summary,
    ):
        """信号端点包含宏观因子 tips_yield（覆盖 lines 100-103）"""
        def side_effect(key, **kwargs):
            if key == macro_fred_cache_key(start_date="2024-01-01"):
                return pd.DataFrame({
                    "date": pd.date_range("2024-01-01", periods=3, freq="D"),
                    "tips_yield": [1.5, 1.6, 1.7],
                }), _meta(3, "live")
            return _fake_ohlcv(), _meta(10)

        mock_cache_get_with_meta.side_effect = side_effect
        mock_signal = MagicMock()
        mock_signal.to_dict.return_value = {
            "signal": "neutral", "score": 0.0, "confidence": 0.5,
            "reasons": ["test reason"], "stop_loss": 1900.0, "take_profit": 2100.0,
        }
        mock_generate.return_value = mock_signal

        resp = client.get("/api/analysis/signal?source=intl&period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["macro_factors"] == {
            "tips_yield": 1.7,
            "aligned_as_of": "2024-01-03T00:00:00",
            "lag_days": 7,
        }
        assert data["macro_factors_meta"]["source_status"] == "live"
        assert data["macro_factors_meta"]["row_count"] == 3
        assert data["evaluation_meta"]["min_required_samples"] == 30
        assert data["evaluation_meta"]["min_required_directional_samples"] == 10

    @patch("gold_agent.api.analysis.get_signal_summary", return_value="signal summary text")
    @patch("gold_agent.api.analysis.generate_signal")
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_signal_with_as_of_override(
        self, mock_cache_get_with_meta, mock_generate, mock_summary,
    ):
        def side_effect(key, **kwargs):
            if key == macro_fred_cache_key(start_date="2024-01-01"):
                return pd.DataFrame({
                    "date": pd.date_range("2024-01-01", periods=3, freq="D"),
                    "tips_yield": [1.5, 1.6, 1.7],
                }), _meta(3, "live")
            return _fake_ohlcv(), _meta(10)

        mock_cache_get_with_meta.side_effect = side_effect
        mock_signal = MagicMock()
        mock_signal.to_dict.return_value = {
            "signal": "neutral", "score": 0.0, "confidence": 0.5,
            "reasons": ["test reason"], "stop_loss": 1900.0, "take_profit": 2100.0,
        }
        mock_generate.return_value = mock_signal

        resp = client.get("/api/analysis/signal?source=intl&period=1y&as_of=2024-01-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["macro_factors"] == {
            "tips_yield": 1.6,
            "aligned_as_of": "2024-01-02T00:00:00",
            "lag_days": 0,
        }
        assert data["macro_factors_meta"]["source_status"] == "live"
        assert data["evaluation_meta"]["source_status"] == "cache"

    @patch("gold_agent.api.analysis.get_signal_summary", return_value="signal summary text")
    @patch("gold_agent.api.analysis.generate_signal")
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_signal_fred_fails(
        self, mock_cache_get_with_meta, mock_generate, mock_summary,
    ):
        """FRED 数据获取失败时信号不包含宏观因子（覆盖 lines 102-103）"""
        def side_effect(key, **kwargs):
            if key == macro_fred_cache_key(start_date="2024-01-01"):
                raise ValueError("FRED API unavailable")
            return _fake_ohlcv(), _meta(10)

        mock_cache_get_with_meta.side_effect = side_effect
        mock_signal = MagicMock()
        mock_signal.to_dict.return_value = {
            "signal": "neutral", "score": 0.0, "confidence": 0.5,
            "reasons": ["test reason"], "stop_loss": 1900.0, "take_profit": 2100.0,
        }
        mock_generate.return_value = mock_signal

        resp = client.get("/api/analysis/signal?source=intl&period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["macro_factors"] is None
        assert data["macro_factors_meta"] is None
        assert data["evaluation_meta"]["row_count"] == 0


# ============================================================
# /api/analysis/predict
# ============================================================


class TestAnalysisPredict:
    """预测端点"""

    @patch("gold_agent.api.analysis.get_prediction_summary", return_value="prediction summary text")
    @patch("gold_agent.api.analysis.predict_gold_price")
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_predict_success(
        self, mock_cache_get_with_meta, mock_predict, mock_summary,
    ):
        def side_effect(key, **kwargs):
            if key == macro_yfinance_cache_key(period="2y"):
                return _fake_macro_with_future(), _meta(5, "live")
            return _fake_ohlcv(), _meta(10)

        mock_cache_get_with_meta.side_effect = side_effect
        mock_predict.return_value = _fake_prediction()

        resp = client.get("/api/analysis/predict?source=intl&days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["prediction"]) == 7
        assert data["trend"] == "up"
        assert data["summary"] == "prediction summary text"
        assert data["meta"]["row_count"] == 10
        assert data["regressor_meta"]["source_status"] == "live"
        assert data["regressor_meta"]["row_count"] == 5
        assert data["regressor_alignment"] == {
            "usd_index": {"aligned_as_of": "2024-01-10T00:00:00", "lag_days": 0},
            "vix": {"aligned_as_of": "2024-01-10T00:00:00", "lag_days": 0},
            "us_10y": {"aligned_as_of": "2024-01-10T00:00:00", "lag_days": 0},
        }
        assert data["evaluation"]["baseline"] == "naive_last_value"
        assert data["evaluation"]["sample_size"] > 0
        assert data["evaluation"]["mae"] is not None
        assert data["evaluation_meta"]["sample_size"] == data["evaluation"]["sample_size"]
        assert data["evaluation_meta"]["min_required_samples"] == 30
        assert data["evaluation_meta"]["baseline_count"] == 3
        assert data["evaluation_meta"]["sample_satisfied"] is False
        assert data["evaluation_meta"]["conclusion_suitable"] is False
        assert [item["baseline"] for item in data["evaluation"]["baselines"]] == [
            "naive_last_value",
            "moving_average",
            "linear_trend",
        ]
        assert "disclaimer" in data
        assert isinstance(data["disclaimer"], str)
        assert len(data["disclaimer"]) > 10
        regressors = mock_predict.call_args.kwargs["regressors"]
        assert list(regressors["usd_index"].index.astype(str)) == [
            "2024-01-08",
            "2024-01-09",
            "2024-01-10",
        ]

    @patch("gold_agent.api.analysis.get_prediction_summary", return_value="prediction summary text")
    @patch("gold_agent.api.analysis.predict_gold_price")
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_predict_with_ds_column(
        self, mock_cache_get_with_meta, mock_predict, mock_summary,
    ):
        """预测 forecast 包含 ds 列（覆盖 line 153）"""
        def side_effect(key, **kwargs):
            if key == macro_yfinance_cache_key(period="2y"):
                return _fake_macro_with_future(), _meta(5, "live")
            return _fake_ohlcv(), _meta(10)

        mock_cache_get_with_meta.side_effect = side_effect
        forecast = pd.DataFrame({
            "ds": pd.date_range("2024-04-01", periods=5, freq="D"),
            "yhat": [2010.0] * 5,
            "yhat_lower": [1990.0] * 5,
            "yhat_upper": [2030.0] * 5,
        })
        mock_predict.return_value = {
            "forecast": forecast,
            "trend": 2008.0,
            "trend_direction": "up",
            "changepoints": [],
            "components": {},
        }

        resp = client.get("/api/analysis/predict?source=intl&days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["prediction"]) == 5
        assert data["prediction"][0]["ds"] is not None


# ============================================================
# /api/analysis/macro
# ============================================================


class TestAnalysisMacro:
    """宏观数据端点"""

    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_macro_success(self, mock_cache_get_with_meta):
        macro = _fake_macro()

        def side_effect(key, **kwargs):
            if key.startswith("macro_yfinance"):
                return macro, _meta(5)
            if key == macro_fred_cache_key(start_date="2020-01-01"):
                return macro, _meta(5, source_status="live")
            return pd.DataFrame(), _meta(0, source_status="unavailable")

        mock_cache_get_with_meta.side_effect = side_effect

        resp = client.get("/api/analysis/macro?period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["realtime"]["records"] == 5
        assert "usd_index" in data["realtime"]["columns"]
        assert len(data["realtime"]["data"]) == 5
        assert data["realtime"]["meta"]["row_count"] == 5
        assert data["official"]["meta"]["source_status"] == "live"
        calls = [call.kwargs["key"] for call in mock_cache_get_with_meta.call_args_list]
        assert macro_fred_cache_key(start_date="2020-01-01") in calls

    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_macro_empty_fred(self, mock_cache_get_with_meta):
        """macro 端点中 FRED 返回空（覆盖 _format empty 分支）"""
        macro = _fake_macro()

        def side_effect(key, **kwargs):
            if key.startswith("macro_yfinance"):
                return macro, _meta(5)
            if key == macro_fred_cache_key(start_date="2020-01-01"):
                return pd.DataFrame(), _meta(0, source_status="unavailable")
            return pd.DataFrame(), _meta(0, source_status="unavailable")

        mock_cache_get_with_meta.side_effect = side_effect

        resp = client.get("/api/analysis/macro?period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["realtime"]["records"] == 5
        assert data["official"]["records"] == 0
        assert data["official"]["columns"] == []
        assert data["official"]["data"] == []
        assert data["official"]["meta"]["source_status"] == "unavailable"

    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_macro_realtime_error_keeps_official_data(self, mock_cache_get_with_meta):
        macro = _fake_macro()

        def side_effect(key, **kwargs):
            if key.startswith("macro_yfinance"):
                raise ValueError("yfinance unavailable")
            if key == macro_fred_cache_key(start_date="2020-01-01"):
                return macro, _meta(5, source_status="live")
            return pd.DataFrame(), _meta(0, source_status="unavailable")

        mock_cache_get_with_meta.side_effect = side_effect

        resp = client.get("/api/analysis/macro?period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["realtime"]["records"] == 0
        assert data["realtime"]["meta"]["source_status"] == "unavailable"
        assert data["realtime"]["meta"]["quality_score"] == 0
        assert data["official"]["records"] == 5
        assert data["official"]["meta"]["source_status"] == "live"
        assert data["meta"]["available_count"] == 1
        assert data["meta"]["coverage_satisfied"] is False


# ============================================================
# /api/analysis/news
# ============================================================


class TestAnalysisErrorPaths:
    """各端点异常路径"""

    @patch("gold_agent.api.analysis._load_gold_from_db", return_value=(pd.DataFrame(), None))
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_indicators_error(self, mock_cache_get_with_meta, mock_load_gold_from_db):
        mock_cache_get_with_meta.side_effect = ValueError("cache error")
        resp = client.get("/api/analysis/indicators")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unavailable"] is True
        assert data["meta"]["source_status"] == "unavailable"
        assert "indicator_meta" not in data
        assert mock_load_gold_from_db.call_count == 2

    @patch("gold_agent.api.analysis._load_gold_from_db", return_value=(pd.DataFrame(), None))
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_signal_error(self, mock_cache_get_with_meta, mock_load_gold_from_db):
        mock_cache_get_with_meta.side_effect = ValueError("cache error")
        resp = client.get("/api/analysis/signal")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unavailable"] is True
        assert data["meta"]["source_status"] == "unavailable"
        assert data["macro_factors_meta"] is None
        assert data["evaluation_meta"] is None
        assert mock_load_gold_from_db.call_count == 2

    @patch("gold_agent.api.analysis._load_gold_from_db", return_value=(pd.DataFrame(), None))
    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_predict_error(self, mock_cache_get_with_meta, mock_load_gold_from_db):
        mock_cache_get_with_meta.side_effect = ValueError("cache error")
        resp = client.get("/api/analysis/predict")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unavailable"] is True
        assert data["meta"]["source_status"] == "unavailable"
        assert data["regressor_meta"] is None
        assert data["evaluation_meta"] is None
        assert mock_load_gold_from_db.call_count == 2

    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_macro_error(self, mock_cache_get_with_meta):
        mock_cache_get_with_meta.side_effect = ValueError("cache error")
        resp = client.get("/api/analysis/macro")
        assert resp.status_code == 200
        data = resp.json()
        assert data["realtime"]["meta"]["source_status"] == "unavailable"
        assert data["official"]["meta"]["source_status"] == "unavailable"
        assert data["meta"]["available_count"] == 0
        assert data["meta"]["coverage_satisfied"] is False
        assert data["meta"]["quality_score"] == 0

    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_news_error(self, mock_cache_get_with_meta):
        mock_cache_get_with_meta.side_effect = ValueError("cache error")
        resp = client.get("/api/analysis/news")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unavailable"] is True
        assert data["total"] == 0
        assert data["news"] == []
        assert data["label"] == "neutral"
        assert data["meta"]["source_status"] == "unavailable"
        assert data["meta"]["quality_score"] == 0
        assert data["meta"]["conclusion_suitable"] is False
        assert "cache error" in data["error"]


class TestAnalysisNews:
    """新闻情绪端点"""

    @patch("gold_agent.api.analysis.cache.get_with_meta")
    def test_get_news_success(self, mock_cache_get_with_meta):
        mock_cache_get_with_meta.return_value = (_fake_news(), _meta(2))

        resp = client.get("/api/analysis/news")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["avg_sentiment"] == 0.2  # (0.5 + -0.1) / 2
        assert data["label"] == "neutral"  # 0.2 is not > 0.2
        assert len(data["news"]) == 2
        assert data["meta"]["row_count"] == 2
        _, kwargs = mock_cache_get_with_meta.call_args
        assert kwargs["key"] == "news_sentiment"
        assert kwargs["expected_frequency"] == "intraday"
        assert callable(kwargs["db_save_fn"])


class TestAnalysisFetchRuns:
    """抓取运行状态端点"""

    @patch("gold_agent.api.analysis.get_data_fetch_runs_overview")
    @patch("gold_agent.api.analysis.SessionLocal")
    def test_get_fetch_runs_success(self, mock_session_local, mock_get_overview):
        mock_session_local.return_value.__enter__.return_value = MagicMock()
        mock_get_overview.return_value = {
            "recent": [
                {
                    "id": 3,
                    "cache_key": "gold_intl_1y",
                    "fetcher": "fetch_gold_price",
                    "status": "failure",
                    "record_count": 0,
                    "duration_ms": 300.0,
                    "error_message": "timeout",
                    "started_at": "2024-01-01T00:02:00+00:00",
                    "finished_at": "2024-01-01T00:02:02+00:00",
                    "created_at": "2024-01-01T00:02:02+00:00",
                }
            ],
            "summary": [
                {
                    "cache_key": "gold_intl_1y",
                    "fetcher": "fetch_gold_price",
                    "total_runs": 2,
                    "success_count": 1,
                    "failure_count": 1,
                    "success_rate": 50.0,
                    "avg_duration_ms": 200.0,
                    "last_status": "failure",
                    "last_error_message": "timeout",
                    "last_record_count": 0,
                    "last_started_at": "2024-01-01T00:02:00+00:00",
                    "last_finished_at": "2024-01-01T00:02:02+00:00",
                }
            ],
        }

        resp = client.get("/api/analysis/fetch-runs?limit=5&cache_key=gold_intl_1y")

        assert resp.status_code == 200
        data = resp.json()
        assert data["filters"] == {"limit": 5, "cache_key": "gold_intl_1y"}
        assert data["recent"][0]["status"] == "failure"
        assert data["summary"][0]["success_rate"] == 50.0
        _, kwargs = mock_get_overview.call_args
        assert kwargs["limit"] == 5
        assert kwargs["cache_key"] == "gold_intl_1y"

    @patch("gold_agent.api.analysis.get_data_fetch_runs_overview")
    @patch("gold_agent.api.analysis.SessionLocal")
    def test_get_fetch_runs_error(self, mock_session_local, mock_get_overview):
        mock_session_local.return_value.__enter__.return_value = MagicMock()
        mock_get_overview.side_effect = ValueError("db unavailable")

        resp = client.get("/api/analysis/fetch-runs")

        assert resp.status_code == 200
        data = resp.json()
        assert data["recent"] == []
        assert data["summary"] == []
        assert data["filters"] == {"limit": 20, "cache_key": None}
        assert data["source_status"] == "unavailable"
        assert data["unavailable"] is True
        assert "db unavailable" in data["error"]
