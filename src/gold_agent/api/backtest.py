"""回测接口 — backtrader 为可选依赖"""

from fastapi import APIRouter, HTTPException, Query
import logging
logger = logging.getLogger(__name__)

from gold_agent.data.gold_price import fetch_gold_price

router = APIRouter(prefix="/api/backtest", tags=["回测"])


def _get_backtester():
    """延迟导入 backtrader"""
    try:
        from gold_agent.quant.backtest.engine import GoldBacktester, STRATEGIES, get_backtest_summary
        return GoldBacktester, STRATEGIES, get_backtest_summary
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="回测功能需要安装 backtrader: pip install backtrader"
        )


@router.get("/strategies")
async def list_strategies():
    """列出可用的回测策略"""
    try:
        _, STRATEGIES, _ = _get_backtester()
        return {"strategies": list(STRATEGIES.keys())}
    except HTTPException:
        return {"strategies": ["golden_cross"], "note": "backtrader 未安装，策略仅作展示"}


@router.get("/run")
async def run_backtest(
    strategy: str = Query("golden_cross", description="策略名称"),
    period: str = Query("2y", description="回测周期"),
    initial_cash: float = Query(100000, description="初始资金"),
):
    """运行回测"""
    GoldBacktester, STRATEGIES, get_backtest_summary = _get_backtester()

    if strategy not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"未知策略: {strategy}")

    df = fetch_gold_price(period)
    if df.empty:
        raise HTTPException(status_code=500, detail="数据获取失败")

    backtester = GoldBacktester(strategy_name=strategy, initial_cash=initial_cash)
    result = backtester.run(df)
    summary = get_backtest_summary(result)

    return summary
