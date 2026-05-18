"""辩论接口单元测试 — /api/debate/*"""

from unittest.mock import AsyncMock, MagicMock, patch

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


def _fake_debate_result():
    result = MagicMock()
    result.to_summary.return_value = "Debate summary text"
    result.to_dict.return_value = {
        "bull": {"confidence": 70, "arguments": []},
        "bear": {"confidence": 60, "arguments": []},
        "audit": {"overall_assessment": "Good"},
        "verdict": {"verdict": "bullish"},
    }
    return result


# ============================================================
# POST /api/debate/run
# ============================================================


class TestDebateRun:
    """完整辩论流程"""

    @patch("gold_agent.api.debate.DebateEngine")
    @patch("gold_agent.api.debate.fetch_news_with_sentiment")
    @patch("gold_agent.api.debate.fetch_macro_yfinance")
    @patch("gold_agent.api.debate.get_prediction_summary")
    @patch("gold_agent.api.debate.predict_gold_price")
    @patch("gold_agent.api.debate.get_signal_summary")
    @patch("gold_agent.api.debate.generate_signal")
    @patch("gold_agent.api.debate.get_indicator_summary")
    @patch("gold_agent.api.debate.cache.get")
    def test_run_debate_success(
        self,
        mock_cache_get,
        mock_indicator_summary,
        mock_generate_signal,
        mock_signal_summary,
        mock_predict,
        mock_pred_summary,
        mock_macro,
        mock_news,
        mock_engine_cls,
    ):
        # Arrange: _build_context infrastructure
        mock_cache_get.return_value = _fake_ohlcv()
        mock_indicator_summary.return_value = "### 国际金价\nMA20: 2000"
        mock_generate_signal.return_value = MagicMock()
        mock_signal_summary.return_value = "### 信号: 中性"
        mock_predict.return_value = _fake_prediction()
        mock_pred_summary.return_value = "### 预测: 看涨"
        mock_macro.return_value = _fake_macro()
        mock_news.return_value = _fake_news()

        # Arrange: DebateEngine
        mock_engine = MagicMock()
        mock_engine.run_debate = AsyncMock()
        mock_engine.run_debate.return_value = _fake_debate_result()
        mock_engine_cls.return_value = mock_engine

        # Act
        resp = client.post("/api/debate/run")

        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "detail" in data
        assert data["summary"] == "Debate summary text"
        assert data["detail"]["verdict"]["verdict"] == "bullish"
        mock_engine.run_debate.assert_awaited_once()

    @patch("gold_agent.api.debate.DebateEngine")
    @patch("gold_agent.api.debate.fetch_news_with_sentiment")
    @patch("gold_agent.api.debate.fetch_macro_yfinance")
    @patch("gold_agent.api.debate.get_prediction_summary")
    @patch("gold_agent.api.debate.predict_gold_price")
    @patch("gold_agent.api.debate.get_signal_summary")
    @patch("gold_agent.api.debate.generate_signal")
    @patch("gold_agent.api.debate.get_indicator_summary")
    @patch("gold_agent.api.debate.cache.get")
    def test_run_debate_error(
        self,
        mock_cache_get,
        mock_indicator_summary,
        mock_generate_signal,
        mock_signal_summary,
        mock_predict,
        mock_pred_summary,
        mock_macro,
        mock_news,
        mock_engine_cls,
    ):
        # Arrange: _build_context can still fail gracefully
        mock_cache_get.side_effect = ValueError("cache unavailable")
        # Provide defaults so _build_context doesn't crash on NameError
        mock_indicator_summary.return_value = ""
        mock_signal_summary.return_value = ""
        mock_pred_summary.return_value = ""
        mock_macro.return_value = _fake_macro()
        mock_news.return_value = _fake_news()

        # Arrange: DebateEngine.run_debate raises
        mock_engine = MagicMock()
        mock_engine.run_debate = AsyncMock()
        mock_engine.run_debate.side_effect = RuntimeError("LLM API failed")
        mock_engine_cls.return_value = mock_engine

        resp = client.post("/api/debate/run")

        assert resp.status_code == 500
        assert "LLM API failed" in resp.json()["detail"]


# ============================================================
# GET /api/debate/quick
# ============================================================


class TestDebateQuick:
    """快速分析"""

    @patch("gold_agent.api.debate.get_indicator_summary", return_value="indicator text")
    @patch("gold_agent.api.debate.generate_signal")
    @patch("gold_agent.api.debate.cache.get")
    def test_quick_analysis_success(self, mock_cache_get, mock_generate, mock_summary):
        mock_cache_get.return_value = _fake_ohlcv()
        mock_signal = MagicMock()
        mock_signal.to_dict.return_value = {
            "signal": "buy", "score": 30.0, "confidence": 0.6,
            "reasons": ["MA5 > MA20"], "stop_loss": 1950.0, "take_profit": 2100.0,
        }
        mock_generate.return_value = mock_signal

        resp = client.get("/api/debate/quick")
        assert resp.status_code == 200
        data = resp.json()
        assert data["signal"]["signal"] == "buy"
        assert data["indicators"] == "indicator text"
