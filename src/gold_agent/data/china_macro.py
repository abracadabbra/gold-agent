"""中国宏观经济数据 — akshare"""

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


def _fetch_akshare(func_path: str, indicator: str) -> pd.DataFrame:
    """调用 akshare 函数并标准化"""
    try:
        import akshare as ak

        # 按函数名调用
        if func_path == "ak.macro_china_cpi":
            df = ak.macro_china_cpi()
        elif func_path == "ak.macro_china_ppi":
            df = ak.macro_china_ppi()
        elif func_path == "ak.macro_china_pmi":
            df = ak.macro_china_pmi()
        elif func_path == "ak.macro_china_money_supply":
            df = ak.macro_china_money_supply()
        elif func_path == "ak.macro_china_gdp":
            df = ak.macro_china_gdp()
        elif func_path == "ak.macro_china_lpr":
            df = ak.macro_china_lpr()
        elif func_path == "ak.fx_spot_quote":
            df = ak.fx_spot_quote()
        else:
            logger.warning(f"[china_macro] 未知函数: {func_path}")
            return pd.DataFrame()

        if df.empty:
            logger.warning(f"[china_macro] {indicator}: 返回空")
            return pd.DataFrame()

        # 标准化 — 找日期列和数值列
        df = df.copy()
        date_keywords = {"date", "时间", "指标", "年份", "季度", "月份", "日期"}
        date_cols = [c for c in df.columns if any(k in c.lower() or k in c for k in date_keywords)]  # noqa: E501
        value_cols = [c for c in df.columns if c not in date_cols]

        if date_cols:
            df["date"] = pd.to_datetime(df[date_cols[0]], errors="coerce")
            # 保留第一个数值列作为 value
            skip_labels = {"date", "日期", "时间", "指标名称", "指标"}
            numeric_cols = [c for c in value_cols if c.lower() not in skip_labels]  # noqa: E501
            if numeric_cols:
                df["value"] = pd.to_numeric(df[numeric_cols[0]], errors="coerce")
                result = df[["date", "value"]].dropna(subset=["date"]).copy()
            else:
                result = df[["date"]].copy()
                result["value"] = None
        else:
            # 尝试用 index 作为日期
            if isinstance(df.index, pd.DatetimeIndex | pd.PeriodIndex):
                df = df.reset_index()
                df = df.rename(columns={"index": "date"})
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                numeric_cols = [
                    c for c in df.columns
                    if c != "date" and pd.api.types.is_numeric_dtype(df[c])
                ]
                if numeric_cols:
                    val_col = numeric_cols[0]
                    result = df[["date", val_col]].rename(columns={val_col: "value"}).copy()  # noqa: E501
                else:
                    result = df[["date"]].copy()
                    result["value"] = None
            else:
                logger.warning(f"[china_macro] {indicator}: 无法解析日期列")
                return pd.DataFrame()

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
    """人民币汇率"""
    return _fetch_akshare("ak.fx_spot_quote", "usd_cny")


def fetch_all_china_macro() -> dict[str, pd.DataFrame]:
    """一次获取所有中国宏观指标"""
    # cache 按单 key 缓存，因此这里汇集所有，但 cache.get 会分散调用
    return {
        "cpi": fetch_china_cpi(),
        "ppi": fetch_china_ppi(),
        "pmi": fetch_china_pmi(),
        "m2": fetch_china_m2(),
        "gdp": fetch_china_gdp(),
        "lpr": fetch_china_lpr(),
        "usd_cny": fetch_china_fx(),
    }
