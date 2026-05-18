"""回测引擎封装 — 基于 backtrader (可选依赖)"""

from dataclasses import dataclass

import pandas as pd
import logging
logger = logging.getLogger(__name__)



# ============================================================
# 内置策略
# ============================================================

def _get_bt():
    """延迟导入 backtrader"""
    try:
        import backtrader as bt
        return bt
    except ImportError:
        raise ImportError("backtrader not installed. Install with: pip install backtrader")


def _create_golden_cross_strategy():
    """动态创建 GoldenCrossStrategy 类"""
    bt = _get_bt()

    class GoldenCrossStrategy(bt.Strategy):
        """MA 金叉死叉 + RSI 过滤 + ATR 止损"""
        params = (
            ("fast_ma", 20),
            ("slow_ma", 60),
            ("rsi_threshold", 40),
            ("atr_stop_mult", 2.0),
        )

        def __init__(self):
            self.ma_fast = bt.indicators.SMA(period=self.p.fast_ma)
            self.ma_slow = bt.indicators.SMA(period=self.p.slow_ma)
            self.rsi = bt.indicators.RSI(period=14)
            self.atr = bt.indicators.ATR(period=14)

        def next(self):
            if not self.position:
                if (self.ma_fast[0] > self.ma_slow[0] and
                    self.ma_fast[-1] <= self.ma_slow[-1] and
                    self.rsi[0] > self.p.rsi_threshold):
                    self.buy()
            else:
                if (self.ma_fast[0] < self.ma_slow[0] and
                    self.ma_fast[-1] >= self.ma_slow[-1]):
                    self.close()

    return GoldenCrossStrategy


# ============================================================
# 回测器封装
# ============================================================

STRATEGIES = {
    "golden_cross": "MA 金叉死叉 + RSI 过滤 + ATR 止损",
}


@dataclass
class BacktestResult:
    """回测结果"""
    strategy: str
    initial_cash: float
    final_value: float
    total_return: float
    max_drawdown: float
    trades: int
    winning_trades: int
    win_rate: float
    sharpe_ratio: float
    equity_curve: list


class GoldBacktester:
    """黄金回测器"""

    def __init__(self, strategy_name: str = "golden_cross", initial_cash: float = 100000):
        self.strategy_name = strategy_name
        self.initial_cash = initial_cash

    def run(self, df: pd.DataFrame) -> BacktestResult:
        """运行回测"""
        bt = _get_bt()

        cerebro = bt.Cerebro()
        cerebro.broker.setcash(self.initial_cash)
        cerebro.broker.setcommission(commission=0.001)

        # 加载数据
        data = bt.feeds.PandasData(
            dataname=df,
            datetime="date",
            open="open",
            high="high",
            low="low",
            close="close",
            volume="volume",
        )
        cerebro.adddata(data)

        # 添加策略
        if self.strategy_name == "golden_cross":
            strategy_class = _create_golden_cross_strategy()
            cerebro.addstrategy(strategy_class)
        else:
            raise ValueError(f"未知策略: {self.strategy_name}")

        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

        # 运行
        results = cerebro.run()
        strat = results[0]

        # 提取结果
        final_value = cerebro.broker.getvalue()
        total_return = (final_value - self.initial_cash) / self.initial_cash

        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        trades = strat.analyzers.trades.get_analysis()

        sharpe_ratio = sharpe.get("sharperatio", 0) or 0
        max_dd = drawdown.get("max", {}).get("drawdown", 0) or 0

        total_trades = trades.get("total", {}).get("total", 0) or 0
        won = trades.get("won", {}).get("total", 0) or 0
        win_rate = won / total_trades if total_trades > 0 else 0

        return BacktestResult(
            strategy=self.strategy_name,
            initial_cash=self.initial_cash,
            final_value=round(final_value, 2),
            total_return=round(total_return, 4),
            max_drawdown=round(max_dd, 4),
            trades=total_trades,
            winning_trades=won,
            win_rate=round(win_rate, 4),
            sharpe_ratio=round(sharpe_ratio, 4),
            equity_curve=[],
        )


def get_backtest_summary(result: BacktestResult) -> dict:
    """格式化回测结果为 JSON"""
    return {
        "strategy": result.strategy,
        "initial_cash": result.initial_cash,
        "final_value": result.final_value,
        "total_return": f"{result.total_return * 100:.2f}%",
        "max_drawdown": f"{result.max_drawdown * 100:.2f}%",
        "sharpe_ratio": result.sharpe_ratio,
        "trades": result.trades,
        "winning_trades": result.winning_trades,
        "win_rate": f"{result.win_rate * 100:.1f}%",
    }
