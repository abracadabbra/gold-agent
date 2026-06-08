"""辩论接口单元测试 — /api/debate/*"""

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from gold_agent.main import app

client = TestClient(app)


def _meta(
    row_count: int,
    *,
    source_status: str = "cache",
    stale: bool = False,
    quality_score: int = 90,
    expected_frequency: str = "daily",
    fetched_at: str = "2024-01-10T08:00:00+00:00",
    cached_at: str | None = None,
) -> dict:
    return {
        "as_of": "2024-01-10T00:00:00",
        "latest_date": "2024-01-10T00:00:00",
        "fetched_at": fetched_at,
        "cached_at": cached_at,
        "row_count": row_count,
        "stale": stale,
        "source_status": source_status,
        "missing_rate": 0.0,
        "quality_score": quality_score,
        "expected_frequency": expected_frequency,
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
    @patch("gold_agent.api.debate.get_indicator_summary")
    @patch("gold_agent.api.debate.get_signal_summary")
    @patch("gold_agent.api.debate.generate_signal")
    @patch("gold_agent.api.debate.build_factor_snapshot", new_callable=AsyncMock)
    @patch("gold_agent.api.debate.cache.get_with_meta")
    def test_run_debate_success(
        self,
        mock_cache_get_with_meta,
        mock_build_factor_snapshot,
        mock_generate_signal,
        mock_signal_summary,
        mock_indicator_summary,
        mock_predict,
        mock_pred_summary,
        mock_fetch_macro,
        mock_fetch_news,
        mock_engine_cls,
    ):
        # Arrange: _build_context infrastructure
        def _cache_side_effect(*_, **kwargs):
            key = kwargs["key"]
            if key.startswith("gold_"):
                return (
                    _fake_ohlcv(),
                    _meta(
                        10,
                        cached_at="2024-01-10T07:55:00+00:00",
                    ),
                )
            if key.startswith("macro_yfinance_"):
                return (_fake_macro(), _meta(5, source_status="live"))
            if key.startswith("macro_fred_"):
                return (_fake_macro(), _meta(5, expected_frequency="mixed"))
            if key == "news_sentiment":
                return (_fake_news(), _meta(2, expected_frequency="intraday"))
            raise AssertionError(f"unexpected cache key: {key}")

        mock_cache_get_with_meta.side_effect = _cache_side_effect
        mock_build_factor_snapshot.return_value = {
            "meta": {
                **_meta(5, expected_frequency="mixed"),
                "available_count": 3,
                "min_required_available": 3,
                "coverage_satisfied": True,
                "max_lag_days": 1,
            },
            "cot": {
                "label": "中性",
                "aligned_as_of": "2024-01-10T00:00:00",
                "lag_days": 0,
            },
        }
        mock_indicator_summary.return_value = "### 国际金价\nMA20: 2000"
        mock_generate_signal.return_value = MagicMock()
        mock_signal_summary.return_value = "### 信号: 中性"
        mock_predict.return_value = _fake_prediction()
        mock_pred_summary.return_value = "### 预测: 看涨"

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
        assert data["meta"]["gold"]["source_status"] == "cache"
        assert data["meta"]["macro"]["source_status"] == "cache"
        assert data["meta"]["news"]["expected_frequency"] == "intraday"
        assert data["meta"]["factors"]["coverage_satisfied"] is True
        assert data["summary"] == "Debate summary text"
        assert data["detail"]["verdict"]["verdict"] == "bullish"
        mock_engine.run_debate.assert_awaited_once()
        context = mock_engine.run_debate.await_args.args[0]
        assert "source_status=cache" in context
        assert "quality_score=90" in context
        assert "新闻情绪" in context
        assert "关键因子快照" in context
        assert "数据使用约束" in context
        assert "cached_at=2024-01-10T07:55:00+00:00" in context
        assert "fetched_at=2024-01-10T08:00:00+00:00" in context
        assert "需要优先查看 cached_at 与 as_of" in context

    @patch("gold_agent.api.debate.DebateEngine")
    @patch("gold_agent.api.debate.get_prediction_summary")
    @patch("gold_agent.api.debate.predict_gold_price")
    @patch("gold_agent.api.debate.get_indicator_summary")
    @patch("gold_agent.api.debate.get_signal_summary")
    @patch("gold_agent.api.debate.generate_signal")
    @patch("gold_agent.api.debate.cache.get_with_meta")
    def test_run_debate_error(
        self,
        mock_cache_get_with_meta,
        mock_generate_signal,
        mock_signal_summary,
        mock_indicator_summary,
        mock_predict,
        mock_pred_summary,
        mock_engine_cls,
    ):
        # Arrange: _build_context can still fail gracefully
        mock_cache_get_with_meta.side_effect = ValueError("cache unavailable")
        # Provide defaults so _build_context doesn't crash on NameError
        mock_indicator_summary.return_value = ""
        mock_signal_summary.return_value = ""
        mock_pred_summary.return_value = ""

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
    @patch("gold_agent.api.debate.cache.get_with_meta")
    def test_quick_analysis_success(self, mock_cache_get_with_meta, mock_generate, mock_summary):
        mock_cache_get_with_meta.return_value = (_fake_ohlcv(), _meta(10, source_status="cache"))
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
        assert data["meta"]["row_count"] == 10
        assert data["meta"]["source_status"] == "cache"

    @patch("gold_agent.api.debate.cache.get_with_meta")
    def test_quick_analysis_error(self, mock_cache_get_with_meta):
        """cache 异常时返回 unavailable meta"""
        mock_cache_get_with_meta.side_effect = ValueError("cache fail")

        resp = client.get("/api/debate/quick")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unavailable"] is True
        assert data["signal"]["signal"] == "neutral"
        assert data["meta"]["source_status"] == "unavailable"
        assert data["meta"]["quality_score"] == 0
        assert "cache fail" in data["error"]

    @patch("gold_agent.api.debate.cache.get_with_meta")
    def test_quick_analysis_empty_data(self, mock_cache_get_with_meta):
        mock_cache_get_with_meta.return_value = (
            pd.DataFrame(),
            _meta(0, source_status="unavailable"),
        )

        resp = client.get("/api/debate/quick")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unavailable"] is True
        assert data["indicators"] == ""
        assert data["meta"]["source_status"] == "unavailable"
        assert data["signal"]["reasons"] == ["数据不可用"]

    @patch("gold_agent.api.debate.DebateEngine")
    @patch("gold_agent.api.debate.get_prediction_summary", return_value="")
    @patch("gold_agent.api.debate.predict_gold_price", return_value=_fake_prediction())
    @patch("gold_agent.api.debate.get_indicator_summary", return_value="### 国际金价")
    @patch("gold_agent.api.debate.get_signal_summary", return_value="")
    @patch("gold_agent.api.debate.generate_signal")
    @patch("gold_agent.api.debate.cache.get_with_meta")
    def test_debate_run_empty_news_and_macro(
        self,
        mock_cache_get_with_meta,
        mock_sig,
        mock_sig_sum,
        mock_ind,
        mock_pred,
        mock_pred_sum,
        mock_engine_cls,
    ):
        """空新闻 + 空宏观数据时正常走完辩论"""
        mock_cache_get_with_meta.side_effect = [
            (_fake_ohlcv(), _meta(10)),
            (pd.DataFrame(), _meta(0, source_status="unavailable")),
            (pd.DataFrame(), _meta(0, source_status="unavailable", expected_frequency="intraday")),
        ]
        mock_sig.return_value = MagicMock()
        mock_engine = MagicMock()
        mock_engine.run_debate = AsyncMock()
        mock_engine.run_debate.return_value = _fake_debate_result()
        mock_engine_cls.return_value = mock_engine

        resp = client.post("/api/debate/run")
        assert resp.status_code == 200
        assert "summary" in resp.json()

    def test_format_meta_summary_hides_duplicate_fetched_at_when_same_as_cached(self):
        from gold_agent.api.debate import _format_meta_summary

        text = _format_meta_summary(
            "国际金价",
            _meta(
                10,
                source_status="cache",
                fetched_at="2024-01-10T08:00:00+00:00",
                cached_at="2024-01-10T08:00:00+00:00",
            ),
        )

        assert "cached_at=2024-01-10T08:00:00+00:00" in text
        assert "fetched_at=2024-01-10T08:00:00+00:00" not in text


class TestDebateStream:
    """SSE 流式辩论 — GET /api/debate/run/stream"""

    @patch("gold_agent.api.debate.DebateEngine")
    @patch("gold_agent.api.debate._build_context", new_callable=AsyncMock)
    def test_stream_success(self, mock_build_context, mock_engine_cls):
        """流式辩论正常返回多个 stage 事件 + complete 事件"""
        mock_build_context.return_value = (
            "debate context",
            {
                "gold": _meta(10),
                "macro": _meta(5, source_status="live"),
                "news": _meta(2, expected_frequency="intraday"),
            },
        )

        mock_engine = MagicMock()

        async def stream_gen(_ctx):
            bull_round = MagicMock()
            bull_round.parsed = {"key_points": ["强势基本面"]}
            yield "bull", bull_round

            bear_round = MagicMock()
            bear_round.parsed = {"key_points": ["政策风险"]}
            yield "bear", bear_round

            audit_round = MagicMock()
            audit_round.parsed = {"missed_data": []}
            yield "audit", audit_round

            result = MagicMock()
            result.to_summary.return_value = "Debate summary text"
            result.to_dict.return_value = {
                "bull": {"confidence": 70},
                "bear": {"confidence": 60},
                "audit": {"overall_assessment": "Good"},
                "verdict": {"verdict": "bullish", "confidence": 75},
            }
            yield "complete", result

        mock_engine.stream_debate = stream_gen
        mock_engine_cls.return_value = mock_engine

        with client.stream("GET", "/api/debate/run/stream") as response:
            assert response.status_code == 200
            lines = list(response.iter_lines())

        text = "\n".join(lines)
        assert "event: stage" in text
        assert "event: complete" in text
        assert "强势基本面" in text
        assert "bullish" in text
        assert "\"meta\"" in text

    @patch("gold_agent.api.debate._build_context", new_callable=AsyncMock)
    def test_stream_build_context_error(self, mock_build_context):
        """_build_context 异常时返回 error 事件"""
        mock_build_context.side_effect = RuntimeError("build failed")

        with client.stream("GET", "/api/debate/run/stream") as response:
            assert response.status_code == 200
            lines = list(response.iter_lines())

        text = "\n".join(lines)
        assert "event: error" in text
        assert "build failed" in text

    @patch("gold_agent.api.debate.DebateEngine")
    @patch("gold_agent.api.debate._build_context", new_callable=AsyncMock)
    def test_stream_engine_error(self, mock_build_context, mock_engine_cls):
        """stream_debate 运行时异常时返回 error 事件"""
        mock_build_context.return_value = (
            "debate context",
            {"gold": None, "macro": None, "news": None},
        )

        mock_engine = MagicMock()

        async def failing_stream(_ctx):
            raise RuntimeError("LLM API failed")
            yield  # pragma: no cover

        mock_engine.stream_debate = failing_stream
        mock_engine_cls.return_value = mock_engine

        with client.stream("GET", "/api/debate/run/stream") as response:
            assert response.status_code == 200
            lines = list(response.iter_lines())

        text = "\n".join(lines)
        assert "event: error" in text
        assert "LLM API failed" in text


    @patch("gold_agent.api.debate.DebateEngine")
    @patch("gold_agent.api.debate.get_prediction_summary")
    @patch("gold_agent.api.debate.predict_gold_price")
    @patch("gold_agent.api.debate.get_indicator_summary")
    @patch("gold_agent.api.debate.get_signal_summary")
    @patch("gold_agent.api.debate.generate_signal")
    @patch("gold_agent.api.debate.cache.get_with_meta")
    def test_debate_run_partial_failure(
        self,
        mock_cache_get_with_meta,
        mock_sig,
        mock_sig_sum,
        mock_ind,
        mock_pred,
        mock_pred_sum,
        mock_engine_cls,
    ):
        """部分数据源失败时仍然完成辩论"""
        mock_cache_get_with_meta.side_effect = [
            (_fake_ohlcv(), _meta(10)),
            ValueError("macro unavailable"),
            ValueError("news unavailable"),
        ]
        mock_ind.return_value = "### 国际金价\nMA20: 2000"
        mock_sig.return_value = MagicMock()
        mock_sig_sum.return_value = "### 信号: 中性"
        mock_pred.return_value = _fake_prediction()
        mock_pred_sum.return_value = "### 预测: 看涨"

        mock_engine = MagicMock()
        mock_engine.run_debate = AsyncMock()
        mock_engine.run_debate.return_value = _fake_debate_result()
        mock_engine_cls.return_value = mock_engine

        resp = client.post("/api/debate/run")
        assert resp.status_code == 200
        assert "summary" in resp.json()

    @patch("gold_agent.api.debate.DebateEngine")
    @patch("gold_agent.api.debate.get_prediction_summary", return_value="")
    @patch("gold_agent.api.debate.predict_gold_price")
    @patch("gold_agent.api.debate.get_indicator_summary", return_value="### 国际金价")
    @patch("gold_agent.api.debate.get_signal_summary", return_value="")
    @patch("gold_agent.api.debate.generate_signal")
    @patch("gold_agent.api.debate.cache.get_with_meta")
    def test_debate_run_prediction_failure(
        self,
        mock_cache_get_with_meta,
        mock_sig,
        mock_sig_sum,
        mock_ind,
        mock_pred,
        mock_pred_sum,
        mock_engine_cls,
    ):
        """预测失败时跳过预测部分"""
        mock_cache_get_with_meta.side_effect = [
            (_fake_ohlcv(), _meta(10)),
            (pd.DataFrame(), _meta(0, source_status="unavailable")),
            (_fake_news(), _meta(2, expected_frequency="intraday")),
        ]
        mock_sig.return_value = MagicMock()
        mock_pred.side_effect = ValueError("prophet failed")

        mock_engine = MagicMock()
        mock_engine.run_debate = AsyncMock()
        mock_engine.run_debate.return_value = _fake_debate_result()
        mock_engine_cls.return_value = mock_engine

        resp = client.post("/api/debate/run")
        assert resp.status_code == 200
        assert "summary" in resp.json()
