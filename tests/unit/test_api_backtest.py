"""回测接口单元测试 — /api/backtest/*"""

from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi import HTTPException
from fastapi.testclient import TestClient

from gold_agent.main import app
from gold_agent.quant.backtest.engine import STRATEGIES

client = TestClient(app)


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
    @patch("gold_agent.api.backtest.fetch_gold_price")
    def test_run_backtest_success(self, mock_fetch, mock_get_bt):
        mock_fetch.return_value = _fake_ohlcv()

        # Mock _get_backtester to return real STRATEGIES + mock classes
        mock_backtester_cls = MagicMock()
        mock_backtester = MagicMock()
        mock_backtester.run.return_value = MagicMock()
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

    def test_run_backtest_unknown_strategy(self):
        resp = client.get("/api/backtest/run?strategy=unknown&period=2y")
        assert resp.status_code == 400

    @patch("gold_agent.api.backtest.fetch_gold_price")
    def test_run_backtest_empty_data(self, mock_fetch):
        mock_fetch.return_value = pd.DataFrame()

        resp = client.get("/api/backtest/run?strategy=golden_cross&period=2y")
        assert resp.status_code == 500
        assert "数据获取失败" in resp.json()["detail"]

    @patch("gold_agent.api.backtest._get_backtester")
    def test_run_backtest_not_installed(self, mock_get_bt):
        mock_get_bt.side_effect = HTTPException(
            status_code=501, detail="回测功能需要安装 backtrader",
        )

        # _get_backtester is called before fetch_gold_price, so it raises 501
        resp = client.get("/api/backtest/run?strategy=golden_cross&period=2y")
        assert resp.status_code == 501
