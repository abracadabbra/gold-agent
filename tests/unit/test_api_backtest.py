"""回测接口单元测试 — /api/backtest/*"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from gold_agent.main import app
from gold_agent.quant.backtest.engine import STRATEGIES

client = TestClient(app)


def _meta(row_count: int) -> dict:
    return {
        "as_of": "2024-01-05T00:00:00",
        "latest_date": "2024-01-05T00:00:00",
        "fetched_at": "2024-01-05T08:00:00+00:00",
        "cached_at": "2024-01-05T07:55:00+00:00",
        "row_count": row_count,
        "stale": False,
        "source_status": "cache",
        "missing_rate": 0.0,
        "quality_score": 95,
        "expected_frequency": "daily",
    }


def _fake_ohlcv():
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=100, freq="D"),
        "open": [2000.0] * 100,
        "high": [2010.0] * 100,
        "low": [1990.0] * 100,
        "close": [2005.0] * 100,
        "volume": [10000] * 100,
    })


# ============================================================
# GET /api/backtest/strategies
# ============================================================


class TestBacktestStrategies:
    """策略列表端点"""

    def test_list_strategies_returns_available_strategies(self):
        resp = client.get("/api/backtest/strategies")
        assert resp.status_code == 200
        data = resp.json()
        assert "strategies" in data
        assert "golden_cross" in data["strategies"]

    @patch("gold_agent.api.backtest._get_backtester")
    def test_list_strategies_backtrader_not_installed(self, mock_get_bt):
        mock_get_bt.side_effect = HTTPException(status_code=501, detail="backtrader not installed")

        resp = client.get("/api/backtest/strategies")
        # /strategies catches HTTPException and returns 200 with fallback
        assert resp.status_code == 200
        data = resp.json()
        assert "golden_cross" in data["strategies"]
        assert "note" in data


# ============================================================
# GET /api/backtest/run
# ============================================================


class TestBacktestRun:
    """运行回测端点"""

    @patch("gold_agent.api.backtest._get_backtester")
    @patch("gold_agent.api.backtest.cache.get_with_meta")
    def test_run_backtest_success(self, mock_cache_get_with_meta, mock_get_bt):
        mock_cache_get_with_meta.return_value = (_fake_ohlcv(), _meta(100))

        # Mock _get_backtester to return real STRATEGIES + mock classes
        mock_backtester_cls = MagicMock()
        mock_backtester = MagicMock()
        mock_backtester.run.return_value = MagicMock(trades=10)
        mock_backtester_cls.return_value = mock_backtester

        mock_summary_fn = MagicMock()
        mock_summary_fn.return_value = {
            "strategy": "golden_cross",
            "initial_cash": 100000.0,
            "final_value": 110000.0,
            "total_return": "10.00%",
            "max_drawdown": "5.00%",
            "sharpe_ratio": 1.5,
            "trades": 10,
            "winning_trades": 6,
            "win_rate": "60.0%",
        }

        mock_get_bt.return_value = (mock_backtester_cls, STRATEGIES, mock_summary_fn)

        resp = client.get("/api/backtest/run?strategy=golden_cross&period=2y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "golden_cross"
        assert data["total_return"] == "10.00%"
        assert data["win_rate"] == "60.0%"
        assert data["meta"]["row_count"] == 100
        assert data["meta"]["source_status"] == "cache"
        assert data["backtest_meta"]["sample_size"] == 100
        assert data["backtest_meta"]["min_required_rows"] == 120
        assert data["backtest_meta"]["sample_satisfied"] is False
        assert data["backtest_meta"]["trades"] == 10
        assert data["backtest_meta"]["trade_sufficient"] is True
        assert data["backtest_meta"]["quality_score"] == 65

    def test_run_backtest_unknown_strategy(self):
        resp = client.get("/api/backtest/run?strategy=unknown&period=2y")
        assert resp.status_code == 400

    @patch("gold_agent.api.backtest.cache.get_with_meta")
    def test_run_backtest_empty_data(self, mock_cache_get_with_meta):
        mock_cache_get_with_meta.return_value = (pd.DataFrame(), _meta(0))

        resp = client.get("/api/backtest/run?strategy=golden_cross&period=2y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unavailable"] is True
        assert data["strategy"] == "golden_cross"
        assert data["final_value"] == 100000
        assert data["meta"]["row_count"] == 0
        assert data["backtest_meta"]["sample_size"] == 0
        assert data["backtest_meta"]["sample_satisfied"] is False
        assert data["backtest_meta"]["trades"] == 0
        assert data["backtest_meta"]["trade_sufficient"] is False
        assert data["backtest_meta"]["quality_score"] == 0
        assert data["error"] == "数据获取失败"

    @patch("gold_agent.api.backtest.cache.get_with_meta")
    def test_run_backtest_fetch_error_returns_unavailable(self, mock_cache_get_with_meta):
        mock_cache_get_with_meta.side_effect = ValueError("cache unavailable")

        resp = client.get("/api/backtest/run?strategy=golden_cross&period=2y")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unavailable"] is True
        assert data["meta"]["source_status"] == "unavailable"
        assert data["backtest_meta"]["quality_score"] == 0
        assert data["backtest_meta"]["sample_satisfied"] is False
        assert "cache unavailable" in data["error"]

    @patch("gold_agent.api.backtest._get_backtester")
    @patch("gold_agent.api.backtest.cache.get_with_meta")
    def test_run_backtest_result_meta_penalizes_zero_trades(
        self,
        mock_cache_get_with_meta,
        mock_get_bt,
    ):
        mock_cache_get_with_meta.return_value = (_fake_ohlcv(), _meta(100))

        mock_backtester_cls = MagicMock()
        mock_backtester = MagicMock()
        mock_backtester.run.return_value = MagicMock(trades=0)
        mock_backtester_cls.return_value = mock_backtester

        mock_summary_fn = MagicMock()
        mock_summary_fn.return_value = {
            "strategy": "golden_cross",
            "initial_cash": 100000.0,
            "final_value": 100000.0,
            "total_return": "0.00%",
            "max_drawdown": "0.00%",
            "sharpe_ratio": 0.0,
            "trades": 0,
            "winning_trades": 0,
            "win_rate": "0.0%",
        }

        mock_get_bt.return_value = (mock_backtester_cls, STRATEGIES, mock_summary_fn)

        resp = client.get("/api/backtest/run?strategy=golden_cross&period=2y")

        assert resp.status_code == 200
        data = resp.json()
        assert data["backtest_meta"]["sample_satisfied"] is False
        assert data["backtest_meta"]["trade_sufficient"] is False
        assert data["backtest_meta"]["quality_score"] == 45

    @patch("gold_agent.api.backtest._get_backtester")
    def test_run_backtest_not_installed(self, mock_get_bt):
        mock_get_bt.side_effect = HTTPException(
            status_code=501, detail="回测功能需要安装 backtrader",
        )

        # _get_backtester is called before fetch_gold_price, so it raises 501
        resp = client.get("/api/backtest/run?strategy=golden_cross&period=2y")
        assert resp.status_code == 501

    def test_get_backtester_import_error(self):
        """触发 _get_backtester 中的实际 ImportError 路径（覆盖 lines 17-18）"""
        import builtins
        import sys

        import gold_agent.api.backtest as _mod
        _get_backtester = _mod._get_backtester

        # Remove the engine module from sys.modules so Python will re-import
        orig_mod = sys.modules.pop("gold_agent.quant.backtest.engine", None)
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "gold_agent.quant.backtest.engine":
                raise ImportError("No module named backtrader")
            return original_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(HTTPException) as exc_info:
                    _get_backtester()
                assert exc_info.value.status_code == 501
                assert "backtrader" in exc_info.value.detail
        finally:
            if orig_mod is not None:
                sys.modules["gold_agent.quant.backtest.engine"] = orig_mod
