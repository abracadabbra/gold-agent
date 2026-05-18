"""技术指标单元测试"""

import numpy as np
import pandas as pd
import pytest

from gold_agent.quant.indicators import compute_indicators, get_indicator_summary


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
