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
from gold_agent.quant.indicators import compute_indicators, get_indicator_summary
from gold_agent.quant.signals import generate_signal, get_signal_summary
from gold_agent.quant.predictor import predict_gold_price, get_prediction_summary

router = APIRouter(prefix="/api/analysis", tags=["分析"])


@router.get("/gold")
async def get_gold_price(
    source: str = Query("intl", description="数据源: intl/shfe/gld"),
    period: str = Query("1y", description="时间范围: 1mo/3mo/6mo/1y/2y/5y"),
):
    """获取金价数据"""
    try:
        df = cache.get(
            key=f"gold_{source}",
            fetch_fn=fetch_gold_price,
            source=source,
            period="1y",
            max_stale_days=1,
        )
        return {
            "source": source,
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
        df = cache.get(
            key=f"gold_{source}",
            fetch_fn=fetch_gold_price,
            source=source,
            period=period,
            max_stale_days=1,
        )

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
        df = cache.get(
            key=f"gold_{source}",
            fetch_fn=fetch_gold_price,
            source=source,
            period=period,
            max_stale_days=1,
        )

        signal = generate_signal(df)
        summary = get_signal_summary(signal)

        return {
            "signal": signal.to_dict(),
            "summary": summary,
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
        df = cache.get(
            key=f"gold_{source}",
            fetch_fn=fetch_gold_price,
            source=source,
            period="1y",
            max_stale_days=1,
        )

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
        )
        official = cache.get(
            key="macro_fred",
            fetch_fn=fetch_macro_fred,
            start_date="2020-01-01",
            ttl=3600,
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
