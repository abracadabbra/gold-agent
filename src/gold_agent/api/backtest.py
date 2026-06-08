"""回测接口 — backtrader 为可选依赖"""

import logging
from types import SimpleNamespace

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

from gold_agent.data.cache import cache
from gold_agent.data.gold_price import fetch_gold_price, gold_cache_key, period_to_months
from gold_agent.data.quality import dataframe_meta

router = APIRouter(prefix="/api/backtest", tags=["回测"])

_BACKTEST_MIN_SAMPLE_ROWS = 120
_BACKTEST_MIN_TRADES = 1


def _get_backtester():
    """延迟导入 backtrader"""
    try:
        from gold_agent.quant.backtest.engine import GoldBacktester, STRATEGIES, get_backtest_summary  # noqa: E501
        return GoldBacktester, STRATEGIES, get_backtest_summary
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="回测功能需要安装 backtrader: pip install backtrader"
        )


def _backtest_result_meta(result, df, source_meta: dict) -> dict:
    """Describe whether the backtest result is suitable evidence."""
    meta = dataframe_meta(
        df,
        max_stale_days=None,
        source_status=source_meta.get("source_status", "live"),
        fetched_at=None,
        cached_at=None,
        expected_frequency="daily",
    )
    meta["fetched_at"] = source_meta.get("fetched_at") or meta["fetched_at"]
    meta["cached_at"] = source_meta.get("cached_at")
    meta["stale"] = bool(source_meta.get("stale", meta["stale"]))
    meta["as_of"] = source_meta.get("as_of") or meta["as_of"]
    meta["latest_date"] = source_meta.get("latest_date") or meta["latest_date"]

    sample_size = int(len(df))
    source_quality = int(source_meta.get("quality_score", meta["quality_score"]) or 0)
    quality_score = min(source_quality, int(meta["quality_score"]))
    sample_satisfied = sample_size >= _BACKTEST_MIN_SAMPLE_ROWS
    trades = int(getattr(result, "trades", getattr(result, "total_trades", 0)) or 0)
    trade_sufficient = trades >= _BACKTEST_MIN_TRADES

    if not sample_satisfied:
        quality_score -= 30
    if not trade_sufficient:
        quality_score -= 20

    meta["quality_score"] = max(0, quality_score)
    meta["sample_size"] = sample_size
    meta["min_required_rows"] = _BACKTEST_MIN_SAMPLE_ROWS
    meta["sample_satisfied"] = sample_satisfied
    meta["trades"] = trades
    meta["min_required_trades"] = _BACKTEST_MIN_TRADES
    meta["trade_sufficient"] = trade_sufficient
    return meta


def _unavailable_backtest_response(
    *,
    strategy: str,
    initial_cash: float,
    meta: dict,
    error: str | None = None,
) -> dict:
    result = SimpleNamespace(trades=0)
    response = {
        "strategy": strategy,
        "initial_cash": initial_cash,
        "final_value": initial_cash,
        "total_return": "0.00%",
        "max_drawdown": "0.00%",
        "sharpe_ratio": 0.0,
        "trades": 0,
        "winning_trades": 0,
        "win_rate": "0.0%",
        "meta": meta,
        "backtest_meta": _backtest_result_meta(result, pd.DataFrame(), meta),
        "unavailable": True,
    }
    if error:
        response["error"] = error
    return response


@router.get("/strategies")
async def list_strategies():
    """列出可用的回测策略"""
    try:
        _, strategies, _ = _get_backtester()
        return {"strategies": list(strategies.keys())}
    except HTTPException:
        return {"strategies": ["golden_cross"], "note": "backtrader 未安装，策略仅作展示"}


@router.get("/run")
async def run_backtest(
    strategy: str = Query("golden_cross", description="策略名称"),
    period: str = Query("2y", description="回测周期"),
    initial_cash: float = Query(100000, description="初始资金"),
):
    """运行回测"""
    backtester_cls, strategies, get_backtest_summary = _get_backtester()

    if strategy not in strategies:
        raise HTTPException(status_code=400, detail=f"未知策略: {strategy}")

    try:
        df, meta = cache.get_with_meta(
            key=gold_cache_key("intl", period),
            fetch_fn=fetch_gold_price,
            source="intl",
            period=period,
            max_stale_days=0.1,
            months=period_to_months(period),
            expected_frequency="daily",
        )
    except Exception as e:
        logger.warning(f"回测数据获取失败: {e}")
        meta = dataframe_meta(
            pd.DataFrame(),
            source_status="unavailable",
            expected_frequency="daily",
        )
        return _unavailable_backtest_response(
            strategy=strategy,
            initial_cash=initial_cash,
            meta=meta,
            error=str(e),
        )
    if df.empty:
        return _unavailable_backtest_response(
            strategy=strategy,
            initial_cash=initial_cash,
            meta=meta,
            error="数据获取失败",
        )

    backtester = backtester_cls(strategy_name=strategy, initial_cash=initial_cash)
    result = backtester.run(df)
    summary = get_backtest_summary(result)
    summary["meta"] = meta
    summary["backtest_meta"] = _backtest_result_meta(result, df, meta)

    return summary
