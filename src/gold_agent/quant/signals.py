"""信号生成 — 综合技术指标生成交易信号"""

from dataclasses import dataclass
from enum import Enum

import pandas as pd
import logging
logger = logging.getLogger(__name__)

from gold_agent.quant.indicators import compute_indicators


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
            score += 20
            reasons.append(f"MA5({ma5:.2f}) > MA20({ma20:.2f})，短期均线多头排列")
        else:
            score -= 20
            reasons.append(f"MA5({ma5:.2f}) < MA20({ma20:.2f})，短期均线空头排列")

    if "ma20" in latest and "ma60" in latest:
        ma20, ma60 = latest["ma20"], latest["ma60"]
        if ma20 > ma60:
            score += 10
            reasons.append(f"MA20({ma20:.2f}) > MA60({ma60:.2f})，中期趋势向上")
        else:
            score -= 10
            reasons.append(f"MA20({ma20:.2f}) < MA60({ma60:.2f})，中期趋势向下")

    return score, reasons


def _score_rsi(latest: dict) -> tuple[float, list[str]]:
    """RSI 评分 (±15)"""
    if "rsi14" not in latest:
        return 0.0, []

    rsi = latest["rsi14"]
    if rsi < 30:
        return 15.0, [f"RSI={rsi:.1f}，超卖区域，可能反弹"]
    if rsi < 40:
        return 8.0, [f"RSI={rsi:.1f}，接近超卖"]
    if rsi > 70:
        return -15.0, [f"RSI={rsi:.1f}，超买区域，可能回调"]
    if rsi > 60:
        return -8.0, [f"RSI={rsi:.1f}，接近超买"]
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
        score += 15
        reasons.append(f"MACD({macd:.4f}) > 信号线({signal:.4f})，多头动能")
    else:
        score -= 15
        reasons.append(f"MACD({macd:.4f}) < 信号线({signal:.4f})，空头动能")

    if hist > 0 and hist > latest.get("macd_hist_prev", 0):
        score += 5
        reasons.append("MACD 柱状图放大，动能增强")

    return score, reasons


def _score_bollinger(latest: dict, price: float) -> tuple[float, list[str]]:
    """布林带评分 (±10)"""
    if "bb_upper" not in latest or "bb_lower" not in latest:
        return 0.0, []

    bb_upper, bb_lower = latest["bb_upper"], latest["bb_lower"]
    if price < bb_lower:
        return 10.0, [f"价格(${price:.2f}) < 布林下轨(${bb_lower:.2f})，可能超卖反弹"]
    if price > bb_upper:
        return -10.0, [f"价格(${price:.2f}) > 布林上轨(${bb_upper:.2f})，可能超买回调"]

    pos = (price - bb_lower) / (bb_upper - bb_lower) * 100
    return 0.0, [f"布林带位置: {pos:.0f}%"]


def _score_supertrend(latest: dict) -> tuple[float, list[str]]:
    """Supertrend 评分 (±20)"""
    if "supertrend_dir" not in latest:
        return 0.0, []

    direction = latest["supertrend_dir"]
    st_val = latest.get("supertrend", 0)
    if direction > 0:
        return 20.0, [f"Supertrend(${st_val:.2f}) 看多信号 🟢"]
    return -20.0, [f"Supertrend(${st_val:.2f}) 看空信号 🔴"]


def _score_adx(latest: dict, score: float) -> tuple[float, list[str]]:
    """ADX 趋势强度评分 (±10)"""
    if "adx" not in latest:
        return 0.0, []

    adx = latest["adx"]
    if adx > 25:
        if score > 0:
            return 10.0, [f"ADX={adx:.1f}，强上升趋势确认"]
        return -10.0, [f"ADX={adx:.1f}，强下降趋势确认"]
    return 0.0, [f"ADX={adx:.1f}，趋势较弱/震荡市"]


def _classify_signal(score: float) -> Signal:
    """根据分数分类信号"""
    if score >= 50:
        return Signal.STRONG_BUY
    if score >= 20:
        return Signal.BUY
    if score <= -50:
        return Signal.STRONG_SELL
    if score <= -20:
        return Signal.SELL
    return Signal.NEUTRAL


def _calc_stop_take_profit(price: float, atr: float, bullish: bool) -> tuple[float, float]:
    """计算止损止盈"""
    if bullish:
        return round(price - 2 * atr, 2), round(price + 3 * atr, 2)
    return round(price + 2 * atr, 2), round(price - 3 * atr, 2)


def generate_signal(df: pd.DataFrame) -> TradeSignal:
    """
    综合多个技术指标生成交易信号

    评分规则:
    - MA 交叉: ±20 分
    - RSI: ±15 分
    - MACD: ±15 分
    - 布林带位置: ±10 分
    - Supertrend: ±20 分
    - ADX 趋势强度: ±10 分 (加分/减分取决于方向)
    - 新闻情绪: ±10 分

    Args:
        df: OHLCV DataFrame

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

    score = max(-100, min(100, score))
    signal = _classify_signal(score)
    confidence = min(1.0, abs(score) / 80)

    atr = latest.get("atr14", price * 0.02)
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
