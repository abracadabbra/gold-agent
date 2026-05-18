"""Backtest 引擎单元测试 — backtrader 回测封装"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from gold_agent.quant.backtest.engine import (
    STRATEGIES,
    BacktestResult,
    GoldBacktester,
    _create_golden_cross_strategy,
    get_backtest_summary,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def sample_data():
    """模拟 OHLCV 数据"""
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    return pd.DataFrame({
        "date": dates,
        "open": [2000] * 100,
        "high": [2010] * 100,
        "low": [1990] * 100,
        "close": [2000] * 100,
        "volume": [50000] * 100,
    })


@pytest.fixture
def mock_backtrader():
    """创建完整的 backtrader mock"""
    mock_bt = MagicMock()

    # Cerebro
    mock_cerebro = MagicMock()
    mock_cerebro.broker.getvalue.return_value = 110000.0

    # Strategy 分析器
    mock_strat = MagicMock()
    mock_strat.analyzers.sharpe.get_analysis.return_value = {"sharperatio": 1.5}
    mock_strat.analyzers.drawdown.get_analysis.return_value = {
        "max": {"drawdown": 0.15},
    }
    mock_strat.analyzers.trades.get_analysis.return_value = {
        "total": {"total": 10},
        "won": {"total": 6},
    }

    mock_cerebro.run.return_value = [mock_strat]
    mock_bt.Cerebro.return_value = mock_cerebro
    mock_bt.Strategy = MagicMock

    # 返回 mock_bt 和 mock_cerebro 供验证
    return mock_bt, mock_cerebro, mock_strat


# ============================================================
# BacktestResult dataclass
# ============================================================


def test_backtest_result_creation():
    """BacktestResult 数据类字段"""
    result = BacktestResult(
        strategy="golden_cross",
        initial_cash=100000.0,
        final_value=110000.0,
        total_return=0.1,
        max_drawdown=0.15,
        trades=10,
        winning_trades=6,
        win_rate=0.6,
        sharpe_ratio=1.5,
        equity_curve=[100000, 105000, 110000],
    )

    assert result.strategy == "golden_cross"
    assert result.initial_cash == 100000.0
    assert result.final_value == 110000.0
    assert result.total_return == 0.1
    assert result.max_drawdown == 0.15
    assert result.trades == 10
    assert result.winning_trades == 6
    assert result.win_rate == 0.6
    assert result.sharpe_ratio == 1.5
    assert result.equity_curve == [100000, 105000, 110000]


def test_backtest_result_defaults():
    """equity_curve 默认为空列表"""
    result = BacktestResult(
        strategy="test",
        initial_cash=0.0,
        final_value=0.0,
        total_return=0.0,
        max_drawdown=0.0,
        trades=0,
        winning_trades=0,
        win_rate=0.0,
        sharpe_ratio=0.0,
        equity_curve=[],
    )
    assert result.equity_curve == []


# ============================================================
# get_backtest_summary
# ============================================================


def test_get_backtest_summary():
    """格式化回测结果"""
    result = BacktestResult(
        strategy="golden_cross",
        initial_cash=100000.0,
        final_value=110000.0,
        total_return=0.1,
        max_drawdown=0.15,
        trades=10,
        winning_trades=6,
        win_rate=0.6,
        sharpe_ratio=1.5,
        equity_curve=[],
    )

    summary = get_backtest_summary(result)

    assert summary["strategy"] == "golden_cross"
    assert summary["initial_cash"] == 100000.0
    assert summary["final_value"] == 110000.0
    assert summary["total_return"] == "10.00%"
    assert summary["max_drawdown"] == "15.00%"
    assert summary["win_rate"] == "60.0%"
    assert summary["trades"] == 10
    assert summary["winning_trades"] == 6
    assert summary["sharpe_ratio"] == 1.5


# ============================================================
# GoldBacktester
# ============================================================


def test_gold_backtester_init_defaults():
    """默认参数"""
    bt = GoldBacktester()
    assert bt.strategy_name == "golden_cross"
    assert bt.initial_cash == 100000.0


def test_gold_backtester_init_custom():
    """自定义参数"""
    bt = GoldBacktester(strategy_name="golden_cross", initial_cash=50000.0)
    assert bt.strategy_name == "golden_cross"
    assert bt.initial_cash == 50000.0


def test_gold_backtester_run_unknown_strategy(sample_data):
    """未知策略应抛出 ValueError"""
    bt = GoldBacktester(strategy_name="unknown_strategy")

    with pytest.raises(ValueError, match="未知策略"):
        bt.run(sample_data)


def test_gold_backtester_run_success(sample_data, mock_backtrader):
    """正常回测流程 — 验证 backtrader 关键操作"""
    mock_bt, mock_cerebro, mock_strat = mock_backtrader

    bt = GoldBacktester(strategy_name="golden_cross", initial_cash=100000.0)

    with patch("gold_agent.quant.backtest.engine._get_bt", return_value=mock_bt):
        result = bt.run(sample_data)

    # 验证结果
    assert isinstance(result, BacktestResult)
    assert result.strategy == "golden_cross"
    assert result.initial_cash == 100000.0
    assert result.final_value == 110000.0
    assert result.total_return == 0.1
    assert result.max_drawdown == 0.15
    assert result.trades == 10
    assert result.winning_trades == 6
    assert result.win_rate == 0.6
    assert result.sharpe_ratio == 1.5

    # 验证 Cerebro 操作
    mock_bt.Cerebro.assert_called_once()
    mock_cerebro.broker.setcash.assert_called_once_with(100000.0)
    mock_cerebro.broker.setcommission.assert_called_once_with(commission=0.001)
    mock_bt.feeds.PandasData.assert_called_once_with(
        dataname=sample_data,
        datetime="date",
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
    )
    mock_cerebro.adddata.assert_called_once()
    mock_cerebro.addstrategy.assert_called_once()
    mock_cerebro.run.assert_called_once()

    # 验证分析器
    assert mock_cerebro.addanalyzer.call_count == 3


def test_gold_backtester_run_zero_trades(sample_data, mock_backtrader):
    """0 笔交易 — win_rate 应为 0"""
    mock_bt, mock_cerebro, mock_strat = mock_backtrader
    mock_strat.analyzers.trades.get_analysis.return_value = {
        "total": {"total": 0},
        "won": {"total": 0},
    }

    bt = GoldBacktester()

    with patch("gold_agent.quant.backtest.engine._get_bt", return_value=mock_bt):
        result = bt.run(sample_data)

    assert result.trades == 0
    assert result.winning_trades == 0
    assert result.win_rate == 0.0


def test_gold_backtester_run_sharpe_none(sample_data, mock_backtrader):
    """Sharpe Ratio 为 None 时返回 0"""
    mock_bt, mock_cerebro, mock_strat = mock_backtrader
    mock_strat.analyzers.sharpe.get_analysis.return_value = {"sharperatio": None}

    bt = GoldBacktester()

    with patch("gold_agent.quant.backtest.engine._get_bt", return_value=mock_bt):
        result = bt.run(sample_data)

    assert result.sharpe_ratio == 0.0


# ============================================================
# STRATEGIES
# ============================================================


def test_strategies_dict():
    """STRATEGIES 常量"""
    assert "golden_cross" in STRATEGIES
    assert "MA 金叉死叉" in STRATEGIES["golden_cross"]


# ============================================================
# _create_golden_cross_strategy
# ============================================================


def test_create_golden_cross_strategy_returns_class():
    """_create_golden_cross_strategy 应返回策略类"""
    mock_bt = MagicMock()
    mock_bt.Strategy = MagicMock

    with patch("gold_agent.quant.backtest.engine._get_bt", return_value=mock_bt):
        strategy_class = _create_golden_cross_strategy()

    assert callable(strategy_class)
