"""黄金生产成本 (AISC) — WGC Goldhub XLSX 下载"""

import io
import logging
import urllib.request

import pandas as pd

logger = logging.getLogger(__name__)

WGC_COST_URL = "https://www.gold.org/goldhub/data/gold-production-costs"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

_XLSX_URLS = [
    "https://www.gold.org/download/file/4976/Gold_Production_Costs.xlsx",
    "https://www.gold.org/download/file/4977/AISC_data.xlsx",
    "https://www.gold.org/download/file/4978/Gold_AISC_Data.xlsx",
]


def fetch_aisc() -> pd.DataFrame:
    """获取全球黄金 AISC 数据，失败时返回参考数据"""
    try:
        df = _fetch_wgc_aisc()
        if not df.empty:
            return df
    except Exception as e:
        logger.warning(f"[aisc] WGC 下载失败: {e}")

    logger.info("[aisc] 使用参考数据")
    return _reference_aisc_data()


def _find_column(
    df: pd.DataFrame, keywords: list[str], exclude: set[str] | None = None,
) -> str | None:
    """按关键词查找列名"""
    exclude = exclude or set()
    for c in df.columns:
        if c in exclude:
            continue
        if any(k in c.lower() for k in keywords):
            return c
    return None


def _find_aisc_column(
    df: pd.DataFrame, year_col: str | None, quarter_col: str | None,
) -> str | None:
    """查找 AISC 成本列"""
    # 优先按名称匹配
    col = _find_column(df, ["aisc", "sustaining"])
    if col:
        return col
    # 退而取第一个数值列
    exclude = {year_col, quarter_col} - {None}
    for c in df.columns:
        if c not in exclude and pd.api.types.is_numeric_dtype(df[c]):
            return c
    return None


def _build_date(df: pd.DataFrame) -> pd.DataFrame:
    """根据 year/quarter 列构建 date 列"""
    if "date" in df.columns or "year" not in df.columns:
        return df

    if "quarter" in df.columns:
        q_map = {"Q1": "01", "Q2": "04", "Q3": "07", "Q4": "10",
                 "1": "01", "2": "04", "3": "07", "4": "10"}
        q_str = df["quarter"].astype(str).str.upper().str.strip().map(
            lambda x: q_map.get(x, "01")
        )
        df["date"] = pd.to_datetime(df["year"].astype(int).astype(str) + "-" + q_str + "-01")
    else:
        df["date"] = pd.to_datetime(df["year"].astype(int).astype(str) + "-06-30")
    return df


def _parse_xlsx(content: bytes) -> pd.DataFrame:
    """解析 XLSX 内容并标准化为 AISC 格式"""
    df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
    if df.empty:
        return pd.DataFrame()

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    year_col = _find_column(df, ["year", "years", "期"])
    quarter_col = _find_column(df, ["quarter", "qtr", "季"])
    aisc_col = _find_aisc_column(df, year_col, quarter_col)

    if aisc_col is None:
        logger.warning("[aisc] 找不到成本列")
        return pd.DataFrame()

    result_cols = {aisc_col: "global_avg_aisc"}
    if year_col:
        result_cols[year_col] = "year"
    if quarter_col:
        result_cols[quarter_col] = "quarter"
    region_col = _find_column(df, ["region", "country", "area"])
    if region_col:
        result_cols[region_col] = "region"

    df = df.rename(columns=result_cols)
    df = df[[c for c in result_cols.values() if c in df.columns]].copy()

    if "note" not in df.columns:
        df["note"] = "WGC Goldhub"
    if "region" not in df.columns:
        df["region"] = "Global"

    df = _build_date(df)
    if "date" not in df.columns:
        return pd.DataFrame()

    return df.sort_values("date").reset_index(drop=True)


def _fetch_wgc_aisc() -> pd.DataFrame:
    """从 WGC 下载 AISC 数据"""
    last_error = None
    for url in _XLSX_URLS:
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
            df = _parse_xlsx(content)
            if not df.empty:
                logger.info(f"[aisc] 处理完成: {len(df)} 行")
                return df
        except Exception as e:
            last_error = e
            logger.debug(f"[aisc] URL {url} 失败: {e}")

    if last_error:
        raise last_error
    return pd.DataFrame()


def _reference_aisc_data() -> pd.DataFrame:
    """返回已知的参考 AISC 数据作为兜底"""
    data = {
        "year": [2022, 2022, 2022, 2022, 2023, 2023, 2023, 2023, 2024, 2024],
        "quarter": ["Q1", "Q2", "Q3", "Q4", "Q1", "Q2", "Q3", "Q4", "Q1", "Q2"],
        "global_avg_aisc": [1270, 1285, 1295, 1310, 1320, 1340, 1330, 1355, 1370, 1385],
        "region": ["Global"] * 10,
        "note": ["WGC Reference Estimate"] * 10,
    }
    df = pd.DataFrame(data)
    q_map = {"Q1": "01", "Q2": "04", "Q3": "07", "Q4": "10"}
    df["date"] = df.apply(
        lambda r: pd.Timestamp(f"{r['year']}-{q_map[r['quarter']]}-01"), axis=1
    )
    logger.info(f"[aisc] 参考数据: {len(df)} 行")
    return df
