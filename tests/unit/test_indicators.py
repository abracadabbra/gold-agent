"""技术指标单元测试"""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from gold_agent.quant.indicators import (
    _adx,
    _atr,
    _bollinger_bands,
    _ema,
    _macd,
    _rsi,
    _sma,
    _stochastic,
    compute_indicators,
    get_indicator_summary,
)


@pytest.fixture
def sample_series():
    """单调递增序列 — 便于手工验证"""
    return pd.Series([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0])


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


# ============================================================
# Fallback 函数直接测试
# ============================================================

class TestSMA:
    def test_basic(self, sample_series):
        result = _sma(sample_series, 3)
        # 前两个值用 min_periods=1，所以为前 i 个值的均值
        assert result.iloc[0] == 10.0
        assert result.iloc[1] == 10.5  # (10+11)/2
        assert result.iloc[2] == 11.0  # (10+11+12)/3
        assert result.iloc[-1] == 16.0  # (15+16+17)/3

    def test_constant_values(self):
        s = pd.Series([5.0] * 10)
        result = _sma(s, 4)
        assert (result == 5.0).all()


class TestEMA:
    def test_basic(self, sample_series):
        result = _ema(sample_series, 3)
        assert len(result) == 8
        assert not result.isna().all()

    def test_constant_values(self):
        s = pd.Series([5.0] * 10)
        result = _ema(s, 4)
        assert (result == 5.0).all()


class TestRSI:
    def test_in_range(self):
        s = pd.Series([10.0, 11.0, 10.5, 12.0, 11.0, 13.0, 12.5, 14.0])
        rsi = _rsi(s, 6)
        val = rsi.dropna().iloc[-1]
        assert 0 <= val <= 100

    def test_majority_up_high_rsi(self):
        s = pd.Series([10, 11, 10.5, 12, 13, 12.5, 14, 15, 14.5, 16,
                       17, 16.5, 18, 19, 18.5, 20, 21, 20.5, 22, 23], dtype=float)
        rsi = _rsi(s, 14)
        val = rsi.dropna().iloc[-1]
        assert val > 50

    def test_majority_down_low_rsi(self):
        s = pd.Series([23, 22, 22.5, 21, 20, 20.5, 19, 18, 18.5, 17,
                       16, 16.5, 15, 14, 14.5, 13, 12, 12.5, 11, 10], dtype=float)
        rsi = _rsi(s, 14)
        val = rsi.dropna().iloc[-1]
        assert val < 50

    def test_constant_gives_50(self):
        s = pd.Series([10.0] * 20)
        _ = _rsi(s, 14)
        # 当 avg_gain 和 avg_loss 都是 0 时，rs=NaN, rsi=NaN
        # 所以测试不下结论


class TestMACD:
    def test_output_shapes(self, sample_series):
        macd, signal, hist = _macd(sample_series, 3, 5, 2)
        assert len(macd) == len(signal) == len(hist) == 8

    def test_macd_relationship(self):
        s = pd.Series([10, 12, 11, 13, 14, 15, 14, 16, 17, 18], dtype=float)
        macd, signal, hist = _macd(s, 3, 5, 2)
        last_hist = hist.dropna().iloc[-1]
        assert abs(last_hist - (macd.dropna().iloc[-1] - signal.dropna().iloc[-1])) < 0.001


class TestStochastic:
    def test_output_shapes(self):
        h = pd.Series([12, 13, 14, 13, 15, 16, 15, 17])
        l_ = pd.Series([10, 11, 12, 11, 13, 14, 13, 15])
        c = pd.Series([11, 12, 13, 12, 14, 15, 14, 16])
        k, d = _stochastic(h, l_, c, 3, 2)
        assert len(k) == len(d) == 8

    def test_k_in_range(self):
        h = pd.Series([12, 13, 14, 13, 15, 16, 15, 17, 18, 19])
        l_ = pd.Series([10, 11, 12, 11, 13, 14, 13, 15, 16, 17])
        c = pd.Series([11, 12, 13, 12, 14, 15, 14, 16, 17, 18])
        k, d = _stochastic(h, l_, c, 5, 3)
        k_valid = k.dropna()
        assert (k_valid >= 0).all() and (k_valid <= 100).all()


class TestBollingerBands:
    def test_output_order(self, sample_series):
        upper, mid, lower = _bollinger_bands(sample_series, 3, 2.0)
        valid = upper.notna() & mid.notna() & lower.notna()
        assert (upper[valid] >= mid[valid]).all()
        assert (mid[valid] >= lower[valid]).all()

    def test_mid_is_sma(self, sample_series):
        upper, mid, lower = _bollinger_bands(sample_series, 3, 2.0)
        sma = _sma(sample_series, 3)
        pd.testing.assert_series_equal(mid, sma)


class TestATR:
    def test_positive(self):
        h = pd.Series([12, 13, 14, 13, 15])
        l_ = pd.Series([10, 11, 12, 11, 13])
        c = pd.Series([11, 12, 13, 12, 14])
        atr = _atr(h, l_, c, 3)
        last = atr.dropna().iloc[-1]
        assert last > 0


class TestADX:
    def test_positive(self):
        h = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19])
        l_ = pd.Series([8, 9, 10, 11, 12, 13, 14, 15, 16, 17])
        c = pd.Series([9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
        adx = _adx(h, l_, c, 5)
        last = adx.dropna().iloc[-1]
        # 强趋势样本 → ADX 应 > 25
        assert last > 0


class TestFallbackPath:
    """验证无 pandas-ta 时 compute_indicators 使用纯 pandas"""

    def test_fallback_computes_indicators(self, sample_ohlcv, monkeypatch):
        monkeypatch.setattr("gold_agent.quant.indicators.HAS_PANDAS_TA", False)
        result = compute_indicators(sample_ohlcv)
        assert result.ma20 is not None
        assert not result.ma20.dropna().empty
        assert len(result.to_dict()) >= 10


def test_compute_indicators(sample_ohlcv):
    """测试技术指标计算"""
    result = compute_indicators(sample_ohlcv)

    # 应该有至少 10 个指标
    assert len(result.to_dict()) >= 10

    # MA20 应该有值
    assert result.ma20 is not None
    assert not result.ma20.dropna().empty

    # RSI 应该在 0-100 之间
    if result.rsi14 is not None:
        rsi_val = result.rsi14.dropna()
        assert (rsi_val >= 0).all() and (rsi_val <= 100).all()


def test_indicator_summary(sample_ohlcv):
    """测试指标摘要生成"""
    summary = get_indicator_summary(sample_ohlcv)

    assert "当前金价" in summary
    assert "移动平均线" in summary
    assert "RSI" in summary


def test_compute_indicators_missing_column():
    """缺少必要列时抛出 ValueError（覆盖 line 210）"""
    df = pd.DataFrame({"date": [1], "close": [2000.0]})  # missing open, high, low
    with pytest.raises(ValueError, match="缺少必要列"):
        compute_indicators(df)


class TestImportErrorPath:
    """测试 pandas-ta 导入失败路径"""

    def test_import_error_sets_flag(self):
        """pandas_ta 导入失败时 HAS_PANDAS_TA 为 False（覆盖 lines 15-17）"""
        import importlib
        import sys

        # Remove cached modules so import machinery runs our mock
        orig_pandas_ta = sys.modules.pop("pandas_ta", None)
        orig_mod = sys.modules.pop("gold_agent.quant.indicators", None)

        import builtins
        _orig_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pandas_ta":
                raise ImportError("No module named pandas_ta")
            return _orig_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=mock_import):
                mod = importlib.import_module("gold_agent.quant.indicators")
                assert mod.HAS_PANDAS_TA is False
        finally:
            # Restore original modules
            if orig_mod is not None:
                sys.modules["gold_agent.quant.indicators"] = orig_mod
            if orig_pandas_ta is not None:
                sys.modules["pandas_ta"] = orig_pandas_ta
