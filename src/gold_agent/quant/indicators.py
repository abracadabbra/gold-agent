"""技术指标计算 — 优先使用 pandas-ta，回退到纯 pandas 实现"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import logging
logger = logging.getLogger(__name__)

# 尝试导入 pandas-ta
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
    logger.info(f"使用 pandas-ta {ta.version}")
except ImportError:
    HAS_PANDAS_TA = False
    logger.info("pandas-ta 不可用，使用纯 pandas 实现")


@dataclass
class IndicatorResult:
    """技术指标计算结果"""

    # 趋势指标
    ma5: pd.Series | None = None
    ma10: pd.Series | None = None
    ma20: pd.Series | None = None
    ma60: pd.Series | None = None
    ema12: pd.Series | None = None
    ema26: pd.Series | None = None

    # MACD
    macd_line: pd.Series | None = None
    macd_signal: pd.Series | None = None
    macd_hist: pd.Series | None = None

    # 振荡器
    rsi14: pd.Series | None = None
    stoch_k: pd.Series | None = None
    stoch_d: pd.Series | None = None

    # 波动率
    bb_upper: pd.Series | None = None
    bb_mid: pd.Series | None = None
    bb_lower: pd.Series | None = None
    atr14: pd.Series | None = None

    # 趋势强度
    adx: pd.Series | None = None
    supertrend: pd.Series | None = None
    supertrend_dir: pd.Series | None = None  # 1=看多, -1=看空

    # 成交量
    obv: pd.Series | None = None

    def to_dict(self) -> dict:
        """转为字典，用于 LLM 上下文注入"""
        result: dict[str, float] = {}
        for k, v in self.__dict__.items():

            if v is not None and isinstance(v, pd.Series) and not v.empty:
                val = v.iloc[-1]
                if pd.notna(val):
                    result[k] = round(float(val), 4)
        return result

    def latest(self) -> dict:
        """获取最新一行所有有效指标值"""
        return self.to_dict()


# ============================================================
# 纯 pandas 实现 (pandas-ta 不可用时的回退方案)
# ============================================================

def _sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length, min_periods=1).mean()

def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                k_period: int = 14, d_period: int = 3) -> tuple:
    lowest_low = low.rolling(window=k_period, min_periods=1).min()
    highest_high = high.rolling(window=k_period, min_periods=1).max()
    denominator = (highest_high - lowest_low).replace(0, np.nan)
    k = 100 * (close - lowest_low) / denominator
    d = k.rolling(window=d_period, min_periods=1).mean()
    return k, d

def _bollinger_bands(series: pd.Series, length: int = 20, std_dev: float = 2.0) -> tuple:
    mid = _sma(series, length)
    std = series.rolling(window=length, min_periods=1).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower

def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)  # noqa: E501
    return tr.ewm(alpha=1 / length, min_periods=length).mean()

def _adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    plus_dm = (high - prev_high).where((high - prev_high) > (prev_low - low), 0.0).clip(lower=0)
    minus_dm = (prev_low - low).where((prev_low - low) > (high - prev_high), 0.0).clip(lower=0)
    atr_val = _atr(high, low, close, length)
    plus_di = 100 * _ema(plus_dm, length) / atr_val.replace(0, np.nan)
    minus_di = 100 * _ema(minus_dm, length) / atr_val.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return _ema(dx, length)


# ============================================================
# 主计算函数
# ============================================================

def _compute_with_pandas_ta(df: pd.DataFrame, result: IndicatorResult):
    """使用 pandas-ta 计算全部技术指标"""
    close = df["close"]
    high = df["high"]
    low = df["low"]

    result.ma5 = ta.sma(close, length=5)
    result.ma10 = ta.sma(close, length=10)
    result.ma20 = ta.sma(close, length=20)
    result.ma60 = ta.sma(close, length=60)
    result.ema12 = ta.ema(close, length=12)
    result.ema26 = ta.ema(close, length=26)

    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        result.macd_line = macd_df.iloc[:, 0]
        result.macd_signal = macd_df.iloc[:, 1]
        result.macd_hist = macd_df.iloc[:, 2]

    result.rsi14 = ta.rsi(close, length=14)

    stoch_df = ta.stoch(high, low, close)
    if stoch_df is not None and not stoch_df.empty:
        result.stoch_k = stoch_df.iloc[:, 0]
        result.stoch_d = stoch_df.iloc[:, 1]

    bb_df = ta.bbands(close, length=20, std=2)  # type: ignore[arg-type]
    if bb_df is not None and not bb_df.empty:
        result.bb_lower = bb_df.iloc[:, 0]
        result.bb_mid = bb_df.iloc[:, 1]
        result.bb_upper = bb_df.iloc[:, 2]

    result.atr14 = ta.atr(high, low, close, length=14)

    adx_df = ta.adx(high, low, close, length=14)
    if adx_df is not None and not adx_df.empty:
        result.adx = adx_df.iloc[:, 0]

    st_df = ta.supertrend(high, low, close, length=10, multiplier=3)
    if st_df is not None and not st_df.empty:
        result.supertrend = st_df.iloc[:, 0]
        result.supertrend_dir = st_df.iloc[:, 1]

    if "volume" in df.columns:
        result.obv = ta.obv(close, df["volume"])


def _compute_with_fallback(df: pd.DataFrame, result: IndicatorResult):
    """纯 pandas 实现回退"""
    close = df["close"]
    high = df["high"]
    low = df["low"]

    result.ma5 = _sma(close, 5)
    result.ma10 = _sma(close, 10)
    result.ma20 = _sma(close, 20)
    result.ma60 = _sma(close, 60)
    result.ema12 = _ema(close, 12)
    result.ema26 = _ema(close, 26)
    result.macd_line, result.macd_signal, result.macd_hist = _macd(close)
    result.rsi14 = _rsi(close, 14)
    result.stoch_k, result.stoch_d = _stochastic(high, low, close)
    result.bb_upper, result.bb_mid, result.bb_lower = _bollinger_bands(close)
    result.atr14 = _atr(high, low, close, 14)
    result.adx = _adx(high, low, close, 14)


def compute_indicators(df: pd.DataFrame) -> IndicatorResult:
    """
    计算全部技术指标
    优先使用 pandas-ta，不可用时回退到纯 pandas 实现
    """
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            raise ValueError(f"缺少必要列: {col}")

    result = IndicatorResult()

    if HAS_PANDAS_TA:
        _compute_with_pandas_ta(df, result)
    else:
        _compute_with_fallback(df, result)

    indicator_count = len([v for v in result.__dict__.values() if v is not None])
    ta_label = "是" if HAS_PANDAS_TA else "否"
    logger.info(f"技术指标计算完成: {indicator_count} 个指标 (pandas-ta={ta_label})")
    return result


def get_indicator_summary(df: pd.DataFrame) -> str:
    """计算指标并生成 LLM 可读的摘要文本"""
    indicators = compute_indicators(df)
    latest = indicators.latest()
    price = df["close"].iloc[-1]
    prev_price = df["close"].iloc[-2] if len(df) > 1 else price
    change_pct = (price - prev_price) / prev_price * 100

    lines = [
        f"## 当前金价: ${price:.2f} ({change_pct:+.2f}%)",
        "",
        "### 移动平均线",
    ]

    for ma in ["ma5", "ma10", "ma20", "ma60"]:
        if ma in latest:
            diff_pct = (price - latest[ma]) / latest[ma] * 100
            pos = "上方" if diff_pct > 0 else "下方"
            lines.append(f"- {ma.upper()}: ${latest[ma]:.2f} (价格在{pos} {abs(diff_pct):.1f}%)")

    if "rsi14" in latest:
        rsi = latest["rsi14"]
        zone = "超买" if rsi > 70 else "超卖" if rsi < 30 else "中性"
        lines.extend(["", "### 振荡指标", f"- RSI(14): {rsi:.1f} ({zone})"])

    if "macd_line" in latest:
        macd = latest["macd_line"]
        sig = latest.get("macd_signal", 0)
        hist = latest.get("macd_hist", 0)
        trend = "多头" if macd > sig else "空头"
        lines.append(f"- MACD: {macd:.4f} (信号线: {sig:.4f}, {trend}, 柱状: {hist:.4f})")

    if "stoch_k" in latest:
        k, d = latest["stoch_k"], latest.get("stoch_d", 0)
        zone = "超买" if k > 80 else "超卖" if k < 20 else "中性"
        lines.append(f"- KDJ: K={k:.1f}, D={d:.1f} ({zone})")

    if "bb_upper" in latest:
        lines.extend([
            "",
            "### 波动率",
            f"- 布林带: 上轨=${latest['bb_upper']:.2f}, "
            f"中轨=${latest['bb_mid']:.2f}, 下轨=${latest['bb_lower']:.2f}",
        ])

    if "atr14" in latest:
        atr_pct = latest["atr14"] / price * 100
        lines.append(f"- ATR(14): ${latest['atr14']:.2f} ({atr_pct:.2f}%)")

    if "adx" in latest:
        adx = latest["adx"]
        strength = "强趋势" if adx > 25 else "弱趋势/震荡"
        lines.extend(["", "### 趋势强度", f"- ADX: {adx:.1f} ({strength})"])

    if "supertrend" in latest:
        direction = "看多 🟢" if latest.get("supertrend_dir", 0) > 0 else "看空 🔴"
        lines.append(f"- Supertrend: ${latest['supertrend']:.2f} ({direction})")

    return "\n".join(lines)
