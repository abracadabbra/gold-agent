"""信号生成单元测试"""

import numpy as np
import pandas as pd
import pytest

from gold_agent.quant.signals import (
    Signal,
    _classify_signal,
    _score_adx,
    _score_bollinger,
    _score_ma_cross,
    _score_macd,
    _score_real_rate,
    _score_rsi,
    _score_supertrend,
    evaluate_signal_history,
    generate_signal,
)


@pytest.fixture
def sample_ohlcv():
    """生成模拟 OHLCV 数据"""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    base_price = 2000
    prices = base_price + np.cumsum(np.random.randn(100) * 20)

    df = pd.DataFrame({
        "date": dates,
        "open": prices + np.random.randn(100) * 5,
        "high": prices + abs(np.random.randn(100) * 15),
        "low": prices - abs(np.random.randn(100) * 15),
        "close": prices,
        "volume": np.random.randint(10000, 100000, 100),
    })
    return df


def test_generate_signal(sample_ohlcv):
    """测试信号生成"""
    signal = generate_signal(sample_ohlcv)

    # 信号值应该是有效枚举
    assert signal.signal in Signal

    # 分数在 -100 到 100 之间
    assert -100 <= signal.score <= 100

    # 置信度在 0 到 1 之间
    assert 0 <= signal.confidence <= 1

    # 应该有至少 3 个理由
    assert len(signal.reasons) >= 3

    # 止损止盈应该有值
    assert signal.stop_loss > 0
    assert signal.take_profit > 0


def test_signal_to_dict(sample_ohlcv):
    """测试信号序列化"""
    signal = generate_signal(sample_ohlcv)
    d = signal.to_dict()

    assert "signal" in d
    assert "score" in d
    assert "confidence" in d
    assert "reasons" in d


def test_evaluate_signal_history_returns_performance(sample_ohlcv):
    """历史滚动信号评估返回样本外方向表现。"""
    result = evaluate_signal_history(
        sample_ohlcv,
        horizon=5,
        window=40,
        min_history=60,
    )

    assert result["horizon_days"] == 5
    assert result["window"] == 40
    assert result["sample_size"] > 0
    assert result["directional_samples"] >= 0
    assert result["avg_forward_return"] is not None
    assert result["avg_signal_score"] is not None


def test_evaluate_signal_history_empty_data():
    result = evaluate_signal_history(pd.DataFrame(), horizon=5, window=40)

    assert result["sample_size"] == 0
    assert result["hit_rate"] is None
    assert result["avg_forward_return"] is None


def test_evaluate_signal_history_validates_args(sample_ohlcv):
    with pytest.raises(ValueError, match="horizon"):
        evaluate_signal_history(sample_ohlcv, horizon=0)
    with pytest.raises(ValueError, match="window"):
        evaluate_signal_history(sample_ohlcv, window=0)
    with pytest.raises(ValueError, match="min_history"):
        evaluate_signal_history(sample_ohlcv, min_history=20)


class TestScoreRealRate:
    """测试 _score_real_rate TIPS 实际利率评分"""

    def test_none_macro_returns_neutral(self):
        s, r = _score_real_rate(None)
        assert s == 0.0
        assert r == []

    def test_missing_tips_key_returns_neutral(self):
        s, r = _score_real_rate({"fed_rate": 5.0})
        assert s == 0.0
        assert r == []

    def test_negative_rate_bullish(self):
        s, r = _score_real_rate({"tips_yield": -0.5})
        assert s == 10.0
        assert any("负利率" in reason for reason in r)

    def test_low_rate_slightly_bullish(self):
        s, r = _score_real_rate({"tips_yield": 0.3})
        assert s == 5.0
        assert any("低利率" in reason for reason in r)

    def test_moderate_rate_neutral(self):
        s, r = _score_real_rate({"tips_yield": 1.0})
        assert s == 0.0
        assert any("中性" in reason for reason in r)

    def test_high_rate_bearish(self):
        s, r = _score_real_rate({"tips_yield": 2.0})
        assert s == -5.0
        assert any("高利率" in reason for reason in r)

    def test_extreme_rate_strongly_bearish(self):
        s, r = _score_real_rate({"tips_yield": 3.0})
        assert s == -10.0
        assert any("极高利率" in reason for reason in r)

    def test_nan_rate_ignored(self):
        s, r = _score_real_rate({"tips_yield": float("nan")})
        assert s == 0.0
        assert r == []

    def test_generate_signal_with_macro_values(self, sample_ohlcv):
        """传入 macro_values 时信号应包含 TIPS 理由"""
        signal = generate_signal(sample_ohlcv, macro_values={"tips_yield": -0.5})
        tips_reasons = [r for r in signal.reasons if "TIPS" in r]
        assert len(tips_reasons) >= 1

    def test_generate_signal_without_macro_values(self, sample_ohlcv):
        """不传 macro_values 时不应有 TIPS 理由"""
        signal = generate_signal(sample_ohlcv)
        tips_reasons = [r for r in signal.reasons if "TIPS" in r]
        assert len(tips_reasons) == 0


# ====================================================================
# 直接测试各评分函数，覆盖所有分支
# ====================================================================


class TestScoreMACross:
    """测试 _score_ma_cross — MA 交叉评分"""

    def test_missing_columns(self):
        """缺少 MA 列时返回中性"""
        s, r = _score_ma_cross({"close": 100})
        assert s == 0.0
        assert r == []

    def test_bullish_short_cross(self):
        """MA5 > MA20 短期看多 (不含 ma60 以隔离测试)"""
        s, r = _score_ma_cross({"ma5": 105, "ma20": 100})
        assert s == pytest.approx(20.0)  # SCORE_MA_CROSS
        assert any("MA5" in line and "多头" in line for line in r)

    def test_bearish_short_cross(self):
        """MA5 < MA20 短期看空 (不含 ma60 以隔离测试)"""
        s, r = _score_ma_cross({"ma5": 95, "ma20": 100})
        assert s == pytest.approx(-20.0)  # -SCORE_MA_CROSS
        assert any("MA5" in line and "空头" in line for line in r)

    def test_bullish_mid_trend(self):
        """MA20 > MA60 中期看多"""
        s, r = _score_ma_cross({"ma5": 105, "ma20": 100, "ma60": 95})
        assert any("MA20" in line and "向上" in line for line in r)
        # 总分 = 20 (short) + 10 (mid) = 30
        assert s == pytest.approx(30.0)

    def test_bearish_mid_trend(self):
        """MA20 < MA60 中期看空"""
        s, r = _score_ma_cross({"ma5": 85, "ma20": 90, "ma60": 95})
        assert any("MA20" in line and "向下" in line for line in r)
        # 总分 = -20 (short) + -10 (mid) = -30
        assert s == pytest.approx(-30.0)


class TestScoreRSI:
    """测试 _score_rsi — RSI 评分"""

    def test_missing_rsi(self):
        """缺少 rsi14 时返回中性"""
        s, r = _score_rsi({"close": 100})
        assert s == 0.0
        assert r == []

    def test_oversold(self):
        """RSI < 30 超卖 → +15"""
        s, r = _score_rsi({"rsi14": 25})
        assert s == pytest.approx(15.0)
        assert any("超卖" in line for line in r)

    def test_near_oversold(self):
        """30 <= RSI < 40 接近超卖 → +8"""
        s, r = _score_rsi({"rsi14": 35})
        assert s == pytest.approx(8.0)
        assert any("接近超卖" in line for line in r)

    def test_overbought(self):
        """RSI > 70 超买 → -15"""
        s, r = _score_rsi({"rsi14": 75})
        assert s == pytest.approx(-15.0)
        assert any("超买" in line for line in r)

    def test_near_overbought(self):
        """60 < RSI <= 70 接近超买 → -8"""
        s, r = _score_rsi({"rsi14": 65})
        assert s == pytest.approx(-8.0)
        assert any("接近超买" in line for line in r)

    def test_neutral(self):
        """40 <= RSI <= 60 中性 → 0"""
        s, r = _score_rsi({"rsi14": 50})
        assert s == pytest.approx(0.0)
        assert any("中性" in line for line in r)


class TestScoreMACD:
    """测试 _score_macd — MACD 评分"""

    def test_missing_columns(self):
        """缺少 macd_line 或 macd_signal 时返回中性"""
        s, r = _score_macd({"rsi14": 50})
        assert s == 0.0
        assert r == []

    def test_bullish(self):
        """MACD > 信号线 → +15"""
        s, r = _score_macd({"macd_line": 0.5, "macd_signal": 0.3})
        assert s == pytest.approx(15.0)
        assert any("多头" in line for line in r)

    def test_bearish(self):
        """MACD < 信号线 → -15"""
        s, r = _score_macd({"macd_line": 0.3, "macd_signal": 0.5})
        assert s == pytest.approx(-15.0)
        assert any("空头" in line for line in r)

    def test_bullish_with_histogram_growth(self):
        """MACD 多头 + 柱状图放大 → +20"""
        s, r = _score_macd({
            "macd_line": 0.5,
            "macd_signal": 0.3,
            "macd_hist": 0.1,
            "macd_hist_prev": 0.05,
        })
        assert s == pytest.approx(20.0)  # 15 + 5
        assert any("柱状图放大" in line for line in r)


class TestScoreBollinger:
    """测试 _score_bollinger — 布林带评分"""

    def test_missing_columns(self):
        """缺少 bb_upper 或 bb_lower 时返回中性"""
        s, r = _score_bollinger({"close": 100}, 100)
        assert s == 0.0
        assert r == []

    def test_below_lower_band(self):
        """价格 < 布林下轨 → +10"""
        s, r = _score_bollinger({"bb_upper": 110, "bb_lower": 90}, 85)
        assert s == pytest.approx(10.0)
        assert any("超卖" in line for line in r)

    def test_above_upper_band(self):
        """价格 > 布林上轨 → -10"""
        s, r = _score_bollinger({"bb_upper": 110, "bb_lower": 90}, 115)
        assert s == pytest.approx(-10.0)
        assert any("超买" in line for line in r)

    def test_neutral(self):
        """价格在布林带内 → 0"""
        s, r = _score_bollinger({"bb_upper": 110, "bb_lower": 90}, 100)
        assert s == pytest.approx(0.0)
        assert any("布林带位置" in line for line in r)

    def test_flat_band_returns_neutral(self):
        """上下轨相等时返回中性，避免除零。"""
        s, r = _score_bollinger({"bb_upper": 100, "bb_lower": 100}, 100)
        assert s == pytest.approx(0.0)
        assert any("宽度不足" in line for line in r)


class TestScoreSupertrend:
    """测试 _score_supertrend — Supertrend 评分"""

    def test_missing_column(self):
        """缺少 supertrend_dir 时返回中性"""
        s, r = _score_supertrend({"close": 100})
        assert s == 0.0
        assert r == []

    def test_bullish(self):
        """direction > 0 → +20"""
        s, r = _score_supertrend({"supertrend_dir": 1, "supertrend": 2000})
        assert s == pytest.approx(20.0)
        assert any("看多" in line for line in r)

    def test_bearish(self):
        """direction <= 0 → -20"""
        s, r = _score_supertrend({"supertrend_dir": -1, "supertrend": 2000})
        assert s == pytest.approx(-20.0)
        assert any("看空" in line for line in r)


class TestScoreADX:
    """测试 _score_adx — ADX 趋势强度评分"""

    def test_missing_adx(self):
        """缺少 adx 时返回中性"""
        s, r = _score_adx({"close": 100}, 10)
        assert s == 0.0
        assert r == []

    def test_strong_bullish(self):
        """ADX > 25 且 score > 0 → +10"""
        s, r = _score_adx({"adx": 30}, 10)
        assert s == pytest.approx(10.0)
        assert any("强上升趋势" in line for line in r)

    def test_strong_bearish(self):
        """ADX > 25 且 score <= 0 → -10"""
        s, r = _score_adx({"adx": 30}, -10)
        assert s == pytest.approx(-10.0)
        assert any("强下降趋势" in line for line in r)

    def test_weak_trend(self):
        """ADX <= 25 → 0"""
        s, r = _score_adx({"adx": 20}, 10)
        assert s == pytest.approx(0.0)
        assert any("趋势较弱" in line for line in r)


class TestClassifySignal:
    """测试 _classify_signal — 信号分类"""

    def test_strong_buy(self):
        assert _classify_signal(60) == Signal.STRONG_BUY
        assert _classify_signal(50) == Signal.STRONG_BUY

    def test_buy(self):
        assert _classify_signal(30) == Signal.BUY
        assert _classify_signal(20) == Signal.BUY

    def test_neutral(self):
        assert _classify_signal(0) == Signal.NEUTRAL
        assert _classify_signal(10) == Signal.NEUTRAL
        assert _classify_signal(-10) == Signal.NEUTRAL

    def test_sell(self):
        assert _classify_signal(-30) == Signal.SELL
        assert _classify_signal(-20) == Signal.SELL

    def test_strong_sell(self):
        assert _classify_signal(-60) == Signal.STRONG_SELL
        assert _classify_signal(-50) == Signal.STRONG_SELL
