"""黄金 ETF 流量 — WGC XLSX 下载 + yfinance 兜底"""

import io
import logging
import urllib.request

import pandas as pd

logger = logging.getLogger(__name__)

WGC_ETF_URL = "https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

# 标准列名映射关键词
_RENAME_KEYWORDS = {
    "holdings_tonnes": ["holding", "tonn"],
    "flow_tonnes": ["flow", "tonn"],
    "flow_usd": ["flow", "usd"],
    "aum_usd": ["aum", "asset"],
    "fund_name": ["fund", "name", "etf"],
    "region": ["region", "country"],
}


def fetch_etf_flow(months: int = 12) -> pd.DataFrame:
    """获取全球黄金 ETF 持仓和流量"""
    df = _fetch_wgc_etf(months)
    if not df.empty:
        return df

    logger.info("[etf_flow] WGC 下载失败，使用 yfinance 兜底")
    return _fetch_yfinance_etf_fallback(months)


def _match_column_name(col: str) -> str | None:
    """匹配列名到标准字段名"""
    col_lower = col.lower()
    for target, keywords in _RENAME_KEYWORDS.items():
        if all(k in col_lower for k in keywords):
            return target
    return None


def _find_date_column(df: pd.DataFrame) -> str | None:
    """查找日期列"""
    for c in df.columns:
        if any(k in c for k in ("date", "period", "month")):
            return c
    return None


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """标准化列名并确保基础列存在"""
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # 查找日期列
    if "date" not in df.columns:
        date_col = _find_date_column(df)
        if date_col:
            df = df.rename(columns={date_col: "date"})

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])

    # 标准化 ETF 列名
    rename_map = {}
    for c in df.columns:
        if c in ("date",):
            continue
        target = _match_column_name(c)
        if target and target not in rename_map.values():
            rename_map[c] = target
    df = df.rename(columns=rename_map)

    for col, default in [("fund_name", "Global"), ("region", "Global")]:
        if col not in df.columns:
            df[col] = default

    return df


def _fetch_wgc_etf(months: int = 12) -> pd.DataFrame:
    """尝试从 WGC Goldhub 下载 XLSX"""
    try:
        req = urllib.request.Request(WGC_ETF_URL, headers=_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
        except Exception:
            xlsx_url = "https://www.gold.org/download/file/4976/Gold_ETF_Holdings.xlsx"
            req = urllib.request.Request(xlsx_url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()

        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        logger.info(f"[etf_flow] WGC XLSX 原始: {df.shape}")

        if df.empty:
            return pd.DataFrame()

        df = _standardize_columns(df)

        result_cols = [c for c in ["date", "fund_name", "region", "holdings_tonnes",
                                    "flow_tonnes", "flow_usd", "aum_usd"] if c in df.columns]
        if "date" not in result_cols:
            return pd.DataFrame()

        result = df[result_cols].sort_values("date").reset_index(drop=True)

        if months and "date" in result.columns:
            cutoff = pd.Timestamp.now() - pd.DateOffset(months=months)
            result = result[result["date"] >= cutoff]

        logger.info(f"[etf_flow] WGC 处理完成: {len(result)} 行")
        return result

    except Exception as e:
        logger.warning(f"[etf_flow] WGC 下载失败: {e}")
        return pd.DataFrame()


def _fetch_yfinance_etf_fallback(months: int = 12) -> pd.DataFrame:
    """使用 yfinance GLD/IAU 日行情估算 ETF 流量"""
    import yfinance as yf

    period = f"{months}mo"
    rows = []

    for ticker, name in [("GLD", "SPDR Gold Shares"), ("IAU", "iShares Gold Trust")]:
        try:
            t = yf.Ticker(ticker)
            df = t.history(period=period, auto_adjust=True)
            if df.empty:
                continue
            df = df.reset_index()
            df["date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            for _, row in df.iterrows():
                rows.append({
                    "date": row["date"],
                    "fund_name": name,
                    "region": "North America",
                    "holdings_tonnes": None,
                    "flow_tonnes": None,
                    "flow_usd": (row.get("Volume", 0) * row.get("Close", 0)
                                 if pd.notna(row.get("Volume")) else None),
                    "aum_usd": row.get("Close", 0) * 1_000_000,
                })
            logger.info(f"[etf_flow] yfinance {ticker}: {len(df)} 行")
        except Exception as e:
            logger.warning(f"[etf_flow] yfinance {ticker} 失败: {e}")

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    result = result.sort_values("date").reset_index(drop=True)
    logger.info(f"[etf_flow] 兜底数据: {len(result)} 行")
    return result
