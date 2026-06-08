"""CFTC COT 持仓报告 — cot_reports 库"""

import datetime
import logging

import pandas as pd

logger = logging.getLogger(__name__)

GOLD_MARKET_CODE = "088691"

# CFTC 原始列名 → 标准列名映射
_COL_MAP = {
    "Market and Exchange Names": "exchange",
    "As of Date in Form YYYY-MM-DD": "date",
    "Open Interest (All)": "open_interest",
    "Noncommercial Positions-Long (All)": "managed_money_long",
    "Noncommercial Positions-Short (All)": "managed_money_short",
    "Commercial Positions-Long (All)": "producer_long",
    "Commercial Positions-Short (All)": "producer_short",
}

_STD_COLS = ["date", "exchange", "open_interest",
             "producer_long", "producer_short",
             "managed_money_long", "managed_money_short"]


def cot_cache_key(year: int | None = None) -> str:
    """COT 缓存 key，按年份隔离，避免历史查询串缓存。"""
    if year is None:
        year = datetime.date.today().year
    return f"cot_{year}"


def _filter_gold(df: pd.DataFrame) -> pd.DataFrame:
    """从 COT 数据中过滤黄金市场"""
    if "Market and Exchange Names" in df.columns:
        col = "Market and Exchange Names"
        gold = df[df[col].astype(str).str.contains("GOLD", case=False, na=False)]
        if not gold.empty:
            return gold
        if "CFTC Commodity Code" in df.columns:
            return df[df["CFTC Commodity Code"].astype(str) == GOLD_MARKET_CODE]

    for col_name in ("CFTC_Commodity_Code", "commodity_code"):
        if col_name in df.columns:
            return df[df[col_name].astype(str) == GOLD_MARKET_CODE]

    # 尝试模糊匹配
    code_cols = [c for c in df.columns if "code" in c.lower() or "market" in c.lower()]
    if code_cols:
        return df[df[code_cols[0]].astype(str).str.contains("088691|GOLD", na=False)]

    logger.warning("[cot] 无法识别市场代码列，使用全部数据")
    return df


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """按模糊匹配重命名列"""
    rename = {}
    for col in df.columns:
        col_clean = col.strip()
        if col_clean in _COL_MAP:
            rename[col] = _COL_MAP[col_clean]
            continue
        lower = col_clean.lower().replace(" ", "_")
        for k, v in _COL_MAP.items():
            if lower == k.lower().replace(" ", "_") or lower == k.lower():
                rename[col] = v
                break
    return df.rename(columns=rename)


def _standardize(result: pd.DataFrame) -> pd.DataFrame:
    """标准化日期和数值列"""
    available = [c for c in _STD_COLS if c in result.columns]
    result = result[available].copy()

    if "date" in result.columns:
        result["date"] = pd.to_datetime(result["date"], errors="coerce")
        result = result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    for c in result.columns:
        if c not in ("date", "exchange"):
            result[c] = pd.to_numeric(result[c], errors="coerce")

    return result


def fetch_cot(year: int | None = None) -> pd.DataFrame:
    """获取 COMEX 黄金期货持仓报告"""
    try:
        from cot_reports import cot_year

        if year is None:
            year = datetime.date.today().year

        df = cot_year(year=year, cot_report_type="legacy_fut")
        logger.info(f"[cot] 原始 {year} 年数据: {df.shape}")

        if df.empty:
            logger.warning("[cot] 返回空数据")
            return pd.DataFrame()

        gold = _filter_gold(df)
        if gold.empty:
            logger.warning("[cot] 未找到黄金持仓数据")
            return pd.DataFrame()

        result = _rename_columns(gold)
        result = _standardize(result)

        logger.info(f"[cot] 黄金持仓: {len(result)} 行, 列={list(result.columns)}")
        return result

    except ImportError:
        logger.warning("[cot] cot_reports 未安装，返回空")
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"[cot] 获取失败: {e}")
        return pd.DataFrame()
