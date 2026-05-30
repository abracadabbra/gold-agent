"""中国宏观经济数据 — akshare"""

import re
import logging

import pandas as pd

logger = logging.getLogger(__name__)

_INDICATOR_MAP = {
    "cpi": ("ak.macro_china_cpi", "居民消费价格指数"),
    "ppi": ("ak.macro_china_ppi", "工业生产者出厂价格指数"),
    "pmi": ("ak.macro_china_pmi", "采购经理人指数"),
    "m2": ("ak.macro_china_money_supply", "货币供应量 M2"),
    "gdp": ("ak.macro_china_gdp", "国内生产总值"),
    "lpr": ("ak.macro_china_lpr", "贷款市场报价利率"),
    "usd_cny": ("ak.fx_spot_quote", "离岸/在岸人民币汇率"),
}

# akshare 函数名 → 调用映射
_AK_FUNC_MAP: dict[str, str] = {
    "ak.macro_china_cpi": "macro_china_cpi",
    "ak.macro_china_ppi": "macro_china_ppi",
    "ak.macro_china_pmi": "macro_china_pmi",
    "ak.macro_china_money_supply": "macro_china_money_supply",
    "ak.macro_china_gdp": "macro_china_gdp",
    "ak.macro_china_lpr": "macro_china_lpr",
    "ak.fx_spot_quote": "fx_spot_quote",
}


def _normalize_date(val: str) -> str:
    """标准化中文日期格式: '2026年04月份' → '2026-04-01'"""
    val = val.replace("年", "-").replace("月份", "-01").replace("月", "-01")
    m = re.search(r"第(\d+)季度", val)
    if m:
        q = int(m.group(1))
        month = str((q - 1) * 3 + 1).zfill(2)
        val = re.sub(r"第\d+季度", f"{month}", val)
    return val


def _extract_date_and_value(df: pd.DataFrame) -> pd.DataFrame:
    """从 DataFrame 中提取 date 和 value 列"""
    date_keywords = {"date", "时间", "指标", "年份", "季度", "月份", "日期"}
    date_cols = [c for c in df.columns if any(k in c.lower() or k in c for k in date_keywords)]
    value_cols = [c for c in df.columns if c not in date_cols]

    if date_cols:
        norm = df[date_cols[0]].astype(str).apply(_normalize_date)
        df["date"] = pd.to_datetime(norm, errors="coerce", format="mixed")
        skip_labels = {"date", "日期", "时间", "指标名称", "指标"}
        numeric_cols = [c for c in value_cols if c.lower() not in skip_labels]
        if numeric_cols:
            df["value"] = pd.to_numeric(df[numeric_cols[0]], errors="coerce")
            return df[["date", "value"]].dropna(subset=["date"]).copy()
        result = df[["date"]].copy()
        result["value"] = None
        return result

    # 尝试用 index 作为日期
    if isinstance(df.index, pd.DatetimeIndex | pd.PeriodIndex):
        df = df.reset_index()
        df = df.rename(columns={"index": "date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed")
        numeric_cols = [
            c for c in df.columns
            if c != "date" and pd.api.types.is_numeric_dtype(df[c])
        ]
        if numeric_cols:
            val_col = numeric_cols[0]
            return df[["date", val_col]].rename(columns={val_col: "value"}).copy()
        result = df[["date"]].copy()
        result["value"] = None
        return result

    return pd.DataFrame()


def _fetch_akshare(func_path: str, indicator: str) -> pd.DataFrame:
    """调用 akshare 函数并标准化"""
    try:
        import akshare as ak

        func_name = _AK_FUNC_MAP.get(func_path)
        if func_name is None:
            logger.warning(f"[china_macro] 未知函数: {func_path}")
            return pd.DataFrame()

        func = getattr(ak, func_name, None)
        if func is None:
            logger.warning(f"[china_macro] akshare 无此函数: {func_name}")
            return pd.DataFrame()

        df = func()

        if df.empty:
            logger.warning(f"[china_macro] {indicator}: 返回空")
            return pd.DataFrame()

        result = _extract_date_and_value(df.copy())
        if result.empty:
            logger.warning(f"[china_macro] {indicator}: 无法解析日期列")
            return result

        result = result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        logger.info(f"[china_macro] {indicator}: {len(result)} 行")
        return result

    except Exception as e:
        logger.warning(f"[china_macro] {indicator} 获取失败: {e}")
        return pd.DataFrame()


def fetch_china_cpi() -> pd.DataFrame:
    """中国 CPI"""
    return _fetch_akshare("ak.macro_china_cpi", "cpi")


def fetch_china_ppi() -> pd.DataFrame:
    """中国 PPI"""
    return _fetch_akshare("ak.macro_china_ppi", "ppi")


def fetch_china_pmi() -> pd.DataFrame:
    """中国 PMI"""
    return _fetch_akshare("ak.macro_china_pmi", "pmi")


def fetch_china_m2() -> pd.DataFrame:
    """中国 M2 货币供应量"""
    return _fetch_akshare("ak.macro_china_money_supply", "m2")


def fetch_china_gdp() -> pd.DataFrame:
    """中国 GDP"""
    return _fetch_akshare("ak.macro_china_gdp", "gdp")


def fetch_china_lpr() -> pd.DataFrame:
    """中国 LPR 利率"""
    return _fetch_akshare("ak.macro_china_lpr", "lpr")


def fetch_china_fx() -> pd.DataFrame:
    """人民币汇率（实时快照）"""
    try:
        import akshare as ak
        df = ak.fx_spot_quote()
        if df.empty:
            return pd.DataFrame()

        cny = df[df["货币对"] == "USD/CNY"].copy()
        if cny.empty:
            cny = df.iloc[[0]].copy()

        cny["date"] = pd.Timestamp.now().normalize()
        cny["value"] = (pd.to_numeric(cny["买报价"], errors="coerce")
                        + pd.to_numeric(cny["卖报价"], errors="coerce")) / 2
        result = cny[["date", "value"]].dropna()
        logger.info(f"[china_macro] usd_cny: {len(result)} 行")
        return result
    except Exception as e:
        logger.warning(f"[china_macro] usd_cny 获取失败: {e}")
        return pd.DataFrame()


def fetch_all_china_macro() -> dict[str, pd.DataFrame]:
    """一次获取所有中国宏观指标"""
    return {
        "cpi": fetch_china_cpi(),
        "ppi": fetch_china_ppi(),
        "pmi": fetch_china_pmi(),
        "m2": fetch_china_m2(),
        "gdp": fetch_china_gdp(),
        "lpr": fetch_china_lpr(),
        "usd_cny": fetch_china_fx(),
    }
