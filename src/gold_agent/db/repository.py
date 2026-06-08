"""数据仓库 — 数据持久化到 DB"""

import logging
import math
from datetime import datetime, UTC

import pandas as pd
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from gold_agent.db.models import (
    DataFetchRun,
    GoldPrice,
    MacroData,
    NewsArticle,
    TechnicalIndicator,
    TradeSignal,
)
from gold_agent.utils.json import json_safe

logger = logging.getLogger(__name__)


def _iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _fetch_run_to_dict(fetch_run: DataFetchRun) -> dict:
    return {
        "id": fetch_run.id,
        "cache_key": fetch_run.cache_key,
        "fetcher": fetch_run.fetcher,
        "status": fetch_run.status,
        "record_count": fetch_run.record_count,
        "duration_ms": fetch_run.duration_ms,
        "error_message": fetch_run.error_message,
        "started_at": _iso_or_none(fetch_run.started_at),
        "finished_at": _iso_or_none(fetch_run.finished_at),
        "created_at": _iso_or_none(fetch_run.created_at),
    }


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """将 DataFrame 转为 dict 列表，处理 NaN/NaT/Inf"""
    return json_safe(df)


def _dialect_name(db: Session) -> str:
    bind = getattr(db, "bind", None)
    if bind is not None:
        try:
            dialect_name = bind.dialect.name
            if isinstance(dialect_name, str):
                return dialect_name
        except Exception:
            pass
    return "sqlite"


def _bulk_insert_do_nothing(
    db: Session,
    model,
    rows: list[dict],
    *,
    index_elements: list[str],
) -> int:
    if not rows:
        return 0

    dialect_name = _dialect_name(db)
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert

    stmt = insert(model).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=index_elements)
    result = db.execute(stmt)
    db.commit()
    return int(result.rowcount or 0)


def _bulk_upsert(
    db: Session,
    model,
    rows: list[dict],
    *,
    index_elements: list[str],
    update_columns: list[str],
    preserve_existing_on_null: bool = False,
) -> int:
    if not rows:
        return 0

    dialect_name = _dialect_name(db)
    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert

    stmt = insert(model).values(rows)
    update_values = {}
    for column in update_columns:
        excluded_value = getattr(stmt.excluded, column)
        if preserve_existing_on_null:
            update_values[column] = func.coalesce(excluded_value, getattr(model, column))
        else:
            update_values[column] = excluded_value
    stmt = stmt.on_conflict_do_update(
        index_elements=index_elements,
        set_=update_values,
    )
    result = db.execute(stmt)
    db.commit()
    return int(result.rowcount or 0)


def _trade_signal_row(signal: dict) -> dict:
    date = pd.to_datetime(signal.get("date", datetime.now(UTC))).to_pydatetime()
    return {
        "date": date,
        "source": signal.get("source", "intl"),
        "signal_type": signal.get("signal", "neutral"),
        "score": signal.get("score", 0),
        "confidence": signal.get("confidence", 0.5),
        "reasons": signal.get("reasons", []),
        "stop_loss": signal.get("stop_loss"),
        "take_profit": signal.get("take_profit"),
    }


def _finite_float_or_none(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def save_gold_prices(db: Session, records: list[dict]) -> int:
    """批量写入金价数据，按 (date, source) 去重"""
    rows: list[dict] = []
    for rec in records:
        date_str = rec.get("date")
        date = pd.to_datetime(date_str).to_pydatetime()  # type: ignore[arg-type]
        source = rec.get("source", "intl")
        rows.append(
            {
                "date": date,
                "source": source,
                "open": rec.get("open"),
                "high": rec.get("high"),
                "low": rec.get("low"),
                "close": rec.get("close"),
                "volume": rec.get("volume"),
            }
        )

    saved = _bulk_upsert(
        db,
        GoldPrice,
        rows,
        index_elements=["source", "date"],
        update_columns=["open", "high", "low", "close", "volume"],
    )
    if saved:
        logger.debug(f"DB 写入 GoldPrice: {saved} 行")
    return saved


def save_technical_indicators(db: Session, records: list[dict]) -> int:
    """批量写入技术指标，按 (date, source) 去重"""
    rows: list[dict] = []
    for rec in records:
        date_str = rec.get("date")
        date = pd.to_datetime(date_str).to_pydatetime()  # type: ignore[arg-type]
        source = rec.get("source", "intl")
        rows.append(
            {
                "date": date,
                "source": source,
                "ma5": rec.get("ma5"),
                "ma10": rec.get("ma10"),
                "ma20": rec.get("ma20"),
                "ma60": rec.get("ma60"),
                "ema12": rec.get("ema12"),
                "ema26": rec.get("ema26"),
                "macd_line": rec.get("macd_line"),
                "macd_signal": rec.get("macd_signal"),
                "macd_hist": rec.get("macd_histogram", rec.get("macd_hist")),
                "rsi14": rec.get("rsi14"),
                "stoch_k": rec.get("stoch_k"),
                "stoch_d": rec.get("stoch_d"),
                "bb_upper": rec.get("bb_upper"),
                "bb_mid": rec.get("bb_middle", rec.get("bb_mid")),
                "bb_lower": rec.get("bb_lower"),
                "atr14": rec.get("atr14"),
                "adx": rec.get("adx"),
                "supertrend": rec.get("supertrend"),
                "supertrend_dir": rec.get("supertrend_direction", rec.get("supertrend_dir")),
                "obv": rec.get("obv"),
            }
        )

    saved = _bulk_upsert(
        db,
        TechnicalIndicator,
        rows,
        index_elements=["source", "date"],
        update_columns=[
            "ma5",
            "ma10",
            "ma20",
            "ma60",
            "ema12",
            "ema26",
            "macd_line",
            "macd_signal",
            "macd_hist",
            "rsi14",
            "stoch_k",
            "stoch_d",
            "bb_upper",
            "bb_mid",
            "bb_lower",
            "atr14",
            "adx",
            "supertrend",
            "supertrend_dir",
            "obv",
        ],
    )
    if saved:
        logger.debug(f"DB 写入 TechnicalIndicator: {saved} 行")
    return saved


def save_trade_signal(db: Session, signal: dict) -> bool:
    """写入单条交易信号"""
    row = _trade_signal_row(signal)
    saved = _bulk_upsert(
        db,
        TradeSignal,
        [row],
        index_elements=["source", "date"],
        update_columns=[
            "signal_type",
            "score",
            "confidence",
            "reasons",
            "stop_loss",
            "take_profit",
        ],
    )
    if not saved:
        return False
    logger.debug(f"DB 写入 TradeSignal: {row['signal_type']} @ {row['date']}")
    return True


def save_macro_data(
    db: Session,
    records: list[dict],
    indicator_col: str = "indicator",
    source: str | None = None,
) -> int:
    """批量写入宏观数据，支持长表或宽表，按 (source, indicator, date) upsert。"""
    rows: list[dict] = []
    for rec in records:
        date_str = rec.get("date")
        if date_str is None:
            continue
        date = pd.to_datetime(date_str).to_pydatetime()  # type: ignore[arg-type]
        row_source = source or rec.get("source", "yfinance")

        has_indicator_field = indicator_col in rec or "indicator" in rec
        indicator = rec.get(indicator_col) or rec.get("indicator", "")
        if has_indicator_field and not indicator:
            continue
        if indicator:
            value = rec.get("value")
            if value is None:
                value = rec.get(indicator)
            numeric_value = _finite_float_or_none(value)
            if numeric_value is None:
                continue

            rows.append(
                {
                    "date": date,
                    "indicator": indicator,
                    "value": numeric_value,
                    "source": row_source,
                }
            )
            continue

        for key, value in rec.items():
            if key in {"date", "source", "created_at"}:
                continue
            numeric_value = _finite_float_or_none(value)
            if numeric_value is None:
                continue
            rows.append(
                {
                    "date": date,
                    "indicator": key,
                    "value": numeric_value,
                    "source": row_source,
                }
            )

    saved = _bulk_upsert(
        db,
        MacroData,
        rows,
        index_elements=["source", "indicator", "date"],
        update_columns=["value"],
    )
    if saved:
        logger.debug(f"DB 写入 MacroData: {saved} 行")
    return saved


def save_news_articles(db: Session, records: list[dict]) -> int:
    """批量写入新闻，优先按 (source, link) 去重，无 link 时退回 title 去重"""
    linked_rows: list[dict] = []
    saved = 0
    for rec in records:
        title = rec.get("title", "").strip()
        if not title:
            continue
        link = (rec.get("link") or "").strip()
        source = rec.get("source")
        pub_date = rec.get("published_date") or rec.get("published")
        published = pd.to_datetime(pub_date).to_pydatetime() if pub_date else None
        row = {
            "published_date": published,
            "title": title,
            "link": link or None,
            "source": source,
            "sentiment_score": rec.get("sentiment_score"),
            "sentiment_label": rec.get("sentiment_label"),
            "bull_hits": rec.get("bull_hits"),
            "bear_hits": rec.get("bear_hits"),
        }
        if source and link:
            linked_rows.append(row)
            continue

        query = db.query(NewsArticle)
        if source:
            query = query.filter(NewsArticle.source == source)
        existing = query.filter(NewsArticle.title == title).first()
        if existing:
            continue
        db.add(NewsArticle(**row))
        saved += 1

    linked_saved = _bulk_upsert(
        db,
        NewsArticle,
        linked_rows,
        index_elements=["source", "link"],
        update_columns=[
            "published_date",
            "title",
            "sentiment_score",
            "sentiment_label",
        ],
        preserve_existing_on_null=True,
    )
    total_saved = saved + linked_saved
    if saved:
        db.commit()
    if total_saved:
        logger.debug(f"DB 写入 NewsArticle: {total_saved} 行")
    return total_saved


def save_data_fetch_run(db: Session, run: dict) -> DataFetchRun:
    """写入单条数据采集运行记录"""
    fetch_run = DataFetchRun(
        cache_key=run["cache_key"],
        fetcher=run["fetcher"],
        status=run["status"],
        record_count=int(run.get("record_count", 0)),
        duration_ms=float(run["duration_ms"]),
        error_message=run.get("error_message"),
        started_at=run["started_at"],
        finished_at=run["finished_at"],
    )
    db.add(fetch_run)
    db.commit()
    logger.debug(
        "DB 写入 DataFetchRun: %s status=%s records=%s",
        fetch_run.cache_key,
        fetch_run.status,
        fetch_run.record_count,
    )
    return fetch_run


def get_data_fetch_runs_overview(
    db: Session,
    *,
    limit: int = 20,
    cache_key: str | None = None,
) -> dict[str, list[dict]]:
    """读取最近抓取记录，并按 cache_key 聚合运行概览。"""
    recent_query = db.query(DataFetchRun)
    if cache_key:
        recent_query = recent_query.filter(DataFetchRun.cache_key == cache_key)
    recent_rows = (
        recent_query
        .order_by(DataFetchRun.started_at.desc(), DataFetchRun.id.desc())
        .limit(limit)
        .all()
    )

    summary_query = db.query(
        DataFetchRun.cache_key.label("cache_key"),
        func.count(DataFetchRun.id).label("total_runs"),
        func.sum(case((DataFetchRun.status == "success", 1), else_=0)).label("success_count"),
        func.sum(
            case(
                (DataFetchRun.status.in_(["failure", "persist_failure"]), 1),
                else_=0,
            )
        ).label("failure_count"),
        func.avg(DataFetchRun.duration_ms).label("avg_duration_ms"),
    )
    if cache_key:
        summary_query = summary_query.filter(DataFetchRun.cache_key == cache_key)
    summary_rows = summary_query.group_by(DataFetchRun.cache_key).all()

    latest_query = db.query(
        DataFetchRun.cache_key.label("cache_key"),
        func.max(DataFetchRun.started_at).label("latest_started_at"),
    )
    if cache_key:
        latest_query = latest_query.filter(DataFetchRun.cache_key == cache_key)
    latest_subquery = latest_query.group_by(DataFetchRun.cache_key).subquery()

    latest_rows = (
        db.query(DataFetchRun)
        .join(
            latest_subquery,
            and_(
                DataFetchRun.cache_key == latest_subquery.c.cache_key,
                DataFetchRun.started_at == latest_subquery.c.latest_started_at,
            ),
        )
        .order_by(DataFetchRun.started_at.desc(), DataFetchRun.id.desc())
        .all()
    )

    latest_by_key: dict[str, DataFetchRun] = {}
    for row in latest_rows:
        existing = latest_by_key.get(row.cache_key)
        current_key = (row.started_at, row.id or 0)
        existing_key = (
            existing.started_at,
            existing.id or 0,
        ) if existing is not None else None
        if existing is None or current_key > existing_key:
            latest_by_key[row.cache_key] = row

    summary: list[dict] = []
    for row in summary_rows:
        latest = latest_by_key.get(row.cache_key)
        total_runs = int(row.total_runs or 0)
        success_count = int(row.success_count or 0)
        failure_count = int(row.failure_count or 0)
        success_rate = round((success_count / total_runs) * 100, 1) if total_runs else 0.0
        summary.append(
            {
                "cache_key": row.cache_key,
                "fetcher": latest.fetcher if latest else None,
                "total_runs": total_runs,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_rate,
                "avg_duration_ms": round(float(row.avg_duration_ms or 0.0), 3),
                "last_status": latest.status if latest else None,
                "last_error_message": latest.error_message if latest else None,
                "last_record_count": latest.record_count if latest else None,
                "last_started_at": _iso_or_none(latest.started_at if latest else None),
                "last_finished_at": _iso_or_none(latest.finished_at if latest else None),
            }
        )

    summary.sort(
        key=lambda item: (item["last_started_at"] or "", item["cache_key"]),
        reverse=True,
    )
    return {
        "recent": [_fetch_run_to_dict(row) for row in recent_rows],
        "summary": summary,
    }


def get_table_stats(db: Session) -> dict:
    """获取各表记录数"""
    from gold_agent.db.models import get_table_stats
    return get_table_stats(db)
