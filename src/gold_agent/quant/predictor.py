"""时序预测 — Prophet + 外部回归因子"""


import pandas as pd
import logging
logger = logging.getLogger(__name__)


def _forecast_error_metrics(actual: pd.Series, predicted: pd.Series) -> dict:
    """Calculate common forecast error metrics for aligned series."""
    errors = actual - predicted
    mae = float(errors.abs().mean())
    rmse = float((errors.pow(2).mean()) ** 0.5)
    nonzero = actual != 0
    mape = (
        float((errors[nonzero].abs() / actual[nonzero].abs()).mean() * 100)
        if nonzero.any()
        else None
    )
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 4) if mape is not None else None,
    }


def _empty_forecast_evaluation(
    horizon: int,
    window: int,
    moving_average_window: int,
) -> dict:
    return {
        "baseline": "naive_last_value",
        "horizon_days": horizon,
        "window": window,
        "sample_size": 0,
        "moving_average_window": moving_average_window,
        "mae": None,
        "rmse": None,
        "mape": None,
        "baselines": [],
    }


def _baseline_result(
    name: str,
    actual: pd.Series,
    predicted: pd.Series,
) -> dict:
    aligned = pd.DataFrame({"actual": actual, "predicted": predicted}).dropna()
    if aligned.empty:
        metrics = {"mae": None, "rmse": None, "mape": None}
    else:
        metrics = _forecast_error_metrics(aligned["actual"], aligned["predicted"])
    return {
        "baseline": name,
        **metrics,
    }


def evaluate_naive_forecast(
    df: pd.DataFrame,
    *,
    horizon: int = 1,
    window: int = 60,
    moving_average_window: int = 5,
) -> dict:
    """Evaluate lightweight historical forecast baselines.

    It does not run Prophet repeatedly, so the endpoint can expose historical
    error context without making the dashboard slow. The top-level metrics keep
    the previous naive-last-value shape for API compatibility.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if window < 1:
        raise ValueError("window must be >= 1")
    if moving_average_window < 1:
        raise ValueError("moving_average_window must be >= 1")

    if df.empty or "close" not in df.columns:
        return _empty_forecast_evaluation(horizon, window, moving_average_window)

    series = df[["date", "close"]].copy() if "date" in df.columns else df[["close"]].copy()
    series["close"] = pd.to_numeric(series["close"], errors="coerce")
    if "date" in series.columns:
        series["date"] = pd.to_datetime(series["date"], errors="coerce")
        series = series.dropna(subset=["date"]).sort_values("date")
    series = series.dropna(subset=["close"]).tail(window + horizon).reset_index(drop=True)

    actual = series["close"].iloc[horizon:].reset_index(drop=True)
    predicted = series["close"].shift(horizon).iloc[horizon:].reset_index(drop=True)
    sample_size = int(len(actual))
    if sample_size == 0:
        metrics = {"mae": None, "rmse": None, "mape": None}
        baselines: list[dict] = []
    else:
        metrics = _forecast_error_metrics(actual, predicted)
        close = series["close"]
        moving_average = (
            close
            .rolling(moving_average_window, min_periods=1)
            .mean()
            .shift(horizon)
            .iloc[horizon:]
            .reset_index(drop=True)
        )
        trend_step = close.diff().rolling(moving_average_window, min_periods=1).mean()
        linear_trend = (
            (close.shift(horizon) + trend_step.shift(horizon) * horizon)
            .iloc[horizon:]
            .reset_index(drop=True)
        )
        baselines = [
            _baseline_result("naive_last_value", actual, predicted),
            _baseline_result("moving_average", actual, moving_average),
            _baseline_result("linear_trend", actual, linear_trend),
        ]

    return {
        "baseline": "naive_last_value",
        "horizon_days": horizon,
        "window": window,
        "sample_size": sample_size,
        "moving_average_window": moving_average_window,
        **metrics,
        "baselines": baselines,
    }


def _prepare_prophet_data(df: pd.DataFrame, days: int) -> tuple[pd.DataFrame, int]:
    """准备 Prophet 输入数据"""
    prophet_df = df[["date", "close"]].copy()
    prophet_df.columns = ["ds", "y"]
    prophet_df = prophet_df.dropna().sort_values("ds").reset_index(drop=True)
    if len(prophet_df) < 30:
        raise ValueError(f"数据不足: 需要至少 30 天，当前 {len(prophet_df)} 天")
    return prophet_df, days


def _add_regressors(prophet_df: pd.DataFrame, regressors: dict | None, model) -> pd.DataFrame:
    """添加外部回归因子到 Prophet 模型"""
    if not regressors:
        return prophet_df
    for name, series in regressors.items():
        if series is not None and not series.empty:
            reg_df = pd.DataFrame({"ds": series.index, name: series.values})
            prophet_df = prophet_df.merge(reg_df, on="ds", how="left")
            prophet_df[name] = prophet_df[name].ffill().bfill()
            model.add_regressor(name)
            logger.info(f"  添加回归因子: {name}")
    return prophet_df


def _fill_future_regressors(
    future: pd.DataFrame, prophet_df: pd.DataFrame, regressors: dict | None
) -> pd.DataFrame:
    """用历史最后一行填充回归因子的未来值"""
    if not regressors:
        return future
    for name in regressors:
        if name in prophet_df.columns:
            future[name] = prophet_df[name].iloc[-1]
    return future


def _extract_forecast(forecast, model, days: int) -> dict:
    """从 Prophet 预测结果中提取返回值"""
    result_df = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(days)
    result_df.columns = ["date", "predicted", "lower_bound", "upper_bound"]

    trend_value = forecast["trend"].iloc[-1]
    trend_direction = "up" if forecast["trend"].diff().iloc[-1] > 0 else "down"

    cp = model.changepoints if hasattr(model, "changepoints") else []
    changepoints = cp.tolist() if hasattr(cp, "tolist") else list(cp)

    components = {}
    for col in ["trend", "weekly", "yearly"]:
        if col in forecast.columns:
            components[col] = round(float(forecast[col].iloc[-1]), 2)

    return {
        "forecast": result_df,
        "trend": round(float(trend_value), 2),
        "trend_direction": trend_direction,
        "changepoints": [str(cp) for cp in changepoints[-5:]],
        "components": components,
    }


def predict_gold_price(
    df: pd.DataFrame,
    days: int = 7,
    regressors: dict[str, pd.Series] | None = None,
) -> dict:
    """
    使用 Prophet 预测金价走势

    Args:
        df: 历史金价 DataFrame，必须包含 date, close 列
        days: 预测天数
        regressors: 外部回归因子 {名称: Series}，如 {"usd_index": ..., "vix": ...}

    Returns:
        forecast / trend / changepoints / components
    """
    from prophet import Prophet

    logger.info(f"Prophet 预测: 未来 {days} 天")

    prophet_df, days = _prepare_prophet_data(df, days)

    model = Prophet(
        daily_seasonality=True,
        yearly_seasonality=True,
        weekly_seasonality=True,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10.0,
    )

    prophet_df = _add_regressors(prophet_df, regressors, model)
    model.fit(prophet_df)

    future = model.make_future_dataframe(periods=days)
    future = _fill_future_regressors(future, prophet_df, regressors)
    forecast = model.predict(future)

    result = _extract_forecast(forecast, model, days)

    logger.info(
        f"Prophet 预测完成: 趋势={result['trend']:.2f} ({result['trend_direction']}), "
        f"区间 [{result['forecast']['lower_bound'].iloc[-1]:.2f}, "
        f"{result['forecast']['upper_bound'].iloc[-1]:.2f}]"
    )

    return result


def get_prediction_summary(pred_result: dict) -> str:
    """生成预测结果的 LLM 可读摘要"""
    df = pred_result["forecast"]
    latest = df.iloc[-1]

    lines = [
        f"## Prophet 时序预测 (未来 {len(df)} 天)",
        "",
        f"- 最终预测价: ${latest['predicted']:.2f}",
        f"- 预测区间: ${latest['lower_bound']:.2f} ~ ${latest['upper_bound']:.2f}",
        f"- 趋势方向: {'上行 📈' if pred_result['trend_direction'] == 'up' else '下行 📉'}",
        f"- 趋势值: {pred_result['trend']:.2f}",
        "",
        "### 逐日预测:",
    ]

    for _, row in df.iterrows():
        date_str = row["date"].strftime("%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])[:10]  # noqa: E501
        lines.append(f"  {date_str}: ${row['predicted']:.2f} [{row['lower_bound']:.2f} ~ {row['upper_bound']:.2f}]")  # noqa: E501

    if pred_result["changepoints"]:
        lines.extend(["", "### 近期趋势变化点:"] + [f"  - {cp}" for cp in pred_result["changepoints"]])  # noqa: E501

    return "\n".join(lines)
