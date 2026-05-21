"""宏观经济数据采集 — yfinance (实时) + FRED (官方统计)"""

import pandas as pd
import yfinance as yf
import logging
logger = logging.getLogger(__name__)

from gold_agent.config import settings


# ============================================================
# yfinance 宏观指标
# ============================================================

_MACRO_TICKERS = {
    "usd_index": ("DX-Y.NYB", "美元指数"),
    "us_10y": ("^TNX", "10年期美债收益率"),
    "us_2y": ("^IRX", "2年期美债收益率"),  # 近似
    "vix": ("^VIX", "VIX 恐慌指数"),
    "sp500": ("^GSPC", "标普500"),
    "crude_oil": ("CL=F", "WTI 原油"),
}


def fetch_macro_yfinance(
    indicators: list[str] | None = None, period: str = "1y"
) -> pd.DataFrame:
    """
    通过 yfinance 批量获取宏观指标

    Args:
        indicators: 指标名列表，默认全部
        period: 时间范围

    Returns:
        DataFrame: date 为索引，每列一个指标的收盘价
    """
    if indicators is None:
        indicators = list(_MACRO_TICKERS.keys())

    tickers = [_MACRO_TICKERS[ind][0] for ind in indicators if ind in _MACRO_TICKERS]
    names = {ind: _MACRO_TICKERS[ind][1] for ind in indicators if ind in _MACRO_TICKERS}

    logger.info(f"获取宏观数据 (yfinance): {list(names.values())}")

    try:
        data = yf.download(tickers, period=period, progress=False)
    except Exception as e:
        logger.warning(f"yfinance 宏观数据获取失败: {e}")
        return pd.DataFrame()

    if data.empty:
        logger.warning("yfinance 宏观数据返回空")
        return pd.DataFrame()

    # 提取 Close 价
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
    else:
        close = data[["Close"]].copy()
        close.columns = [tickers[0]]

    # 重命名列为中文名
    ticker_to_name = {v[0]: k for k, v in _MACRO_TICKERS.items() if k in indicators}
    close = close.rename(columns=ticker_to_name)

    close = close.reset_index()
    close.columns = [c.lower().replace(" ", "_") for c in close.columns]
    if "date" not in close.columns and "datetime" in close.columns:
        close = close.rename(columns={"datetime": "date"})

    close["date"] = pd.to_datetime(close["date"]).dt.tz_localize(None)
    close = close.sort_values("date").reset_index(drop=True)

    logger.info(f"宏观数据获取成功: {len(close)} 行, 列={list(close.columns[1:])}")
    return close


# ============================================================
# FRED 官方数据
# ============================================================

_FRED_SERIES = {
    "cpi": ("CPIAUCSL", "美国 CPI (同比)"),
    "fed_rate": ("FEDFUNDS", "联邦基金利率"),
    "m2": ("M2SL", "M2 货币供应量"),
    "us_10y_yield": ("DGS10", "10年期美债收益率 (日频)"),
    "us_2y_yield": ("DGS2", "2年期美债收益率 (日频)"),
    "tips_yield": ("DFII10", "10年期 TIPS 收益率 (实际利率)"),
}


def fetch_macro_fred(
    series_ids: list[str] | None = None, start_date: str = "2020-01-01"
) -> pd.DataFrame:
    """
    通过 FRED API 获取宏观经济数据

    Args:
        series_ids: FRED series ID 列表，默认全部
        start_date: 开始日期 YYYY-MM-DD

    Returns:
        DataFrame: date 为索引，每列一个指标
    """
    if not settings.fred_api_key:
        logger.warning("FRED_API_KEY 未配置，跳过 FRED 数据")
        return pd.DataFrame()

    from fredapi import Fred

    fred = Fred(api_key=settings.fred_api_key)

    if series_ids is None:
        series_ids = list(_FRED_SERIES.keys())

    results = {}
    for sid in series_ids:
        if sid not in _FRED_SERIES:
            logger.warning(f"未知 FRED series: {sid}")
            continue

        fred_code, desc = _FRED_SERIES[sid]
        try:
            series = fred.get_series(fred_code, observation_start=start_date)
            if not series.empty:
                results[sid] = series
                logger.info(f"  FRED {desc}: {len(series)} 条记录")
            else:
                logger.warning(f"  FRED {desc}: 返回空数据")
        except Exception as e:
            logger.error(f"  FRED {desc} 获取失败: {e}")

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df.index.name = "date"
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    logger.info(f"FRED 数据获取成功: {len(df)} 行, 列={list(df.columns[1:])}")
    return df


def fetch_all_macro(period: str = "1y", start_date: str = "2020-01-01") -> dict:
    """
    获取全部宏观数据，返回两份 DataFrame

    Returns:
        {
            "realtime": DataFrame (yfinance, 日频),
            "official": DataFrame (FRED, 月频/日频混合)
        }
    """
    return {
        "realtime": fetch_macro_yfinance(period=period),
        "official": fetch_macro_fred(start_date=start_date),
    }
