"""Predictor 单元测试 — Prophet 时序预测"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from gold_agent.quant.predictor import (
    evaluate_naive_forecast,
    get_prediction_summary,
    predict_gold_price,
)


@pytest.fixture
def sample_ohlcv():
    """生成模拟 OHLCV 数据 (50 天)"""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=50, freq="D")
    prices = 2000 + np.cumsum(np.random.randn(50) * 10)
    return pd.DataFrame({"date": dates, "close": prices})


@pytest.fixture
def sample_tiny():
    """生成不足 30 天的数据"""
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    return pd.DataFrame({"date": dates, "close": [2000] * 20})


@pytest.fixture
def mock_prophet():
    """创建 Prophet mock 实例和补丁"""
    dates = pd.date_range("2024-01-01", periods=57, freq="D")

    forecast_df = pd.DataFrame({
        "ds": dates,
        "yhat": np.linspace(2000, 2050, 57) + np.random.randn(57) * 5,
        "yhat_lower": np.linspace(1980, 2020, 57) + np.random.randn(57) * 5,
        "yhat_upper": np.linspace(2020, 2080, 57) + np.random.randn(57) * 5,
        "trend": np.linspace(2000, 2050, 57),
        "weekly": np.random.randn(57),
        "yearly": np.random.randn(57),
    })
    future_df = pd.DataFrame({"ds": dates})

    instance = MagicMock()
    instance.predict.return_value = forecast_df
    instance.make_future_dataframe.return_value = future_df
    instance.changepoints = [dates[10], dates[20], dates[30]]

    patcher = patch("prophet.Prophet", return_value=instance)
    mock_class = patcher.start()
    yield instance, mock_class
    patcher.stop()


# ============================================================
# predict_gold_price
# ============================================================


def test_predict_gold_price_success(sample_ohlcv, mock_prophet):
    """正常预测流程 — 验证结果结构和 Prophet 调用"""
    mock_instance, mock_class = mock_prophet
    result = predict_gold_price(sample_ohlcv, days=7)

    # 结果结构
    assert "forecast" in result
    assert "trend" in result
    assert isinstance(result["trend"], float)
    assert "trend_direction" in result
    assert result["trend_direction"] in ("up", "down")
    assert "changepoints" in result
    assert isinstance(result["changepoints"], list)
    assert "components" in result

    # 预测表
    forecast = result["forecast"]
    assert list(forecast.columns) == ["date", "predicted", "lower_bound", "upper_bound"]
    assert len(forecast) == 7  # days=7

    # Prophet 初始化参数
    mock_class.assert_called_once_with(
        daily_seasonality=True,
        yearly_seasonality=True,
        weekly_seasonality=True,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10.0,
    )

    # fit 被调用
    mock_instance.fit.assert_called_once()

    # make_future_dataframe 使用正确 days
    mock_instance.make_future_dataframe.assert_called_once_with(periods=7)

    # predict 被调用
    mock_instance.predict.assert_called_once()


def test_predict_gold_price_with_regressors(sample_ohlcv, mock_prophet):
    """带外部回归因子的预测"""
    mock_instance, _ = mock_prophet

    reg_series = pd.Series(
        np.random.randn(50) * 5 + 100,
        index=sample_ohlcv["date"],
        name="usd_index",
    )
    regressors = {"usd_index": reg_series}

    result = predict_gold_price(sample_ohlcv, days=7, regressors=regressors)

    assert "forecast" in result
    assert len(result["forecast"]) == 7

    # 验证 add_regressor 被调用
    mock_instance.add_regressor.assert_called_once_with("usd_index")


def test_predict_gold_price_empty_regressor_dict(sample_ohlcv, mock_prophet):
    """空回归因子字典不应影响流程"""
    mock_instance, _ = mock_prophet

    result = predict_gold_price(sample_ohlcv, days=7, regressors={})

    assert "forecast" in result
    assert len(result["forecast"]) == 7
    mock_instance.add_regressor.assert_not_called()


def test_predict_gold_price_none_regressor(sample_ohlcv, mock_prophet):
    """regressors=None 不应调用 add_regressor"""
    mock_instance, _ = mock_prophet

    result = predict_gold_price(sample_ohlcv, days=7, regressors=None)

    assert "forecast" in result
    mock_instance.add_regressor.assert_not_called()


def test_predict_gold_price_insufficient_data(sample_tiny):
    """数据不足应抛出 ValueError"""
    with pytest.raises(ValueError, match="数据不足"):
        predict_gold_price(sample_tiny)


def test_predict_gold_price_different_days(sample_ohlcv, mock_prophet):
    """不同预测天数"""
    mock_instance, _ = mock_prophet

    result_3 = predict_gold_price(sample_ohlcv, days=3)
    assert len(result_3["forecast"]) == 3

    result_14 = predict_gold_price(sample_ohlcv, days=14)
    assert len(result_14["forecast"]) == 14


# ============================================================
# evaluate_naive_forecast
# ============================================================


def test_evaluate_naive_forecast_returns_error_metrics():
    """naive baseline 评估返回 MAE/RMSE/MAPE。"""
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=5, freq="D"),
        "close": [100.0, 102.0, 101.0, 105.0, 110.0],
    })

    result = evaluate_naive_forecast(df, horizon=1, window=4)

    assert result["baseline"] == "naive_last_value"
    assert result["horizon_days"] == 1
    assert result["window"] == 4
    assert result["sample_size"] == 4
    assert result["moving_average_window"] == 5
    assert result["mae"] == 3.0
    assert result["rmse"] == pytest.approx(3.3912)
    assert result["mape"] == pytest.approx(2.8265)
    assert [item["baseline"] for item in result["baselines"]] == [
        "naive_last_value",
        "moving_average",
        "linear_trend",
    ]
    assert result["baselines"][0]["mae"] == result["mae"]
    assert result["baselines"][0]["rmse"] == result["rmse"]
    assert result["baselines"][0]["mape"] == result["mape"]


def test_evaluate_naive_forecast_empty_data():
    result = evaluate_naive_forecast(pd.DataFrame(), horizon=1, window=60)

    assert result["sample_size"] == 0
    assert result["mae"] is None
    assert result["rmse"] is None
    assert result["mape"] is None
    assert result["moving_average_window"] == 5
    assert result["baselines"] == []


def test_evaluate_naive_forecast_validates_args(sample_ohlcv):
    with pytest.raises(ValueError, match="horizon"):
        evaluate_naive_forecast(sample_ohlcv, horizon=0)
    with pytest.raises(ValueError, match="window"):
        evaluate_naive_forecast(sample_ohlcv, window=0)
    with pytest.raises(ValueError, match="moving_average_window"):
        evaluate_naive_forecast(sample_ohlcv, moving_average_window=0)


# ============================================================
# get_prediction_summary
# ============================================================


def test_get_prediction_summary(sample_ohlcv, mock_prophet):
    """预测摘要应包含关键信息"""
    result = predict_gold_price(sample_ohlcv, days=7)
    summary = get_prediction_summary(result)

    assert "Prophet" in summary
    assert "最终预测价" in summary
    assert "预测区间" in summary
    assert "趋势方向" in summary
    assert "趋势值" in summary
    assert "逐日预测" in summary


def test_get_prediction_summary_without_changepoints(sample_ohlcv, mock_prophet):
    """无变化点时不应显示变化点章节"""
    mock_instance, _ = mock_prophet
    mock_instance.changepoints = []

    result = predict_gold_price(sample_ohlcv, days=7)
    summary = get_prediction_summary(result)

    assert "近期趋势变化点" not in summary


def test_get_prediction_summary_custom_forecast():
    """直接构造 pred_result 测试"""
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    forecast = pd.DataFrame({
        "date": dates,
        "predicted": [2000.0, 2010.0, 2020.0],
        "lower_bound": [1980.0, 1990.0, 2000.0],
        "upper_bound": [2020.0, 2030.0, 2040.0],
    })
    result = {
        "forecast": forecast,
        "trend": 2010.0,
        "trend_direction": "up",
        "changepoints": [],
        "components": {"trend": 2010.0},
    }

    summary = get_prediction_summary(result)
    assert "$2000.00" in summary
    assert "上行" in summary
    assert "01-03" in summary
