"""补充数据聚合接口 — GET /api/analysis/extra"""

import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter

logger = logging.getLogger(__name__)

from gold_agent.data.cache import cache
from gold_agent.data.geopol import fetch_geopol
from gold_agent.data.fed_watch import fetch_fedwatch
from gold_agent.data.cot import fetch_cot
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

router = APIRouter(prefix="/api/analysis", tags=["数据补充"])


def _json_safe(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame → JSON-safe list"""
    if df.empty:
        return []
    return df.where(df.notna(), None).astype(object).where(df.notna(), None).to_dict(  # noqa: E501
        orient="records",
    )


def _safe_fetch(key: str, fetch_fn, **kwargs) -> dict:
    """安全调用 fetch_fn，失败返回空"""
    ttl_map = {
        "central_bank_reserves": 604800,   # 7 天
        "cot": 86400,                       # 1 天
        "etf_flow": 604800,                 # 7 天
        "geopol": 86400,                    # 1 天
        "fedwatch": 21600,                  # 6 小时
        "aisc": 2592000,                    # 30 天
    }
    old_ttl = None
    if key in ttl_map:
        old_ttl = cache.cache_ttl
        cache.cache_ttl = ttl_map[key]
    try:
        df = cache.get(key=key, fetch_fn=fetch_fn, **kwargs)
        records = len(df)
        data = _json_safe(df.tail(100))
        return {
            "records": records,
            "data": data,
            "_status": "ok",
        }
    except Exception as e:
        logger.warning(f"[extra_data] {key} 获取失败: {e}")
        return {
            "records": 0,
            "data": [],
            "_status": "error",
            "_error": str(e),
        }
    finally:
        if old_ttl is not None:
            cache.cache_ttl = old_ttl


@router.get("/extra")
async def get_extra_data():
    """获取所有补充数据"""
    results: dict[str, Any] = {}

    # 1. 央行黄金储备
    results["central_bank"] = _safe_fetch("central_bank_reserves", fetch_central_bank_reserves)

    # 2. CFTC COT
    results["cot"] = _safe_fetch("cot", fetch_cot)

    # 3. ETF 流量
    results["etf_flow"] = _safe_fetch("etf_flow", fetch_etf_flow)

    # 4. GPR 指数
    results["geopol"] = _safe_fetch("geopol", fetch_geopol)

    # 5. FedWatch
    results["fedwatch"] = _safe_fetch("fedwatch", fetch_fedwatch)

    # 6. 中国宏观 — 每个指标独立缓存
    china_data = {}
    for indicator_name, fetch_fn, cache_key in [
        ("cpi", fetch_china_cpi, "china_cpi"),
        ("ppi", fetch_china_ppi, "china_ppi"),
        ("pmi", fetch_china_pmi, "china_pmi"),
        ("m2", fetch_china_m2, "china_m2"),
        ("gdp", fetch_china_gdp, "china_gdp"),
        ("lpr", fetch_china_lpr, "china_lpr"),
        ("usd_cny", fetch_china_fx, "china_usd_cny"),
    ]:
        china_data[indicator_name] = _safe_fetch(cache_key, fetch_fn)
    results["china_macro"] = china_data

    # 7. AISC
    results["aisc"] = _safe_fetch("aisc", fetch_aisc)

    return results
