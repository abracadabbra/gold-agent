"""分析接口 — 金价数据 + 技术指标 + 信号"""

from datetime import datetime

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
import logging
logger = logging.getLogger(__name__)


from gold_agent.utils.json import json_safe as _json_safe

from gold_agent.data.gold_price import (
    fetch_gold_price,
    gold_cache_key,
    period_to_days,
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
from gold_agent.data.quality import (
    align_series_as_of,
    dataframe_meta,
    metadata_snapshot_meta,
    with_alignment_info,
)
from gold_agent.api.db_persistence import db_save_macro
from gold_agent.db.session import SessionLocal
from gold_agent.db.repository import (
    get_data_fetch_runs_overview,
    save_gold_prices,
    save_news_articles,
)
from gold_agent.db.models import GoldPrice
from gold_agent.quant.indicators import compute_indicators, get_indicator_summary
from gold_agent.quant.signals import (
    evaluate_signal_history,
    generate_signal,
    get_signal_summary,
)
from gold_agent.quant.predictor import (
    evaluate_naive_forecast,
    get_prediction_summary,
    predict_gold_price,
)

router = APIRouter(prefix="/api/analysis", tags=["分析"])

_FALLBACK_SOURCES = {"intl": "shfe", "shfe": "intl", "gld": "shfe"}
_INDICATOR_WARMUP_DAYS = 60
_SIGNAL_EVALUATION_MIN_SAMPLES = 30
_SIGNAL_EVALUATION_MIN_DIRECTIONAL_SAMPLES = 10
_PREDICTION_EVALUATION_MIN_SAMPLES = 30
_PREDICTION_EVALUATION_MIN_BASELINES = 3
_MACRO_DATASETS = ("realtime", "official")
_NEWS_MIN_ARTICLES = 5

# API source name → DB source name
_SOURCE_TO_DB = {"intl": "xauusd", "gld": "etf", "shfe": "spot_cny"}
_DB_TO_SOURCE = {v: k for k, v in _SOURCE_TO_DB.items()}


def _meta_datetime(meta: dict | None, key: str) -> datetime | None:
    if not meta:
        return None
    value = meta.get(key)
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _indicator_result_meta(indicators, price_df: pd.DataFrame, source_meta: dict | None) -> dict:
    """Describe quality of the computed indicator snapshot, not the raw price input."""
    indicator_fields = list(getattr(indicators, "__dataclass_fields__", {}).keys())
    values: dict[str, float | None] = {}
    missing: list[str] = []

    for name in indicator_fields:
        series = getattr(indicators, name, None)
        if not isinstance(series, pd.Series) or series.empty:
            missing.append(name)
            values[name] = None
            continue
        latest = series.iloc[-1]
        if pd.isna(latest):
            missing.append(name)
            values[name] = None
        else:
            values[name] = float(latest)

    if not values:
        values = dict(indicators.to_dict())
        missing = []

    if values:
        latest_date = pd.to_datetime(price_df["date"].max(), errors="coerce")
        meta_df = pd.DataFrame([{**values, "date": latest_date}])
    else:
        meta_df = pd.DataFrame()

    meta = dataframe_meta(
        meta_df,
        max_stale_days=0.1,
        source_status=(source_meta or {}).get("source_status", "live"),
        fetched_at=_meta_datetime(source_meta, "fetched_at"),
        cached_at=_meta_datetime(source_meta, "cached_at"),
        expected_frequency="daily",
    )
    meta["available_indicators"] = len([v for v in values.values() if v is not None])
    meta["missing_indicators"] = missing
    meta["warmup_required_days"] = _INDICATOR_WARMUP_DAYS
    meta["warmup_satisfied"] = len(price_df) >= _INDICATOR_WARMUP_DAYS
    return meta


def _signal_evaluation_meta(
    evaluation: dict,
    price_df: pd.DataFrame,
    source_meta: dict | None,
) -> dict:
    """Describe quality of the rolling signal evaluation result."""
    meta = dataframe_meta(
        price_df,
        max_stale_days=None,
        source_status=(source_meta or {}).get("source_status", "live"),
        fetched_at=_meta_datetime(source_meta, "fetched_at"),
        cached_at=_meta_datetime(source_meta, "cached_at"),
        expected_frequency="rolling_evaluation",
    )

    sample_size = int(evaluation.get("sample_size") or 0)
    directional_samples = int(evaluation.get("directional_samples") or 0)
    sample_satisfied = sample_size >= _SIGNAL_EVALUATION_MIN_SAMPLES
    directional_satisfied = directional_samples >= _SIGNAL_EVALUATION_MIN_DIRECTIONAL_SAMPLES

    quality_score = int((source_meta or {}).get("quality_score", meta["quality_score"]) or 0)
    quality_score = min(quality_score, int(meta["quality_score"]))
    if not sample_satisfied:
        quality_score -= 30
    if not directional_satisfied:
        quality_score -= 20

    meta["quality_score"] = max(0, quality_score)
    meta["row_count"] = sample_size
    meta["sample_size"] = sample_size
    meta["directional_samples"] = directional_samples
    meta["min_required_samples"] = _SIGNAL_EVALUATION_MIN_SAMPLES
    meta["min_required_directional_samples"] = _SIGNAL_EVALUATION_MIN_DIRECTIONAL_SAMPLES
    meta["sample_satisfied"] = sample_satisfied
    meta["directional_satisfied"] = directional_satisfied
    return meta


def _news_sentiment_meta(df: pd.DataFrame, source_meta: dict | None) -> dict:
    """Describe whether the aggregate news sentiment is backed by enough articles."""
    meta = dict(source_meta or {})
    sample_size = int(len(df))
    if not meta:
        meta = dataframe_meta(
            df,
            max_stale_days=1,
            source_status="unavailable" if df.empty else "live",
            expected_frequency="intraday",
        )

    if "sentiment_score" in df.columns:
        valid_scores = pd.to_numeric(df["sentiment_score"], errors="coerce")
        valid_sentiment_count = int(valid_scores.notna().sum())
    else:
        valid_sentiment_count = 0
    sample_satisfied = valid_sentiment_count >= _NEWS_MIN_ARTICLES
    quality_score = int(meta.get("quality_score") or 0)
    if not sample_satisfied:
        quality_score -= 30

    meta["quality_score"] = max(0, quality_score)
    meta["sample_size"] = sample_size
    meta["valid_sentiment_count"] = valid_sentiment_count
    meta["min_required_articles"] = _NEWS_MIN_ARTICLES
    meta["sample_satisfied"] = sample_satisfied
    meta["conclusion_suitable"] = (
        sample_satisfied
        and not bool(meta.get("stale"))
        and meta["quality_score"] >= 60
    )
    return meta


def _prediction_evaluation_meta(
    evaluation: dict,
    price_df: pd.DataFrame,
    source_meta: dict | None,
) -> dict:
    """Describe whether historical prediction metrics are suitable for conclusions."""
    meta = dataframe_meta(
        price_df,
        max_stale_days=None,
        source_status=(source_meta or {}).get("source_status", "live"),
        fetched_at=_meta_datetime(source_meta, "fetched_at"),
        cached_at=_meta_datetime(source_meta, "cached_at"),
        expected_frequency="forecast_evaluation",
    )

    sample_size = int(evaluation.get("sample_size") or 0)
    baselines = evaluation.get("baselines") or []
    baseline_count = len(baselines) if isinstance(baselines, list) else 0
    sample_satisfied = sample_size >= _PREDICTION_EVALUATION_MIN_SAMPLES
    baselines_satisfied = baseline_count >= _PREDICTION_EVALUATION_MIN_BASELINES

    quality_score = int((source_meta or {}).get("quality_score", meta["quality_score"]) or 0)
    quality_score = min(quality_score, int(meta["quality_score"]))
    if not sample_satisfied:
        quality_score -= 30
    if not baselines_satisfied:
        quality_score -= 20

    meta["quality_score"] = max(0, quality_score)
    meta["row_count"] = sample_size
    meta["sample_size"] = sample_size
    meta["min_required_samples"] = _PREDICTION_EVALUATION_MIN_SAMPLES
    meta["baseline_count"] = baseline_count
    meta["min_required_baselines"] = _PREDICTION_EVALUATION_MIN_BASELINES
    meta["sample_satisfied"] = sample_satisfied
    meta["baselines_satisfied"] = baselines_satisfied
    meta["conclusion_suitable"] = (
        sample_satisfied
        and baselines_satisfied
        and not bool(meta.get("stale"))
        and meta["quality_score"] >= 60
    )
    return meta


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
        raise


def _load_gold_from_db(source: str, period: str) -> tuple[pd.DataFrame, datetime | None]:
    """从 DB 加载历史金价数据作为兜底"""
    db_source = _SOURCE_TO_DB.get(source, source)
    days = period_to_days(period)
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
                return pd.DataFrame(), None
            df = pd.DataFrame([
                {"date": r.date, "open": r.open, "high": r.high,
                 "low": r.low, "close": r.close, "volume": r.volume}
                for r in rows
            ])
            latest_created_at = max(
                (
                    pd.to_datetime(r.created_at).to_pydatetime()
                    for r in rows
                    if getattr(r, "created_at", None) is not None
                ),
                default=None,
            )
            logger.info(f"从 DB 加载 {source}: {len(df)} 条记录")
            return df, latest_created_at
    except Exception as e:
        logger.warning(f"DB 读取金价失败 ({source}): {e}")
        return pd.DataFrame(), None


def _db_save_news(records: list[dict]) -> None:
    """将采集到的新闻写入 DB。"""
    try:
        with SessionLocal() as db:
            save_news_articles(db, records)
    except Exception as e:
        logger.warning(f"DB 保存新闻失败: {e}")
        raise


def _fetch_gold_with_fallback(source: str, period: str) -> tuple[pd.DataFrame, str]:
    df, actual_source, _ = _fetch_gold_with_fallback_meta(source, period)
    return df, actual_source


def _fetch_gold_with_fallback_meta(source: str, period: str) -> tuple[pd.DataFrame, str, dict]:
    """获取金价数据: live → 备选源 → DB 历史兜底"""
    months = period_to_months(period)

    def _fetch_source(candidate: str) -> tuple[pd.DataFrame, dict]:
        try:
            return cache.get_with_meta(
                key=gold_cache_key(candidate, period),
                fetch_fn=fetch_gold_price,
                source=candidate,
                period=period,
                max_stale_days=0.1,
                months=months,
                expected_frequency="daily",
                db_save_fn=lambda records: _db_save_gold(candidate, records),
            )
        except Exception as e:
            logger.warning(f"数据源 {candidate} 获取失败: {e}")
            return pd.DataFrame(), dataframe_meta(
                pd.DataFrame(),
                max_stale_days=0.1,
                source_status="unavailable",
                expected_frequency="daily",
            )

    df, meta = _fetch_source(source)
    if not df.empty:
        return df, source, meta

    fallback = _FALLBACK_SOURCES.get(source)
    if fallback:
        logger.warning(f"数据源 {source} 不可用，降级到 {fallback}")
        df, meta = _fetch_source(fallback)
        if not df.empty:
            return df, fallback, meta

    # 最后兜底：从 DB 读历史数据
    df, db_cached_at = _load_gold_from_db(source, period)
    if not df.empty:
        logger.info(f"使用 DB 历史数据兜底: {source}")
        return df, source, dataframe_meta(
            df,
            max_stale_days=0.1,
            source_status="db_fallback",
            fetched_at=db_cached_at,
            cached_at=db_cached_at,
            expected_frequency="daily",
        )

    # 连 DB 都没有，试备选源的 DB 数据
    if fallback:
        df, db_cached_at = _load_gold_from_db(fallback, period)
        if not df.empty:
            logger.info(f"使用 DB 历史数据兜底: {fallback}")
            return df, fallback, dataframe_meta(
                df,
                max_stale_days=0.1,
                source_status="db_fallback",
                fetched_at=db_cached_at,
                cached_at=db_cached_at,
                expected_frequency="daily",
            )

    return df, source, dataframe_meta(
        df,
        max_stale_days=0.1,
        source_status="unavailable",
        expected_frequency="daily",
    )


@router.get("/gold")
async def get_gold_price(
    source: str = Query("intl", description="数据源: intl/shfe/gld"),
    period: str = Query("1y", description="时间范围: 1mo/3mo/6mo/1y/2y/5y"),
):
    """获取金价数据"""
    try:
        df, actual_source, meta = _fetch_gold_with_fallback_meta(source, period)
        return {
            "source": actual_source,
            "records": len(df),
            "latest_price": float(df["close"].iloc[-1]) if not df.empty else None,
            "data": df.tail(100).to_dict(orient="records"),
            "meta": meta,
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
        df, _, meta = _fetch_gold_with_fallback_meta(source, period)

        if df.empty:
            return {
                "price": None,
                "indicators": {},
                "summary": f"数据源 {source} 暂时不可用，请稍后重试或切换数据源",
                "unavailable": True,
                "meta": meta,
            }

        indicators = compute_indicators(df)
        indicator_meta = _indicator_result_meta(indicators, df, meta)
        summary = get_indicator_summary(df)

        return {
            "price": float(df["close"].iloc[-1]),
            "indicators": indicators.to_dict(),
            "summary": summary,
            "meta": meta,
            "indicator_meta": indicator_meta,
        }
    except Exception as e:
        logger.error(f"计算指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signal")
async def get_signal(
    source: str = Query("intl", description="数据源"),
    period: str = Query("1y", description="时间范围"),
    as_of: str | None = Query(None, description="对齐锚点日期 YYYY-MM-DD"),
):
    """获取交易信号"""
    try:
        df, _, meta = _fetch_gold_with_fallback_meta(source, period)

        if df.empty:
            return {
                "signal": {"signal": 0, "score": 0, "factors": {}},
                "summary": f"数据源 {source} 暂时不可用，请稍后重试或切换数据源",
                "macro_factors": None,
                "macro_factors_meta": None,
                "evaluation": None,
                "evaluation_meta": None,
                "unavailable": True,
                "meta": meta,
            }

        # 获取宏观数据（FRED TIPS 实际利率等）作为可选因子
        macro_values: dict[str, float] | None = None
        macro_meta: dict | None = None
        try:
            fred_df, macro_meta = cache.get_with_meta(
                key=macro_fred_cache_key(start_date="2024-01-01"),
                fetch_fn=fetch_macro_fred,
                start_date="2024-01-01",
                ttl=3600,
                max_stale_days=1,
                expected_frequency="daily",
                db_save_fn=lambda records: db_save_macro("fred", records),
            )
            if not fred_df.empty and "tips_yield" in fred_df.columns:
                anchor_date = as_of or df["date"].max()
                aligned = align_series_as_of(
                    fred_df,
                    anchor_date=anchor_date,
                    required_cols=["tips_yield"],
                )
                if aligned:
                    macro_values = with_alignment_info(
                        {"tips_yield": float(aligned["row"]["tips_yield"])},
                        aligned,
                    )
        except Exception:
            logger.warning("获取 FRED 宏观数据失败，信号将不含宏观因子")

        signal = generate_signal(df, macro_values=macro_values)
        summary = get_signal_summary(signal)
        evaluation = evaluate_signal_history(df, horizon=5, window=120, min_history=60)
        evaluation_meta = _signal_evaluation_meta(evaluation, df, meta)

        return {
            "signal": signal.to_dict(),
            "summary": summary,
            "macro_factors": macro_values,
            "macro_factors_meta": macro_meta,
            "evaluation": evaluation,
            "evaluation_meta": evaluation_meta,
            "meta": meta,
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
        df, _, meta = _fetch_gold_with_fallback_meta(source, "1y")

        if df.empty:
            return {
                "prediction": [],
                "history": [],
                "trend": "unknown",
                "summary": f"数据源 {source} 暂时不可用，请稍后重试或切换数据源",
                "unavailable": True,
                "meta": meta,
                "regressor_meta": None,
                "regressor_alignment": {},
                "evaluation": None,
                "evaluation_meta": None,
            }

        # 获取宏观数据作为回归因子（使用缓存）
        macro_df, regressor_meta = cache.get_with_meta(
            key=macro_yfinance_cache_key(period="2y"),
            fetch_fn=fetch_macro_yfinance,
            period="2y",
            ttl=3600,
            max_stale_days=1,
            months=period_to_months("2y"),
            expected_frequency="daily",
            db_save_fn=lambda records: db_save_macro("yfinance", records),
        )
        regressors = {}
        regressor_alignment = {}
        if not macro_df.empty and "date" in macro_df.columns:
            gold_as_of = pd.to_datetime(df["date"].max())
            for col in ["usd_index", "vix", "us_10y"]:
                if col in macro_df.columns:
                    aligned = align_series_as_of(
                        macro_df,
                        anchor_date=gold_as_of,
                        required_cols=[col],
                    )
                    series = macro_df.set_index("date")[col].dropna()
                    series = series[series.index <= gold_as_of]
                    if not series.empty:
                        regressors[col] = series
                    if aligned:
                        regressor_alignment[col] = {
                            "aligned_as_of": aligned["aligned_as_of"],
                            "lag_days": aligned["lag_days"],
                        }

        prediction = predict_gold_price(df, days=days, regressors=regressors)
        summary = get_prediction_summary(prediction)
        evaluation = evaluate_naive_forecast(df, horizon=1, window=60)
        evaluation_meta = _prediction_evaluation_meta(evaluation, df, meta)

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
            "meta": meta,
            "regressor_meta": regressor_meta,
            "regressor_alignment": regressor_alignment,
            "evaluation": evaluation,
            "evaluation_meta": evaluation_meta,
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
    def _unavailable_macro_meta(expected_frequency: str) -> dict:
        return dataframe_meta(
            pd.DataFrame(),
            source_status="unavailable",
            expected_frequency=expected_frequency,
        )

    try:
        realtime, realtime_meta = cache.get_with_meta(
            key=macro_yfinance_cache_key(period=period),
            fetch_fn=fetch_macro_yfinance,
            period=period,
            ttl=3600,
            max_stale_days=1,
            months=period_to_months(period),
            expected_frequency="daily",
            db_save_fn=lambda records: db_save_macro("yfinance", records),
        )
    except Exception as e:
        logger.warning(f"获取 yfinance 宏观数据失败: {e}")
        realtime = pd.DataFrame()
        realtime_meta = _unavailable_macro_meta("daily")

    try:
        official, official_meta = cache.get_with_meta(
            key=macro_fred_cache_key(start_date="2020-01-01"),
            fetch_fn=fetch_macro_fred,
            start_date="2020-01-01",
            ttl=3600,
            max_stale_days=1,
            expected_frequency="mixed",
            db_save_fn=lambda records: db_save_macro("fred", records),
        )
    except Exception as e:
        logger.warning(f"获取 FRED 宏观数据失败: {e}")
        official = pd.DataFrame()
        official_meta = _unavailable_macro_meta("mixed")

    def _format(df: pd.DataFrame, meta: dict) -> dict:
        if df.empty:
            return {"records": 0, "columns": [], "data": [], "meta": meta}
        d = df.tail(100).copy()
        if "date" in d.columns:
            d["date"] = d["date"].dt.strftime("%Y-%m-%d")
        return {
            "records": len(d),
            "columns": list(d.columns),
            "data": _json_safe(d),
            "meta": meta,
        }

    return {
        "realtime": _format(realtime, realtime_meta),
        "official": _format(official, official_meta),
        "meta": metadata_snapshot_meta(
            {
                "realtime": realtime_meta,
                "official": official_meta,
            },
            dataset_names=_MACRO_DATASETS,
            min_required_available=len(_MACRO_DATASETS),
            expected_frequency="mixed",
        ),
    }


@router.get("/news")
async def get_news():
    """获取新闻情绪"""
    try:
        df, meta = cache.get_with_meta(
            key="news_sentiment",
            fetch_fn=fetch_news_with_sentiment,
            ttl=300,
            max_stale_days=1,
            expected_frequency="intraday",
            db_save_fn=_db_save_news,
        )
        avg_score = float(df["sentiment_score"].mean()) if not df.empty else 0
        sentiment_meta = _news_sentiment_meta(df, meta)

        return {
            "total": len(df),
            "avg_sentiment": avg_score,
            "label": "bullish" if avg_score > 0.2 else "bearish" if avg_score < -0.2 else "neutral",
            "news": _json_safe(df.head(20)),
            "meta": sentiment_meta,
        }
    except Exception as e:
        logger.error(f"获取新闻失败: {e}")
        meta = _news_sentiment_meta(
            pd.DataFrame(),
            dataframe_meta(
                pd.DataFrame(),
                source_status="unavailable",
                expected_frequency="intraday",
            ),
        )
        return {
            "total": 0,
            "avg_sentiment": 0,
            "label": "neutral",
            "news": [],
            "meta": meta,
            "unavailable": True,
            "error": str(e),
        }


@router.get("/fetch-runs")
async def get_fetch_runs(
    limit: int = Query(20, ge=1, le=100, description="最近抓取记录条数"),
    cache_key: str | None = Query(None, description="按 cache_key 过滤"),
):
    """读取数据抓取运行状态，便于观察稳定性与新鲜度。"""
    try:
        with SessionLocal() as db:
            overview = get_data_fetch_runs_overview(
                db,
                limit=limit,
                cache_key=cache_key,
            )
        return {
            **overview,
            "filters": {
                "limit": limit,
                "cache_key": cache_key,
            },
        }
    except Exception as e:
        logger.error(f"获取抓取运行状态失败: {e}")
        return {
            "recent": [],
            "summary": [],
            "filters": {
                "limit": limit,
                "cache_key": cache_key,
            },
            "source_status": "unavailable",
            "unavailable": True,
            "error": str(e),
        }
