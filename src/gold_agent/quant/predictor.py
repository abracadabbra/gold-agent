"""时序预测 — Prophet + 外部回归因子"""

from typing import Optional

import pandas as pd
import logging
logger = logging.getLogger(__name__)


def predict_gold_price(
    df: pd.DataFrame,
    days: int = 7,
    regressors: Optional[dict[str, pd.Series]] = None,
) -> dict:
    """
    使用 Prophet 预测金价走势

    Args:
        df: 历史金价 DataFrame，必须包含 date, close 列
        days: 预测天数
        regressors: 外部回归因子 {名称: Series}，如 {"usd_index": ..., "vix": ...}

    Returns:
        {
            "forecast": DataFrame (ds, yhat, yhat_lower, yhat_upper),
            "trend": float,
            "changepoints": list,
            "components": dict (trend, weekly, yearly 的最新值)
        }
    """
    from prophet import Prophet

    logger.info(f"Prophet 预测: 未来 {days} 天")

    # 准备数据
    prophet_df = df[["date", "close"]].copy()
    prophet_df.columns = ["ds", "y"]
    prophet_df = prophet_df.dropna().sort_values("ds").reset_index(drop=True)

    if len(prophet_df) < 30:
        raise ValueError(f"数据不足: 需要至少 30 天，当前 {len(prophet_df)} 天")

    # 初始化模型
    model = Prophet(
        daily_seasonality=True,
        yearly_seasonality=True,
        weekly_seasonality=True,
        changepoint_prior_scale=0.05,  # 控制趋势灵活度
        seasonality_prior_scale=10.0,
    )

    # 添加外部回归因子
    if regressors:
        for name, series in regressors.items():
            if series is not None and not series.empty:
                # 对齐日期
                reg_df = pd.DataFrame({"ds": series.index, name: series.values})
                prophet_df = prophet_df.merge(reg_df, on="ds", how="left")
                prophet_df[name] = prophet_df[name].ffill().bfill()
                model.add_regressor(name)
                logger.info(f"  添加回归因子: {name}")

    # 训练
    model.fit(prophet_df)

    # 预测
    future = model.make_future_dataframe(periods=days)

    # 填充回归因子的未来值 (用最后一行)
    if regressors:
        for name in regressors:
            if name in prophet_df.columns:
                future[name] = prophet_df[name].iloc[-1]

    forecast = model.predict(future)

    # 提取结果
    result_df = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(days)
    result_df.columns = ["date", "predicted", "lower_bound", "upper_bound"]

    # 趋势
    trend_value = forecast["trend"].iloc[-1]
    trend_direction = "up" if forecast["trend"].diff().iloc[-1] > 0 else "down"

    # 变化点
    cp = model.changepoints if hasattr(model, "changepoints") else []
    changepoints = cp.tolist() if hasattr(cp, "tolist") else list(cp)

    # 组件
    components = {}
    for col in ["trend", "weekly", "yearly"]:
        if col in forecast.columns:
            components[col] = round(float(forecast[col].iloc[-1]), 2)

    result = {
        "forecast": result_df,
        "trend": round(float(trend_value), 2),
        "trend_direction": trend_direction,
        "changepoints": [str(cp) for cp in changepoints[-5:]],  # 最近5个变化点
        "components": components,
    }

    logger.info(
        f"Prophet 预测完成: 趋势={trend_value:.2f} ({trend_direction}), "
        f"区间 [{result_df['lower_bound'].iloc[-1]:.2f}, "
        f"{result_df['upper_bound'].iloc[-1]:.2f}]"
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
        date_str = row["date"].strftime("%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])[:10]
        lines.append(f"  {date_str}: ${row['predicted']:.2f} [{row['lower_bound']:.2f} ~ {row['upper_bound']:.2f}]")

    if pred_result["changepoints"]:
        lines.extend(["", "### 近期趋势变化点:"] + [f"  - {cp}" for cp in pred_result["changepoints"]])

    return "\n".join(lines)
