"""集成测试 — App 启动和 API 基本功能"""

from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from gold_agent.main import app

client = TestClient(app)


def test_root():
    """GET / 返回 API 概览"""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "GoldAgent"
    assert "analysis" in data["endpoints"]
    assert "debate" in data["endpoints"]
    assert "backtest" in data["endpoints"]


def test_health():
    """GET /health 返回系统状态"""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "websocket" in data
    assert "config" in data


def test_stats():
    """GET /stats 返回统计信息"""
    resp = client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "websocket" in data
    assert "system" in data
    assert "cache" in data
    assert "uptime" in data["system"]


def test_docs_available():
    """OpenAPI 文档可访问"""
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower()


@patch("gold_agent.api.analysis.cache.get")
def test_analysis_gold(mock_cache):
    """GET /api/analysis/gold 返回金价数据"""
    mock_cache.return_value = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=5, freq="D"),
        "open": [2000.0] * 5, "high": [2010.0] * 5, "low": [1990.0] * 5,
        "close": [2005.0] * 5, "volume": [10000] * 5,
    })
    resp = client.get("/api/analysis/gold?source=intl&period=1y")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "intl"
    assert data["latest_price"] == 2005.0


@patch("gold_agent.api.analysis.cache.get")
def test_analysis_signal(mock_cache):
    """GET /api/analysis/signal 返回交易信号"""
    mock_cache.return_value = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=100, freq="D"),
        "open": [2000.0] * 100, "high": [2010.0] * 100, "low": [1990.0] * 100,
        "close": [2005.0] * 100, "volume": [10000] * 100,
    })
    resp = client.get("/api/analysis/signal")
    assert resp.status_code == 200
    data = resp.json()
    assert "signal" in data


@patch("gold_agent.api.backtest.fetch_gold_price")
@patch("gold_agent.api.backtest._get_backtester")
def test_backtest_strategies(mock_get_bt, mock_fetch):
    """GET /api/backtest/strategies 返回策略列表"""
    from gold_agent.quant.backtest.engine import STRATEGIES, GoldBacktester, get_backtest_summary
    mock_get_bt.return_value = (GoldBacktester, STRATEGIES, get_backtest_summary)
    mock_fetch.return_value = pd.DataFrame({
        "date": pd.date_range("2022-01-01", periods=500, freq="D"),
        "open": [2000.0] * 500, "high": [2010.0] * 500, "low": [1990.0] * 500,
        "close": [2005.0] * 500, "volume": [10000] * 500,
    })
    resp = client.get("/api/backtest/strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert "strategies" in data
