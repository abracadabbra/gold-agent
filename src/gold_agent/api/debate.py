"""辩论接口"""

import asyncio
import json
from typing import Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import logging
logger = logging.getLogger(__name__)

import pandas as pd

from gold_agent.api.db_persistence import db_save_macro
from gold_agent.data.gold_price import (
    fetch_gold_price,
    gold_cache_key,
    period_to_months,
)
from gold_agent.data.macro import (
    fetch_macro_fred,
    fetch_macro_yfinance,
    macro_fred_cache_key,
    macro_yfinance_cache_key,
)
from gold_agent.data.news import fetch_news_with_sentiment
from gold_agent.data.cache import cache
from gold_agent.data.quality import dataframe_meta, metadata_snapshot_meta
from gold_agent.quant.indicators import get_indicator_summary
from gold_agent.quant.signals import generate_signal, get_signal_summary
from gold_agent.quant.predictor import predict_gold_price, get_prediction_summary
from gold_agent.debate.engine import DebateEngine
from gold_agent.api.factors import build_factor_snapshot

router = APIRouter(prefix="/api/debate", tags=["辩论"])

_MACRO_DATASETS = ("realtime", "official")


def _unavailable_quick_response(error: str | None = None) -> dict:
    response = {
        "signal": {
            "signal": "neutral",
            "score": 0,
            "confidence": 0,
            "reasons": ["数据不可用"],
            "stop_loss": 0,
            "take_profit": 0,
        },
        "indicators": "",
        "meta": dataframe_meta(
            pd.DataFrame(),
            source_status="unavailable",
            expected_frequency="daily",
        ),
        "unavailable": True,
    }
    if error:
        response["error"] = error
    return response


def _empty_source_meta() -> dict[str, dict[str, Any] | None]:
    return {
        "gold": None,
        "macro": None,
        "factors": None,
        "news": None,
    }


def _format_meta_summary(name: str, meta: dict[str, Any]) -> str:
    """Format a short quality summary for prompt context."""
    as_of = meta.get("as_of") or meta.get("latest_date") or "unknown"
    fetched_at = meta.get("fetched_at") or "unknown"
    cached_at = meta.get("cached_at")
    status = meta.get("source_status") or "unknown"
    stale = "yes" if meta.get("stale") else "no"
    quality = meta.get("quality_score", 0)
    rows = meta.get("row_count", 0)
    missing_rate = meta.get("missing_rate", 0.0)
    frequency = meta.get("expected_frequency") or "unknown"
    coverage_parts = []
    if "available_count" in meta:
        coverage_parts.append(
            f"available_count={meta.get('available_count')}/{meta.get('row_count')}"
        )
    if "min_required_available" in meta:
        coverage_parts.append(f"min_required_available={meta.get('min_required_available')}")
    if "coverage_satisfied" in meta:
        coverage_parts.append(f"coverage_satisfied={meta.get('coverage_satisfied')}")
    if "max_lag_days" in meta:
        coverage_parts.append(f"max_lag_days={meta.get('max_lag_days')}")
    time_parts = []
    if cached_at:
        time_parts.append(f"cached_at={cached_at}")
    if fetched_at != "unknown" and fetched_at != cached_at:
        time_parts.append(f"fetched_at={fetched_at}")
    if not time_parts:
        time_parts.append("fetched_at=unknown")
    return (
        f"- {name}: source_status={status}, stale={stale}, as_of={as_of}, "
        f"{', '.join(time_parts)}, quality_score={quality}, row_count={rows}, "
        f"missing_rate={missing_rate}, expected_frequency={frequency}"
        f"{', ' + ', '.join(coverage_parts) if coverage_parts else ''}"
    )


async def _build_context() -> tuple[str, dict[str, dict[str, Any] | None]]:
    """构建辩论上下文 — 并行获取独立数据源"""
    # 金价、宏观、新闻 — 并行获取（三者独立）
    async def _fetch_gold():
        df, meta = cache.get_with_meta(
            key=gold_cache_key("intl", "1y"),
            fetch_fn=fetch_gold_price,
            source="intl",
            period="1y",
            max_stale_days=0.1,
            months=period_to_months("1y"),
            expected_frequency="daily",
        )
        parts = [
            "### 数据质量摘要",
            _format_meta_summary("国际金价", meta),
            "",
            "### 国际金价 (XAUUSD)\n" + get_indicator_summary(df),
        ]
        signal = generate_signal(df)
        parts.append(get_signal_summary(signal))
        return "\n".join(parts), df, meta

    async def _fetch_macro():
        macro, realtime_meta = cache.get_with_meta(
            key=macro_yfinance_cache_key(period="1mo"),
            fetch_fn=fetch_macro_yfinance,
            period="1mo",
            ttl=3600,
            max_stale_days=1,
            months=period_to_months("1mo"),
            expected_frequency="daily",
            db_save_fn=lambda records: db_save_macro("yfinance", records),
        )
        official_meta: dict[str, Any] | None = None
        try:
            _, official_meta = cache.get_with_meta(
                key=macro_fred_cache_key(start_date="2020-01-01"),
                fetch_fn=fetch_macro_fred,
                start_date="2020-01-01",
                ttl=3600,
                max_stale_days=1,
                expected_frequency="mixed",
                db_save_fn=lambda records: db_save_macro("fred", records),
            )
        except Exception as e:
            logger.warning(f"官方宏观数据获取失败: {e}")
        snapshot_meta = metadata_snapshot_meta(
            {
                "realtime": realtime_meta,
                "official": official_meta,
            },
            dataset_names=_MACRO_DATASETS,
            min_required_available=len(_MACRO_DATASETS),
            expected_frequency="mixed",
        )
        if not macro.empty:
            latest = macro.iloc[-1]
            lines = [
                "### 数据质量摘要",
                _format_meta_summary("宏观快照", snapshot_meta),
                _format_meta_summary("实时宏观", realtime_meta),
                "",
                "### 宏观指标 (最新值)",
            ]
            if official_meta is not None:
                lines.insert(3, _format_meta_summary("官方宏观", official_meta))
            for col in macro.columns:
                if col != "date" and latest.get(col) is not None:
                    lines.append(f"- {col}: {latest[col]:.2f}")
            return "\n".join(lines), snapshot_meta
        return "", snapshot_meta

    async def _fetch_news():
        news_df, meta = cache.get_with_meta(
            key="news_sentiment",
            fetch_fn=fetch_news_with_sentiment,
            ttl=300,
            max_stale_days=1,
            expected_frequency="intraday",
        )
        if not news_df.empty:
            avg = news_df["sentiment_score"].mean()
            label = "看多" if avg > 0.2 else "看空" if avg < -0.2 else "中性"
            lines = [
                "### 数据质量摘要",
                _format_meta_summary("新闻情绪", meta),
                "",
                f"### 新闻情绪 (平均得分: {avg:.3f}, 倾向: {label})",
            ]
            for _, row in news_df.head(10).iterrows():
                lines.append(f"- [{row['sentiment_label']}] {row['title']}")
            return "\n".join(lines), meta
        return "", meta

    async def _fetch_factors():
        snapshot = await build_factor_snapshot()
        meta = snapshot.get("meta")
        if not isinstance(meta, dict):
            return "", None
        lines = [
            "### 数据质量摘要",
            _format_meta_summary("关键因子快照", meta),
            "",
            "### 关键因子状态",
        ]
        for name in ["cot", "fedwatch", "central_bank", "tips", "dxy"]:
            value = snapshot.get(name)
            if isinstance(value, dict):
                label = value.get("label", "未知")
                aligned_as_of = value.get("aligned_as_of") or "unknown"
                lag_days = value.get("lag_days")
                lines.append(
                    f"- {name}: label={label}, aligned_as_of={aligned_as_of}, "
                    f"lag_days={lag_days}"
                )
        return "\n".join(lines), meta

    gold_task = asyncio.create_task(_fetch_gold())
    macro_task = asyncio.create_task(_fetch_macro())
    factors_task = asyncio.create_task(_fetch_factors())
    news_task = asyncio.create_task(_fetch_news())

    gold_result = ""
    df: pd.DataFrame = pd.DataFrame()
    gold_meta: dict[str, Any] | None = None
    source_meta = _empty_source_meta()
    try:
        gold_result, df, gold_meta = await gold_task
        source_meta["gold"] = gold_meta
    except Exception as e:
        logger.warning(f"金价数据获取失败: {e}")

    macro_result = ""
    try:
        macro_result, macro_meta = await macro_task
        source_meta["macro"] = macro_meta
    except Exception as e:
        logger.warning(f"宏观数据获取失败: {e}")

    factors_result = ""
    try:
        factors_result, factors_meta = await factors_task
        source_meta["factors"] = factors_meta
    except Exception as e:
        logger.warning(f"关键因子获取失败: {e}")

    news_result = ""
    try:
        news_result, news_meta = await news_task
        source_meta["news"] = news_meta
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

    quality_block = ""
    if gold_meta is not None:
        quality_block = "\n".join(
            [
                "## 数据使用约束",
                (
                    "请优先参考 source_status=live 的数据；如果 "
                    "source_status=cache 或 db_fallback，需要优先查看 "
                    "cached_at 与 as_of，审慎降权。"
                ),
                (
                    "任何 stale=yes、quality_score<60 或 row_count 很小的数据，"
                    "都不应被当作强结论依据。"
                ),
            ]
        )

    parts = [
        p
        for p in [
            quality_block,
            gold_result,
            pred_result,
            macro_result,
            factors_result,
            news_result,
        ]
        if p
    ]
    return "\n\n---\n\n".join(parts), source_meta


@router.post("/run")
async def run_debate():
    """运行完整辩论流程"""
    try:
        logger.info("开始构建辩论上下文...")
        context, source_meta = await _build_context()

        logger.info("开始辩论...")
        engine = DebateEngine()
        result = await engine.run_debate(context)

        return {
            "summary": result.to_summary(),
            "detail": result.to_dict(),
            "meta": source_meta,
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
            context, source_meta = await _build_context()
            engine = DebateEngine()
            async for stage, data in engine.stream_debate(context):
                if stage == "complete":
                    # data 是 DebateResult
                    payload = json.dumps({
                        "summary": data.to_summary(),
                        "detail": data.to_dict(),
                        "meta": source_meta,
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
        df, meta = cache.get_with_meta(
            key=gold_cache_key("intl", "1y"),
            fetch_fn=fetch_gold_price,
            source="intl",
            period="1y",
            max_stale_days=0.1,
            months=period_to_months("1y"),
            expected_frequency="daily",
        )

        if df.empty:
            return _unavailable_quick_response("数据获取失败")

        signal = generate_signal(df)
        indicators = get_indicator_summary(df)

        return {
            "signal": signal.to_dict(),
            "indicators": indicators,
            "meta": meta,
        }
    except Exception as e:
        logger.error(f"快速分析失败: {e}")
        return _unavailable_quick_response(str(e))
