"""黄金 ETF 流量 — WGC XLSX 下载 + yfinance 兜底"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# WGC Goldhub ETF 数据页面
WGC_ETF_URL = "https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows"


def fetch_etf_flow(months: int = 12) -> pd.DataFrame:
    """
    获取全球黄金 ETF 持仓和流量

    优先从 WGC XLSX 下载，失败时以 yfinance GLD/IAU 数据兜底

    Args:
        months: 回溯月数

    Returns:
        DataFrame: date, fund_name, region, holdings_tonnes, flow_tonnes, flow_usd, aum_usd
    """
    # 优先尝试 WGC
    df = _fetch_wgc_etf(months)
    if not df.empty:
        return df

    # 兜底: yfinance GLD/IAU 每日持仓估算
    logger.info("[etf_flow] WGC 下载失败，使用 yfinance 兜底")
    return _fetch_yfinance_etf_fallback(months)


def _fetch_wgc_etf(months: int = 12) -> pd.DataFrame:
    """尝试从 WGC Goldhub 下载 XLSX"""
    try:
        # WGC 可能需要 session 和 cookie，尝试直接下载
        import io
        import urllib.request

        # 构造 WGC ETF 数据下载 URL
        # 实际下载链接可能包含重定向，用 urllib 处理
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(WGC_ETF_URL, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
        except Exception:
            # 尝试直接 XLSX 下载模式
            xlsx_url = "https://www.gold.org/download/file/4976/Gold_ETF_Holdings.xlsx"
            req = urllib.request.Request(xlsx_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()

        # 解析 XLSX
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        logger.info(f"[etf_flow] WGC XLSX 原始: {df.shape}")

        if df.empty:
            return pd.DataFrame()

        # 标准化
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # 查找日期列
        if "date" not in df.columns:
            dc = [c for c in df.columns if any(k in c for k in ("date", "period", "month"))]
            date_candidates = dc
            if date_candidates:
                df = df.rename(columns={date_candidates[0]: "date"})

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])

        # 标准化 ETF 持有量和流量列名
        rename_map = {}
        for c in df.columns:
            if "holding" in c and "tonn" in c:
                rename_map[c] = "holdings_tonnes"
            elif "flow" in c and "tonn" in c:
                rename_map[c] = "flow_tonnes"
            elif "flow" in c and "usd" in c:
                rename_map[c] = "flow_usd"
            elif "aum" in c or ("asset" in c and "usd" in c):
                rename_map[c] = "aum_usd"
            elif "fund" in c or "name" in c or "etf" in c:
                rename_map[c] = "fund_name"
            elif "region" in c or "country" in c:
                rename_map[c] = "region"

        df = df.rename(columns=rename_map)

        # 确保基础列存在
        if "fund_name" not in df.columns:
            df["fund_name"] = "Global"
        if "region" not in df.columns:
            df["region"] = "Global"

        result_cols = [c for c in ["date", "fund_name", "region", "holdings_tonnes",
                                    "flow_tonnes", "flow_usd", "aum_usd"] if c in df.columns]
        if "date" not in result_cols:
            return pd.DataFrame()

        result = df[result_cols].sort_values("date").reset_index(drop=True)

        # 按月份过滤
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
                    "holdings_tonnes": None,  # yfinance 不提供持仓量
                    "flow_tonnes": None,
                    "flow_usd": (row.get("Volume", 0) * row.get("Close", 0)
                                 if pd.notna(row.get("Volume")) else None),
                    "aum_usd": row.get("Close", 0) * 1_000_000,  # 估算（实际需流通股数）
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
