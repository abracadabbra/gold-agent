"""金价数据采集 — akshare (国内) + yfinance (国际)"""

import logging
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)


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
        df = ak.spot_golden_benchmark_sge(
            start_date=(datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
        )
        df = df.rename(columns={
            "日期": "date",
            "开盘价": "open",
            "最高价": "high",
            "最低价": "low",
            "收盘价": "close",
            "成交量": "volume",
        })
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        logger.info(f"[akshare] 沪金现货: {len(df)} 条记录")
        return df
    except Exception as e:
        logger.warning(f"[akshare] 沪金现货采集失败: {e}")
        return pd.DataFrame()


def fetch_all_gold(period: str = "1y") -> dict[str, pd.DataFrame]:
    """一次性拉取全部金价数据"""
    days = 365 if period == "1y" else 730
    return {
        "gold_xauusd": fetch_gold_xauusd(period),
        "gold_etf": fetch_gold_etf(period),
        "gold_spot_cny": fetch_gold_spot_akshare(days),
    }


# Alias for API compatibility
def fetch_gold_price(period='1y'):
    return fetch_gold_xauusd(period)
