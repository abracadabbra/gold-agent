"""Backtest 引擎单元测试 — backtrader 回测封装"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from gold_agent.quant.backtest.engine import (
    STRATEGIES,
    BacktestResult,
    GoldBacktester,
    _create_golden_cross_strategy,
    _get_bt,
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


def test_get_bt_returns_backtrader():
    """_get_bt 应返回 backtrader 模块"""
    bt = _get_bt()
    assert bt is not None
    assert hasattr(bt, "Strategy")
    assert hasattr(bt, "indicators")


def test_get_bt_import_error():
    """_get_bt 在 backtrader 不可用时抛出 ImportError"""
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "backtrader":
            raise ImportError("No module named 'backtrader'")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(ImportError, match="backtrader"):
            _get_bt()


# ============================================================
# GoldenCrossStrategy — __init__ & next
# ============================================================


class TestGoldenCrossStrategy:
    """测试 GoldenCrossStrategy 的 __init__ 和 next 方法"""

    def _make_mock_bt(self):
        """创建 backtrader mock 环境"""
        mock_bt = MagicMock()
        mock_bt.Strategy = MagicMock
        mock_bt.indicators = MagicMock()
        mock_bt.indicators.SMA = MagicMock()
        mock_bt.indicators.RSI = MagicMock()
        mock_bt.indicators.ATR = MagicMock()
        return mock_bt

    def _make_mock_self(self):
        """创建策略实例 mock"""
        mock_self = MagicMock()
        mock_self.p = MagicMock()
        mock_self.p.fast_ma = 20
        mock_self.p.slow_ma = 60
        mock_self.p.rsi_threshold = 40
        mock_self.p.atr_stop_mult = 2.0
        return mock_self

    def test_init_creates_indicators(self):
        """__init__ 应创建 MA/RSI/ATR 指标 (行 38-41)"""
        mock_bt = self._make_mock_bt()
        with patch("gold_agent.quant.backtest.engine._get_bt", return_value=mock_bt):
            strategy_class = _create_golden_cross_strategy()

        mock_self = self._make_mock_self()
        strategy_class.__init__(mock_self)

        mock_bt.indicators.SMA.assert_any_call(period=20)
        mock_bt.indicators.SMA.assert_any_call(period=60)
        mock_bt.indicators.RSI.assert_called_once_with(period=14)
        mock_bt.indicators.ATR.assert_called_once_with(period=14)

    def test_next_buy_on_golden_cross(self):
        """next 金叉时买入 (行 44-49)"""
        mock_bt = self._make_mock_bt()
        with patch("gold_agent.quant.backtest.engine._get_bt", return_value=mock_bt):
            strategy_class = _create_golden_cross_strategy()

        mock_self = self._make_mock_self()
        strategy_class.__init__(mock_self)

        # 配置指标值：金叉成立
        mock_self.ma_fast = MagicMock()
        mock_self.ma_slow = MagicMock()
        mock_self.rsi = MagicMock()
        mock_self.ma_fast.__getitem__.side_effect = lambda i: 110 if i == 0 else 100
        mock_self.ma_slow.__getitem__.side_effect = lambda i: 100 if i == 0 else 105
        mock_self.rsi.__getitem__.return_value = 50
        mock_self.position = False

        strategy_class.next(mock_self)

        mock_self.buy.assert_called_once()

    def test_next_close_on_death_cross(self):
        """next 死叉时平仓 (行 50-52)"""
        mock_bt = self._make_mock_bt()
        with patch("gold_agent.quant.backtest.engine._get_bt", return_value=mock_bt):
            strategy_class = _create_golden_cross_strategy()

        mock_self = self._make_mock_self()
        strategy_class.__init__(mock_self)

        mock_self.ma_fast = MagicMock()
        mock_self.ma_slow = MagicMock()
        mock_self.ma_fast.__getitem__.side_effect = lambda i: 90 if i == 0 else 100
        mock_self.ma_slow.__getitem__.side_effect = lambda i: 100 if i == 0 else 90
        mock_self.position = True

        strategy_class.next(mock_self)

        mock_self.close.assert_called_once()

    def test_next_no_action_when_no_position_and_no_cross(self):
        """next 无头寸且无交叉时无操作"""
        mock_bt = self._make_mock_bt()
        with patch("gold_agent.quant.backtest.engine._get_bt", return_value=mock_bt):
            strategy_class = _create_golden_cross_strategy()

        mock_self = self._make_mock_self()
        strategy_class.__init__(mock_self)

        mock_self.ma_fast = MagicMock()
        mock_self.ma_slow = MagicMock()
        mock_self.rsi = MagicMock()
        mock_self.ma_fast.__getitem__.side_effect = lambda i: 90 if i == 0 else 100
        mock_self.ma_slow.__getitem__.side_effect = lambda i: 100 if i == 0 else 90
        mock_self.rsi.__getitem__.return_value = 50
        mock_self.position = False

        strategy_class.next(mock_self)

        mock_self.buy.assert_not_called()
        mock_self.close.assert_not_called()
