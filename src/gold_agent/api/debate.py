"""辩论接口"""

import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import logging
logger = logging.getLogger(__name__)

import pandas as pd

from gold_agent.data.gold_price import fetch_gold_price
from gold_agent.data.macro import fetch_macro_yfinance
from gold_agent.data.news import fetch_news_with_sentiment
from gold_agent.data.cache import cache
from gold_agent.quant.indicators import get_indicator_summary
from gold_agent.quant.signals import generate_signal, get_signal_summary
from gold_agent.quant.predictor import predict_gold_price, get_prediction_summary
from gold_agent.debate.engine import DebateEngine

router = APIRouter(prefix="/api/debate", tags=["辩论"])


async def _build_context() -> str:
    """构建辩论上下文 — 并行获取独立数据源"""
    loop = asyncio.get_event_loop()

    async def _run_sync(fn, *args, **kwargs):
        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    # 金价、宏观、新闻 — 并行获取（三者独立）
    async def _fetch_gold():
        df = cache.get(
            key="gold_intl", fetch_fn=fetch_gold_price,
            source="intl", period="1y", max_stale_days=1,
        )
        parts = ["### 国际金价 (XAUUSD)\n" + get_indicator_summary(df)]
        signal = generate_signal(df)
        parts.append(get_signal_summary(signal))
        return "\n".join(parts), df

    async def _fetch_macro():
        macro = fetch_macro_yfinance(period="1mo")
        if not macro.empty:
            latest = macro.iloc[-1]
            lines = ["### 宏观指标 (最新值)"]
            for col in macro.columns:
                if col != "date" and latest.get(col) is not None:
                    lines.append(f"- {col}: {latest[col]:.2f}")
            return "\n".join(lines)
        return ""

    async def _fetch_news():
        news_df = fetch_news_with_sentiment()
        if not news_df.empty:
            avg = news_df["sentiment_score"].mean()
            label = "看多" if avg > 0.2 else "看空" if avg < -0.2 else "中性"
            lines = [f"### 新闻情绪 (平均得分: {avg:.3f}, 倾向: {label})"]
            for _, row in news_df.head(10).iterrows():
                lines.append(f"- [{row['sentiment_label']}] {row['title']}")
            return "\n".join(lines)
        return ""

    gold_task = asyncio.create_task(_fetch_gold())
    macro_task = asyncio.create_task(_fetch_macro())
    news_task = asyncio.create_task(_fetch_news())

    gold_result = ""
    df: pd.DataFrame = pd.DataFrame()
    try:
        gold_result, df = await _fetch_gold() if False else await gold_task
    except Exception as e:
        logger.warning(f"金价数据获取失败: {e}")

    macro_result = ""
    try:
        macro_result = await macro_task
    except Exception as e:
        logger.warning(f"宏观数据获取失败: {e}")

    news_result = ""
    try:
        news_result = await news_task
    except Exception as e:
        logger.warning(f"新闻获取失败: {e}")

    # 预测依赖金价 df，串行
    pred_result = ""
    if not df.empty:
        try:
            pred = predict_gold_price(df, days=7)
            pred_result = get_prediction_summary(pred)
        except Exception as e:
            logger.warning(f"预测失败: {e}")

    parts = [p for p in [gold_result, pred_result, macro_result, news_result] if p]
    return "\n\n---\n\n".join(parts)


@router.post("/run")
async def run_debate():
    """运行完整辩论流程"""
    try:
        logger.info("开始构建辩论上下文...")
        context = await _build_context()

        logger.info("开始辩论...")
        engine = DebateEngine()
        result = await engine.run_debate(context)

        return {
            "summary": result.to_summary(),
            "detail": result.to_dict(),
        }
    except Exception as e:
        logger.error(f"辩论失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/run/stream")
async def stream_debate():
    """SSE 流式辩论 — 逐轮推送进度"""
    stage_meta = {
        "bull": {"label": "看多方", "color": "#22c55e"},
        "bear": {"label": "看空方", "color": "#ff4444"},
        "audit": {"label": "数据审计", "color": "#3b82f6"},
        "verdict": {"label": "最终裁决", "color": "#eab308"},
    }

    async def event_stream():
        try:
            context = await _build_context()
            engine = DebateEngine()
            async for stage, data in engine.stream_debate(context):
                if stage == "complete":
                    # data 是 DebateResult
                    payload = json.dumps({
                        "summary": data.to_summary(),
                        "detail": data.to_dict(),
                    }, ensure_ascii=False)
                    yield f"event: complete\ndata: {payload}\n\n"
                else:
                    meta = stage_meta.get(stage, {"label": stage, "color": "#888"})
                    payload = json.dumps({
                        "stage": stage,
                        "label": meta["label"],
                        "color": meta["color"],
                        "result": data.parsed,
                    }, ensure_ascii=False)
                    yield f"event: stage\ndata: {payload}\n\n"
        except Exception as e:
            logger.error(f"流式辩论失败: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/quick")
async def quick_analysis():
    """快速分析 (不走辩论，直接出信号)"""
    try:
        df = cache.get(key="gold_intl", fetch_fn=fetch_gold_price, source="intl", period="1y")

        signal = generate_signal(df)
        indicators = get_indicator_summary(df)

        return {
            "signal": signal.to_dict(),
            "indicators": indicators,
        }
    except Exception as e:
        logger.error(f"快速分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
