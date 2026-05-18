"""分析接口单元测试 — /api/analysis/*"""

from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from gold_agent.main import app

client = TestClient(app)


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

    @patch("gold_agent.api.analysis.cache.get")
    def test_get_gold_price_success(self, mock_cache_get):
        mock_cache_get.return_value = _fake_ohlcv()

        resp = client.get("/api/analysis/gold?source=intl&period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "intl"
        assert data["records"] == 10
        assert data["latest_price"] == 2005.0
        assert len(data["data"]) == 10

    @patch("gold_agent.api.analysis.cache.get")
    def test_get_gold_price_error(self, mock_cache_get):
        mock_cache_get.side_effect = ValueError("data source unavailable")

        resp = client.get("/api/analysis/gold?source=intl&period=1y")
        assert resp.status_code == 500
        assert "data source unavailable" in resp.json()["detail"]


# ============================================================
# /api/analysis/indicators
# ============================================================


class TestAnalysisIndicators:
    """技术指标端点"""

    @patch("gold_agent.api.analysis.get_indicator_summary", return_value="indicator summary text")
    @patch("gold_agent.api.analysis.compute_indicators")
    @patch("gold_agent.api.analysis.cache.get")
    def test_get_indicators_success(
        self, mock_cache_get, mock_compute, mock_summary,
    ):
        mock_cache_get.return_value = _fake_ohlcv()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"ma20": 2000.0, "rsi14": 55.0}
        mock_compute.return_value = mock_result

        resp = client.get("/api/analysis/indicators?source=intl&period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["price"] == 2005.0
        assert data["indicators"] == {"ma20": 2000.0, "rsi14": 55.0}
        assert data["summary"] == "indicator summary text"


# ============================================================
# /api/analysis/signal
# ============================================================


class TestAnalysisSignal:
    """交易信号端点"""

    @patch("gold_agent.api.analysis.get_signal_summary", return_value="signal summary text")
    @patch("gold_agent.api.analysis.generate_signal")
    @patch("gold_agent.api.analysis.cache.get")
    def test_get_signal_success(self, mock_cache_get, mock_generate, mock_summary):
        mock_cache_get.return_value = _fake_ohlcv()
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


# ============================================================
# /api/analysis/predict
# ============================================================


class TestAnalysisPredict:
    """预测端点"""

    @patch("gold_agent.api.analysis.get_prediction_summary", return_value="prediction summary text")
    @patch("gold_agent.api.analysis.predict_gold_price")
    @patch("gold_agent.api.analysis.fetch_macro_yfinance")
    @patch("gold_agent.api.analysis.cache.get")
    def test_get_predict_success(
        self, mock_cache_get, mock_macro, mock_predict, mock_summary,
    ):
        mock_cache_get.return_value = _fake_ohlcv()
        mock_macro.return_value = _fake_macro()
        mock_predict.return_value = _fake_prediction()

        resp = client.get("/api/analysis/predict?source=intl&days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["prediction"]) == 7
        assert data["trend"] == "up"
        assert data["summary"] == "prediction summary text"


# ============================================================
# /api/analysis/macro
# ============================================================


class TestAnalysisMacro:
    """宏观数据端点"""

    @patch("gold_agent.api.analysis.cache.get")
    def test_get_macro_success(self, mock_cache_get):
        mock_cache_get.return_value = _fake_macro()

        resp = client.get("/api/analysis/macro?period=1y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["records"] == 5
        assert "usd_index" in data["columns"]
        assert len(data["data"]) == 5


# ============================================================
# /api/analysis/news
# ============================================================


class TestAnalysisNews:
    """新闻情绪端点"""

    @patch("gold_agent.api.analysis.fetch_news_with_sentiment")
    def test_get_news_success(self, mock_news):
        mock_news.return_value = _fake_news()

        resp = client.get("/api/analysis/news")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["avg_sentiment"] == 0.2  # (0.5 + -0.1) / 2
        assert data["label"] == "neutral"  # 0.2 is not > 0.2
        assert len(data["news"]) == 2
