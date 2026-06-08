"""信号生成 — 综合技术指标生成交易信号"""

from dataclasses import dataclass
from enum import Enum

import pandas as pd
import logging
logger = logging.getLogger(__name__)

from gold_agent.quant.indicators import compute_indicators

# ── 评分权重 ──
SCORE_MA_CROSS = 20
SCORE_MA_MID = 10
SCORE_RSI = 15
SCORE_RSI_NEAR = 8
SCORE_MACD = 15
SCORE_MACD_HIST = 5
SCORE_BOLLINGER = 10
SCORE_SUPERTREND = 20
SCORE_ADX = 10
SCORE_REAL_RATE = 10

# ── RSI 阈值 ──
RSI_OVERSOLD = 30
RSI_NEAR_OVERSOLD = 40
RSI_OVERBOUGHT = 70
RSI_NEAR_OVERBOUGHT = 60

# ── ADX 阈值 ──
ADX_STRONG = 25

# ── 实际利率阈值 (%)
TIPS_NEGATIVE = 0.0
TIPS_LOW = 0.5
TIPS_MODERATE = 1.5
TIPS_HIGH = 2.5

# ── 信号分类阈值 ──
STRONG_BUY_THRESHOLD = 50
BUY_THRESHOLD = 20
STRONG_SELL_THRESHOLD = -50
SELL_THRESHOLD = -20

# ── 分数边界 ──
MAX_SCORE = 100
MIN_SCORE = -100
CONFIDENCE_DIVISOR = 80

# ── 风控参数 ──
STOP_LOSS_ATR = 2
TAKE_PROFIT_ATR = 3
FALLBACK_ATR_RATIO = 0.02


class Signal(Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class TradeSignal:
    """交易信号"""
    signal: Signal
    score: float          # -100 到 +100
    confidence: float     # 0 到 1
    reasons: list[str]    # 信号依据
    stop_loss: float      # 建议止损价
    take_profit: float    # 建议止盈价

    def to_dict(self) -> dict:
        return {
            "signal": self.signal.value,
            "score": round(self.score, 1),
            "confidence": round(self.confidence, 2),
            "reasons": self.reasons,
            "stop_loss": round(self.stop_loss, 2),
            "take_profit": round(self.take_profit, 2),
        }


def _score_ma_cross(latest: dict) -> tuple[float, list[str]]:
    """MA 交叉评分 (±20)"""
    score = 0.0
    reasons = []

    if "ma5" in latest and "ma20" in latest:
        ma5, ma20 = latest["ma5"], latest["ma20"]
        if ma5 > ma20:
            score += SCORE_MA_CROSS
            reasons.append(f"MA5({ma5:.2f}) > MA20({ma20:.2f})，短期均线多头排列")
        else:
            score -= SCORE_MA_CROSS
            reasons.append(f"MA5({ma5:.2f}) < MA20({ma20:.2f})，短期均线空头排列")

    if "ma20" in latest and "ma60" in latest:
        ma20, ma60 = latest["ma20"], latest["ma60"]
        if ma20 > ma60:
            score += SCORE_MA_MID
            reasons.append(f"MA20({ma20:.2f}) > MA60({ma60:.2f})，中期趋势向上")
        else:
            score -= SCORE_MA_MID
            reasons.append(f"MA20({ma20:.2f}) < MA60({ma60:.2f})，中期趋势向下")

    return score, reasons


def _score_rsi(latest: dict) -> tuple[float, list[str]]:
    """RSI 评分 (±15)"""
    if "rsi14" not in latest:
        return 0.0, []

    rsi = latest["rsi14"]
    if rsi < RSI_OVERSOLD:
        return SCORE_RSI, [f"RSI={rsi:.1f}，超卖区域，可能反弹"]
    if rsi < RSI_NEAR_OVERSOLD:
        return SCORE_RSI_NEAR, [f"RSI={rsi:.1f}，接近超卖"]
    if rsi > RSI_OVERBOUGHT:
        return -SCORE_RSI, [f"RSI={rsi:.1f}，超买区域，可能回调"]
    if rsi > RSI_NEAR_OVERBOUGHT:
        return -SCORE_RSI_NEAR, [f"RSI={rsi:.1f}，接近超买"]
    return 0.0, [f"RSI={rsi:.1f}，中性区域"]


def _score_macd(latest: dict) -> tuple[float, list[str]]:
    """MACD 评分 (±15)"""
    if "macd_line" not in latest or "macd_signal" not in latest:
        return 0.0, []

    macd, signal = latest["macd_line"], latest["macd_signal"]
    hist = latest.get("macd_hist", 0)
    score = 0.0
    reasons = []

    if macd > signal:
        score += SCORE_MACD
        reasons.append(f"MACD({macd:.4f}) > 信号线({signal:.4f})，多头动能")
    else:
        score -= SCORE_MACD
        reasons.append(f"MACD({macd:.4f}) < 信号线({signal:.4f})，空头动能")

    if hist > 0 and hist > latest.get("macd_hist_prev", 0):
        score += SCORE_MACD_HIST
        reasons.append("MACD 柱状图放大，动能增强")

    return score, reasons


def _score_bollinger(latest: dict, price: float) -> tuple[float, list[str]]:
    """布林带评分 (±10)"""
    if "bb_upper" not in latest or "bb_lower" not in latest:
        return 0.0, []

    bb_upper, bb_lower = latest["bb_upper"], latest["bb_lower"]
    if price < bb_lower:
        return SCORE_BOLLINGER, [f"价格(${price:.2f}) < 布林下轨(${bb_lower:.2f})，可能超卖反弹"]
    if price > bb_upper:
        return -SCORE_BOLLINGER, [f"价格(${price:.2f}) > 布林上轨(${bb_upper:.2f})，可能超买回调"]

    band_width = bb_upper - bb_lower
    if pd.isna(band_width) or band_width == 0:
        return 0.0, ["布林带宽度不足，位置判断中性"]

    pos = (price - bb_lower) / band_width * 100
    return 0.0, [f"布林带位置: {pos:.0f}%"]


def _score_supertrend(latest: dict) -> tuple[float, list[str]]:
    """Supertrend 评分 (±20)"""
    if "supertrend_dir" not in latest:
        return 0.0, []

    direction = latest["supertrend_dir"]
    st_val = latest.get("supertrend", 0)
    if direction > 0:
        return SCORE_SUPERTREND, [f"Supertrend(${st_val:.2f}) 看多信号 🟢"]
    return -SCORE_SUPERTREND, [f"Supertrend(${st_val:.2f}) 看空信号 🔴"]


def _score_real_rate(macro_values: dict[str, float] | None) -> tuple[float, list[str]]:
    """TIPS 实际利率评分 (±10)

    实际利率 = TIPS 收益率。实际利率越低/负，对黄金越有利。
    """
    if not macro_values or "tips_yield" not in macro_values:
        return 0.0, []

    rate = macro_values["tips_yield"]
    if pd.isna(rate):
        return 0.0, []

    if rate < TIPS_NEGATIVE:
        return SCORE_REAL_RATE, [f"TIPS 实际利率 = {rate:.2f}%，负利率利多黄金"]
    if rate < TIPS_LOW:
        return SCORE_REAL_RATE / 2, [f"TIPS 实际利率 = {rate:.2f}%，低利率环境利多黄金"]
    if rate < TIPS_MODERATE:
        return 0.0, [f"TIPS 实际利率 = {rate:.2f}%，中性区间"]
    if rate < TIPS_HIGH:
        return -SCORE_REAL_RATE / 2, [f"TIPS 实际利率 = {rate:.2f}%，高利率压制黄金"]
    return -SCORE_REAL_RATE, [f"TIPS 实际利率 = {rate:.2f}%，极高利率严重压制黄金"]


def _score_adx(latest: dict, score: float) -> tuple[float, list[str]]:
    """ADX 趋势强度评分 (±10)"""
    if "adx" not in latest:
        return 0.0, []

    adx = latest["adx"]
    if adx > ADX_STRONG:
        if score > 0:
            return SCORE_ADX, [f"ADX={adx:.1f}，强上升趋势确认"]
        return -SCORE_ADX, [f"ADX={adx:.1f}，强下降趋势确认"]
    return 0.0, [f"ADX={adx:.1f}，趋势较弱/震荡市"]


def _classify_signal(score: float) -> Signal:
    """根据分数分类信号"""
    if score >= STRONG_BUY_THRESHOLD:
        return Signal.STRONG_BUY
    if score >= BUY_THRESHOLD:
        return Signal.BUY
    if score <= STRONG_SELL_THRESHOLD:
        return Signal.STRONG_SELL
    if score <= SELL_THRESHOLD:
        return Signal.SELL
    return Signal.NEUTRAL


def _calc_stop_take_profit(price: float, atr: float, bullish: bool) -> tuple[float, float]:
    """计算止损止盈"""
    if bullish:
        return round(price - STOP_LOSS_ATR * atr, 2), round(price + TAKE_PROFIT_ATR * atr, 2)
    return round(price + STOP_LOSS_ATR * atr, 2), round(price - TAKE_PROFIT_ATR * atr, 2)


def generate_signal(df: pd.DataFrame, macro_values: dict[str, float] | None = None) -> TradeSignal:
    """
    综合多个技术指标 + 可选宏观因子生成交易信号

    评分规则:
    - MA 交叉: ±20 分
    - RSI: ±15 分
    - MACD: ±15 分
    - 布林带位置: ±10 分
    - Supertrend: ±20 分
    - ADX 趋势强度: ±10 分 (加分/减分取决于方向)
    - TIPS 实际利率: ±10 分 (需传入 macro_values)

    Args:
        df: OHLCV DataFrame
        macro_values: 宏观经济指标最新值 dict，如 {"tips_yield": 1.23}

    Returns:
        TradeSignal 对象
    """
    indicators = compute_indicators(df)
    latest = indicators.latest()
    price = df["close"].iloc[-1]

    score = 0.0
    reasons = []

    for scorer in [_score_ma_cross, _score_rsi, _score_macd]:
        s, r = scorer(latest)
        score += s
        reasons.extend(r)

    s, r = _score_bollinger(latest, price)
    score += s
    reasons.extend(r)

    s, r = _score_supertrend(latest)
    score += s
    reasons.extend(r)

    s, r = _score_adx(latest, score)
    score += s
    reasons.extend(r)

    s, r = _score_real_rate(macro_values)
    score += s
    reasons.extend(r)

    score = max(MIN_SCORE, min(MAX_SCORE, score))
    signal = _classify_signal(score)
    confidence = min(1.0, abs(score) / CONFIDENCE_DIVISOR)

    atr = latest.get("atr14", price * FALLBACK_ATR_RATIO)
    stop_loss, take_profit = _calc_stop_take_profit(price, atr, score > 0)

    result = TradeSignal(
        signal=signal,
        score=score,
        confidence=confidence,
        reasons=reasons,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )

    logger.info(f"信号生成: {signal.value} (score={score:.1f}, confidence={confidence:.2f})")
    return result


def _signal_direction(signal: Signal) -> int:
    if signal in {Signal.STRONG_BUY, Signal.BUY}:
        return 1
    if signal in {Signal.STRONG_SELL, Signal.SELL}:
        return -1
    return 0


def evaluate_signal_history(
    df: pd.DataFrame,
    *,
    horizon: int = 5,
    window: int = 120,
    min_history: int = 60,
) -> dict:
    """Evaluate rolling historical signal direction against future returns.

    Each sample generates a signal using only data available at that date, then
    checks whether the future horizon return moved in the same direction.
    Neutral signals are counted in samples but excluded from directional hit rate.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if window < 1:
        raise ValueError("window must be >= 1")
    if min_history < 30:
        raise ValueError("min_history must be >= 30")

    empty_result = {
        "horizon_days": horizon,
        "window": window,
        "sample_size": 0,
        "directional_samples": 0,
        "hit_rate": None,
        "avg_forward_return": None,
        "avg_signal_score": None,
    }
    if df.empty or "date" not in df.columns or "close" not in df.columns:
        return empty_result

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working["close"] = pd.to_numeric(working["close"], errors="coerce")
    working = working.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    if len(working) <= min_history + horizon:
        return empty_result

    start = max(min_history, len(working) - window - horizon)
    end = len(working) - horizon
    rows: list[dict[str, float | int]] = []

    for idx in range(start, end):
        history = working.iloc[: idx + 1].copy()
        try:
            signal = generate_signal(history)
        except Exception:
            logger.debug("跳过历史信号评估样本 idx=%s", idx, exc_info=True)
            continue

        current = float(working["close"].iloc[idx])
        future = float(working["close"].iloc[idx + horizon])
        forward_return = (future - current) / current if current else 0.0
        direction = _signal_direction(signal.signal)
        future_direction = 1 if forward_return > 0 else -1 if forward_return < 0 else 0
        hit = int(direction != 0 and direction == future_direction)
        rows.append({
            "direction": direction,
            "hit": hit,
            "forward_return": forward_return,
            "score": signal.score,
        })

    if not rows:
        return empty_result

    result_df = pd.DataFrame(rows)
    directional = result_df[result_df["direction"] != 0]
    hit_rate = (
        float(directional["hit"].mean() * 100)
        if not directional.empty
        else None
    )

    return {
        "horizon_days": horizon,
        "window": window,
        "sample_size": int(len(result_df)),
        "directional_samples": int(len(directional)),
        "hit_rate": round(hit_rate, 2) if hit_rate is not None else None,
        "avg_forward_return": round(float(result_df["forward_return"].mean() * 100), 4),
        "avg_signal_score": round(float(result_df["score"].mean()), 4),
    }


def get_signal_summary(signal: TradeSignal) -> str:
    """生成信号的 LLM 可读摘要"""
    emoji_map = {
        Signal.STRONG_BUY: "🟢🟢 强烈看多",
        Signal.BUY: "🟢 看多",
        Signal.NEUTRAL: "⚪ 中性/震荡",
        Signal.SELL: "🔴 看空",
        Signal.STRONG_SELL: "🔴🔴 强烈看空",
    }

    lines = [
        f"## 交易信号: {emoji_map[signal.signal]}",
        f"- 综合评分: {signal.score:.1f} / 100",
        f"- 置信度: {signal.confidence:.0%}",
        f"- 建议止损: ${signal.stop_loss:.2f}",
        f"- 建议止盈: ${signal.take_profit:.2f}",
        "",
        "### 信号依据:",
    ]

    for i, reason in enumerate(signal.reasons, 1):
        lines.append(f"  {i}. {reason}")

    return "\n".join(lines)
