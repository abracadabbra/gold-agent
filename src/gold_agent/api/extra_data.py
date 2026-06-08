"""补充数据聚合接口 — GET /api/analysis/extra"""

import asyncio
import logging
from typing import Any
from datetime import date
from functools import partial

from fastapi import APIRouter
import pandas as pd

logger = logging.getLogger(__name__)

from gold_agent.data.cache import cache
from gold_agent.data.geopol import fetch_geopol
from gold_agent.data.fed_watch import fetch_fedwatch
from gold_agent.data.cot import cot_cache_key, fetch_cot
from gold_agent.data.quality import dataframe_meta
from gold_agent.data.china_macro import (
    fetch_china_cpi,
    fetch_china_ppi,
    fetch_china_pmi,
    fetch_china_m2,
    fetch_china_gdp,
    fetch_china_lpr,
    fetch_china_fx,
)
from gold_agent.data.central_bank import fetch_central_bank_reserves
from gold_agent.data.etf_flow import fetch_etf_flow
from gold_agent.data.aisc import fetch_aisc
from gold_agent.data.calendar import fetch_calendar, get_upcoming_events, get_next_major_event

router = APIRouter(prefix="/api/analysis", tags=["数据补充"])


from gold_agent.utils.json import json_safe as _json_safe


# 各数据源的缓存 TTL 配置
TTL_MAP: dict[str, int] = {
    "central_bank_reserves": 604800,   # 7 天
    "cot": 86400,                       # 1 天
    "etf_flow": 604800,                 # 7 天
    "geopol": 86400,                    # 1 天
    "fedwatch": 21600,                  # 6 小时
    "aisc": 2592000,                    # 30 天
    "china_cpi": 2678400,               # 31 天
    "china_ppi": 2678400,               # 31 天
    "china_pmi": 2678400,               # 31 天
    "china_m2": 2678400,                # 31 天
    "china_gdp": 8035200,               # 93 天
    "china_lpr": 2678400,               # 31 天
    "china_usd_cny": 86400,             # 1 天
}

EXPECTED_FREQUENCY_MAP: dict[str, str] = {
    "central_bank_reserves": "monthly",
    "cot": "weekly",
    "etf_flow": "daily",
    "geopol": "daily",
    "fedwatch": "intraday",
    "aisc": "quarterly",
    "china_cpi": "monthly",
    "china_ppi": "monthly",
    "china_pmi": "monthly",
    "china_m2": "monthly",
    "china_gdp": "quarterly",
    "china_lpr": "monthly",
    "china_usd_cny": "daily",
}


def _normalize_meta_key(key: str) -> str:
    if key.startswith("cot_"):
        return "cot"
    return key


def _safe_fetch(key: str, fetch_fn, **kwargs) -> dict:
    """同步安全调用 fetch_fn，失败返回空"""
    try:
        meta_key = _normalize_meta_key(key)
        ttl = TTL_MAP.get(meta_key)
        # max_stale_days 与 TTL 对齐：允许数据新鲜度不超过 TTL+1 天
        max_stale_days = (ttl // 86400) + 1 if ttl else None
        df, meta = cache.get_with_meta(
            key=key,
            fetch_fn=fetch_fn,
            ttl=ttl,
            max_stale_days=max_stale_days,
            expected_frequency=EXPECTED_FREQUENCY_MAP.get(meta_key),
            **kwargs,
        )
        records = len(df)
        out = df.tail(100).copy()
        if "date" in out.columns:
            out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        data = _json_safe(out)
        return {
            "records": records,
            "data": data,
            "_status": "ok",
            "meta": meta,
        }
    except Exception as e:
        logger.warning(f"[extra_data] {key} 获取失败: {e}")
        return {
            "records": 0,
            "data": [],
            "_status": "error",
            "_error": str(e),
            "meta": dataframe_meta(
                pd.DataFrame(),
                source_status="unavailable",
                expected_frequency=EXPECTED_FREQUENCY_MAP.get(meta_key),
            ),
        }


async def _safe_fetch_async(key: str, fetch_fn, **kwargs) -> dict:
    """异步安全调用 — 在 executor 中运行同步 _safe_fetch"""
    loop = asyncio.get_event_loop()
    task = partial(_safe_fetch, key, fetch_fn, **kwargs)
    return await loop.run_in_executor(None, task)


@router.get("/extra")
async def get_extra_data():
    """获取所有补充数据（并行获取）"""
    tasks = {
        "central_bank": _safe_fetch_async("central_bank_reserves", fetch_central_bank_reserves),
        "cot": _safe_fetch_async(
            cot_cache_key(),
            fetch_cot,
            year=date.today().year,
        ),
        "etf_flow": _safe_fetch_async("etf_flow", fetch_etf_flow),
        "geopol": _safe_fetch_async("geopol", fetch_geopol),
        "fedwatch": _safe_fetch_async("fedwatch", fetch_fedwatch),
        "aisc": _safe_fetch_async("aisc", fetch_aisc),
        "cpi": _safe_fetch_async("china_cpi", fetch_china_cpi),
        "ppi": _safe_fetch_async("china_ppi", fetch_china_ppi),
        "pmi": _safe_fetch_async("china_pmi", fetch_china_pmi),
        "m2": _safe_fetch_async("china_m2", fetch_china_m2),
        "gdp": _safe_fetch_async("china_gdp", fetch_china_gdp),
        "lpr": _safe_fetch_async("china_lpr", fetch_china_lpr),
        "usd_cny": _safe_fetch_async("china_usd_cny", fetch_china_fx),
    }

    results_list = await asyncio.gather(*tasks.values())
    results: dict[str, Any] = dict(zip(tasks.keys(), results_list))

    # 将 7 个中国指标合并到一个 china_macro 字段
    china_keys = ["cpi", "ppi", "pmi", "m2", "gdp", "lpr", "usd_cny"]
    china_data = {k: results.pop(k) for k in china_keys}
    results["china_macro"] = china_data

    return results


@router.get("/calendar")
async def get_calendar(
    start_date: str | None = None,
    end_date: str | None = None,
    days: int = 60,
):
    """财经日历（mock 数据）"""
    try:
        if start_date and end_date:
            df = fetch_calendar(start_date, end_date)
        else:
            df = get_upcoming_events(days)

        next_event = get_next_major_event()

        data = df.to_dict(orient="records")
        # Format dates
        for row in data:
            if "date" in row and row["date"] is not None:
                row["date"] = str(row["date"])[:10]

        return {
            "records": len(df),
            "next_event": next_event,
            "data": data,
            "meta": dataframe_meta(
                df,
                source_status="live",
                expected_frequency="event",
            ),
        }
    except Exception as e:
        logger.error(f"获取财经日历失败: {e}")
        return {
            "records": 0,
            "next_event": None,
            "data": [],
            "error": str(e),
            "meta": dataframe_meta(
                pd.DataFrame(),
                source_status="unavailable",
                expected_frequency="event",
            ),
        }
