"""金价数据采集 — akshare (国内) + yfinance (国际)"""

import logging
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)


_PERIOD_TO_DAYS = {
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
}

_PERIOD_TO_MONTHS = {
    "1mo": 1,
    "3mo": 3,
    "6mo": 6,
    "1y": 12,
    "2y": 24,
    "5y": 60,
}


def period_to_days(period: str) -> int:
    """将 API period 转为近似天数。"""
    return _PERIOD_TO_DAYS.get(period, 365)


def period_to_months(period: str) -> int:
    """将 API period 转为 Parquet 读取月份数。"""
    return _PERIOD_TO_MONTHS.get(period, 12)


def gold_cache_key(source: str, period: str) -> str:
    """金价缓存 key，按 source + period 隔离不同时间窗口。"""
    return f"gold_{source}_{period}"


def fetch_gold_xauusd(period: str = "1y") -> pd.DataFrame:
    """
    COMEX 黄金期货 (GC=F) — yfinance 日频
    返回列: date, open, high, low, close, volume
    """
    import yfinance as yf

    try:
        ticker = yf.Ticker("GC=F")
        df = ticker.history(period=period, auto_adjust=True)
        df = df.reset_index()
        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df[["date", "open", "high", "low", "close", "volume"]]
        df = df.sort_values("date").reset_index(drop=True)
        logger.info(f"[yfinance] XAUUSD: {len(df)} 条记录")
        return df
    except Exception as e:
        logger.warning(f"[yfinance] XAUUSD 采集失败: {e}")
        return pd.DataFrame()


def fetch_gold_etf(period: str = "1y") -> pd.DataFrame:
    """
    SPDR Gold ETF (GLD) — yfinance
    """
    import yfinance as yf

    try:
        ticker = yf.Ticker("GLD")
        df = ticker.history(period=period, auto_adjust=True)
        df = df.reset_index()
        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df[["date", "open", "high", "low", "close", "volume"]]
        df = df.sort_values("date").reset_index(drop=True)
        logger.info(f"[yfinance] GLD ETF: {len(df)} 条记录")
        return df
    except Exception as e:
        logger.warning(f"[yfinance] GLD ETF 采集失败: {e}")
        return pd.DataFrame()


def fetch_gold_spot_akshare(days: int = 365) -> pd.DataFrame:
    """
    上海金交所现货金 (Au99.99) — 日频
    """
    import akshare as ak

    try:
        df = ak.spot_hist_sge(symbol="Au99.99")
        df = df.rename(columns={
            "date": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
        })
        df["volume"] = None
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df["date"] >= cutoff].reset_index(drop=True)
        logger.info(f"[akshare] 沪金现货: {len(df)} 条记录")
        return df
    except Exception as e:
        logger.warning(f"[akshare] 沪金现货采集失败: {e}")
        return pd.DataFrame()


def fetch_all_gold(period: str = "1y") -> dict[str, pd.DataFrame]:
    """一次性拉取全部金价数据"""
    days = period_to_days(period)
    return {
        "gold_xauusd": fetch_gold_xauusd(period),
        "gold_etf": fetch_gold_etf(period),
        "gold_spot_cny": fetch_gold_spot_akshare(days),
    }


# Alias for API compatibility
def fetch_gold_price(source='intl', period='1y'):
    """统一入口，根据 source 路由到对应数据源"""
    if source == 'gld':
        return fetch_gold_etf(period=period)
    elif source == 'shfe':
        return fetch_gold_spot_akshare(period_to_days(period))
    return fetch_gold_xauusd(period=period)
