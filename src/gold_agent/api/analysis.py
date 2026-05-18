"""分析接口 — 金价数据 + 技术指标 + 信号"""

from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
import logging
logger = logging.getLogger(__name__)


def _json_safe(df: pd.DataFrame) -> list[dict[str, Any]]:
    """将 DataFrame 转为 JSON-safe 字典列表"""
    return df.where(df.notna(), None).astype(object).where(df.notna(), None).to_dict(orient="records")  # noqa: E501

from gold_agent.data.gold_price import fetch_gold_price
from gold_agent.data.macro import fetch_macro_yfinance, fetch_all_macro
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
            period=period,
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
            key=f"gold_{source}_2y",
            fetch_fn=fetch_gold_price,
            source=source,
            period="2y",
        )

        # 获取宏观数据作为回归因子
        macro_df = fetch_macro_yfinance(period="2y")
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

        return {
            "prediction": _json_safe(forecast),
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
        data = fetch_all_macro(period=period)
        realtime = data["realtime"]
        official = data["official"]
        return {
            "realtime": {
                "records": len(realtime),
                "columns": list(realtime.columns) if not realtime.empty else [],
                "data": _json_safe(realtime.tail(100)),
            },
            "official": {
                "records": len(official),
                "columns": list(official.columns) if not official.empty else [],
                "data": _json_safe(official.tail(100)),
            },
        }
    except Exception as e:
        logger.error(f"获取宏观数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news")
async def get_news():
    """获取新闻情绪"""
    try:
        df = fetch_news_with_sentiment()
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
