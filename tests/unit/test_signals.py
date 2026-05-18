"""信号生成单元测试"""

import numpy as np
import pandas as pd
import pytest

from gold_agent.quant.signals import Signal, generate_signal


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
