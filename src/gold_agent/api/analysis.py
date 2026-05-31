"""分析接口 — 金价数据 + 技术指标 + 信号"""

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
import logging
logger = logging.getLogger(__name__)


from gold_agent.utils.json import json_safe as _json_safe

from gold_agent.data.gold_price import fetch_gold_price
from gold_agent.data.macro import fetch_macro_yfinance, fetch_macro_fred
from gold_agent.data.news import fetch_news_with_sentiment
from gold_agent.data.cache import cache
from gold_agent.db.session import SessionLocal
from gold_agent.db.repository import save_gold_prices
from gold_agent.db.models import GoldPrice
from gold_agent.quant.indicators import compute_indicators, get_indicator_summary
from gold_agent.quant.signals import generate_signal, get_signal_summary
from gold_agent.quant.predictor import predict_gold_price, get_prediction_summary

router = APIRouter(prefix="/api/analysis", tags=["分析"])

_FALLBACK_SOURCES = {"intl": "shfe", "shfe": "intl", "gld": "shfe"}

# API source name → DB source name
_SOURCE_TO_DB = {"intl": "xauusd", "gld": "etf", "shfe": "spot_cny"}
_DB_TO_SOURCE = {v: k for k, v in _SOURCE_TO_DB.items()}


def _db_save_gold(source: str, records: list[dict]) -> None:
    """将采集到的金价数据写入 DB，自动补 source 字段"""
    db_source = _SOURCE_TO_DB.get(source, source)
    for r in records:
        r.setdefault("source", db_source)
    try:
        with SessionLocal() as db:
            save_gold_prices(db, records)
    except Exception as e:
        logger.warning(f"DB 保存金价失败 ({source}): {e}")


def _load_gold_from_db(source: str, period: str) -> pd.DataFrame:
    """从 DB 加载历史金价数据作为兜底"""
    db_source = _SOURCE_TO_DB.get(source, source)
    days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}.get(period, 365)
    try:
        with SessionLocal() as db:
            from datetime import datetime, timedelta
            cutoff = datetime.utcnow() - timedelta(days=days)
            # 同时查映射名和原始名，兼容新旧数据
            rows = (
                db.query(GoldPrice)
                .filter(
                    GoldPrice.source.in_([db_source, source]),
                    GoldPrice.date >= cutoff,
                )
                .order_by(GoldPrice.date)
                .all()
            )
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame([
                {"date": r.date, "open": r.open, "high": r.high,
                 "low": r.low, "close": r.close, "volume": r.volume}
                for r in rows
            ])
            logger.info(f"从 DB 加载 {source}: {len(df)} 条记录")
            return df
    except Exception as e:
        logger.warning(f"DB 读取金价失败 ({source}): {e}")
        return pd.DataFrame()


def _fetch_gold_with_fallback(source: str, period: str) -> tuple[pd.DataFrame, str]:
    """获取金价数据: live → 备选源 → DB 历史兜底"""
    df = cache.get(
        key=f"gold_{source}",
        fetch_fn=fetch_gold_price,
        source=source,
        period=period,
        max_stale_days=0.1,
        db_save_fn=lambda records: _db_save_gold(source, records),
    )
    if not df.empty:
        return df, source

    fallback = _FALLBACK_SOURCES.get(source)
    if fallback:
        logger.warning(f"数据源 {source} 不可用，降级到 {fallback}")
        df = cache.get(
            key=f"gold_{fallback}",
            fetch_fn=fetch_gold_price,
            source=fallback,
            period=period,
            max_stale_days=0.1,
            db_save_fn=lambda records: _db_save_gold(fallback, records),
        )
        if not df.empty:
            return df, fallback

    # 最后兜底：从 DB 读历史数据
    df = _load_gold_from_db(source, period)
    if not df.empty:
        logger.info(f"使用 DB 历史数据兜底: {source}")
        return df, source

    # 连 DB 都没有，试备选源的 DB 数据
    if fallback:
        df = _load_gold_from_db(fallback, period)
        if not df.empty:
            logger.info(f"使用 DB 历史数据兜底: {fallback}")
            return df, fallback

    return df, source


@router.get("/gold")
async def get_gold_price(
    source: str = Query("intl", description="数据源: intl/shfe/gld"),
    period: str = Query("1y", description="时间范围: 1mo/3mo/6mo/1y/2y/5y"),
):
    """获取金价数据"""
    try:
        df, actual_source = _fetch_gold_with_fallback(source, period)
        return {
            "source": actual_source,
            "records": len(df),
            "latest_price": float(df["close"].iloc[-1]) if not df.empty else None,
            "data": df.tail(100).to_dict(orient="records"),
        }
    except Exception as e:
        logger.error(f"获取金价失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indicators")
async def get_indicators(
    source: str = Query("intl", description="数据源"),
    period: str = Query("1y", description="时间范围"),
):
    """获取技术指标"""
    try:
        df, _ = _fetch_gold_with_fallback(source, period)

        if df.empty:
            return {
                "price": None,
                "indicators": {},
                "summary": f"数据源 {source} 暂时不可用，请稍后重试或切换数据源",
                "unavailable": True,
            }

        indicators = compute_indicators(df)
        summary = get_indicator_summary(df)

        return {
            "price": float(df["close"].iloc[-1]),
            "indicators": indicators.to_dict(),
            "summary": summary,
        }
    except Exception as e:
        logger.error(f"计算指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signal")
async def get_signal(
    source: str = Query("intl", description="数据源"),
    period: str = Query("1y", description="时间范围"),
):
    """获取交易信号"""
    try:
        df, _ = _fetch_gold_with_fallback(source, period)

        if df.empty:
            return {
                "signal": {"signal": 0, "score": 0, "factors": {}},
                "summary": f"数据源 {source} 暂时不可用，请稍后重试或切换数据源",
                "macro_factors": None,
                "unavailable": True,
            }

        # 获取宏观数据（FRED TIPS 实际利率等）作为可选因子
        macro_values: dict[str, float] | None = None
        try:
            fred_df = cache.get(
                key="macro_fred",
                fetch_fn=fetch_macro_fred,
                start_date="2024-01-01",
                ttl=3600,
            )
            if not fred_df.empty and "tips_yield" in fred_df.columns:
                latest_fred = fred_df.dropna(subset=["tips_yield"]).iloc[-1]
                macro_values = {"tips_yield": float(latest_fred["tips_yield"])}
        except Exception:
            logger.warning("获取 FRED 宏观数据失败，信号将不含宏观因子")

        signal = generate_signal(df, macro_values=macro_values)
        summary = get_signal_summary(signal)

        return {
            "signal": signal.to_dict(),
            "summary": summary,
            "macro_factors": macro_values,
        }
    except Exception as e:
        logger.error(f"生成信号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/predict")
async def get_prediction(
    source: str = Query("intl", description="数据源"),
    days: int = Query(7, ge=1, le=30, description="预测天数"),
):
    """时序预测"""
    try:
        df, _ = _fetch_gold_with_fallback(source, "1y")

        if df.empty:
            return {
                "prediction": [],
                "history": [],
                "trend": "unknown",
                "summary": f"数据源 {source} 暂时不可用，请稍后重试或切换数据源",
                "unavailable": True,
            }

        # 获取宏观数据作为回归因子（使用缓存）
        macro_df = cache.get(
            key="macro_yfinance_2y",
            fetch_fn=fetch_macro_yfinance,
            period="2y",
            ttl=3600,
        )
        regressors = {}
        if not macro_df.empty:
            for col in ["usd_index", "vix", "us_10y"]:
                if col in macro_df.columns:
                    series = macro_df.set_index("date")[col].dropna()
                    if not series.empty:
                        regressors[col] = series

        prediction = predict_gold_price(df, days=days, regressors=regressors)
        summary = get_prediction_summary(prediction)

        forecast = prediction["forecast"]
        if "ds" in forecast.columns:
            forecast["ds"] = forecast["ds"].astype(str)
        elif "date" in forecast.columns:
            forecast = forecast.rename(columns={
                "date": "ds",
                "predicted": "yhat",
                "lower_bound": "yhat_lower",
                "upper_bound": "yhat_upper",
            })

        # 取最近 60 天历史价格作为上下文
        history_df = df.tail(60)[["date", "close"]].copy()
        history_df.columns = ["ds", "close"]
        history_df["ds"] = history_df["ds"].astype(str)

        return {
            "prediction": _json_safe(forecast),
            "history": _json_safe(history_df),
            "trend": prediction["trend_direction"],
            "summary": summary,
            "disclaimer": (  # noqa: E501
                "AI 预测仅供参考，不构成投资建议。"
                "实际价格可能因市场变化与预测结果存在显著偏差。"
            ),
        }
    except Exception as e:
        logger.error(f"预测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/macro")
async def get_macro_data(period: str = Query("1y")):
    """获取宏观数据 (yfinance 实时 + FRED 官方)"""
    try:
        realtime = cache.get(
            key=f"macro_yfinance_{period}",
            fetch_fn=fetch_macro_yfinance,
            period=period,
            ttl=3600,
            max_stale_days=1,
        )
        official = cache.get(
            key="macro_fred",
            fetch_fn=fetch_macro_fred,
            start_date="2020-01-01",
            ttl=3600,
            max_stale_days=1,
        )

        def _format(df: pd.DataFrame) -> dict:
            if df.empty:
                return {"records": 0, "columns": [], "data": []}
            d = df.tail(100).copy()
            if "date" in d.columns:
                d["date"] = d["date"].dt.strftime("%Y-%m-%d")
            return {
                "records": len(d),
                "columns": list(d.columns),
                "data": _json_safe(d),
            }

        return {"realtime": _format(realtime), "official": _format(official)}
    except Exception as e:
        logger.error(f"获取宏观数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news")
async def get_news():
    """获取新闻情绪"""
    try:
        df = cache.get(
            key="news_sentiment",
            fetch_fn=fetch_news_with_sentiment,
            ttl=300,
            max_stale_days=1,
        )
        avg_score = float(df["sentiment_score"].mean()) if not df.empty else 0

        return {
            "total": len(df),
            "avg_sentiment": avg_score,
            "label": "bullish" if avg_score > 0.2 else "bearish" if avg_score < -0.2 else "neutral",
            "news": _json_safe(df.head(20)),
        }
    except Exception as e:
        logger.error(f"获取新闻失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
