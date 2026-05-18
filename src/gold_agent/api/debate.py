"""辩论接口"""

from fastapi import APIRouter, HTTPException
import logging
logger = logging.getLogger(__name__)

from gold_agent.data.gold_price import fetch_gold_price
from gold_agent.data.macro import fetch_macro_yfinance
from gold_agent.data.news import fetch_news_with_sentiment
from gold_agent.data.cache import cache
from gold_agent.quant.indicators import get_indicator_summary
from gold_agent.quant.signals import generate_signal, get_signal_summary
from gold_agent.quant.predictor import predict_gold_price, get_prediction_summary
from gold_agent.debate.engine import DebateEngine

router = APIRouter(prefix="/api/debate", tags=["辩论"])


async def _build_context() -> str:
    """构建辩论上下文 — 汇总所有数据"""
    parts = []

    # 金价数据
    try:
        df = cache.get(key="gold_intl", fetch_fn=fetch_gold_price, source="intl", period="1y")
        parts.append("### 国际金价 (XAUUSD)\n" + get_indicator_summary(df))

        signal = generate_signal(df)
        parts.append(get_signal_summary(signal))
    except Exception as e:
        logger.warning(f"金价数据获取失败: {e}")

    # 预测
    try:
        pred = predict_gold_price(df, days=7)
        parts.append(get_prediction_summary(pred))
    except Exception as e:
        logger.warning(f"预测失败: {e}")

    # 宏观数据
    try:
        macro = fetch_macro_yfinance(period="1mo")
        if not macro.empty:
            latest = macro.iloc[-1]
            lines = ["### 宏观指标 (最新值)"]
            for col in macro.columns:
                if col != "date" and latest.get(col) is not None:
                    lines.append(f"- {col}: {latest[col]:.2f}")
            parts.append("\n".join(lines))
    except Exception as e:
        logger.warning(f"宏观数据获取失败: {e}")

    # 新闻
    try:
        news_df = fetch_news_with_sentiment()
        if not news_df.empty:
            avg = news_df["sentiment_score"].mean()
            label = "看多" if avg > 0.2 else "看空" if avg < -0.2 else "中性"
            lines = [f"### 新闻情绪 (平均得分: {avg:.3f}, 倾向: {label})"]
            for _, row in news_df.head(10).iterrows():
                lines.append(f"- [{row['sentiment_label']}] {row['title']}")
            parts.append("\n".join(lines))
    except Exception as e:
        logger.warning(f"新闻获取失败: {e}")

    return "\n\n---\n\n".join(parts)


@router.post("/run")
async def run_debate():
    """运行完整辩论流程"""
    try:
        logger.info("开始构建辩论上下文...")
        context = await _build_context()

        logger.info("开始辩论...")
        engine = DebateEngine()
        result = await engine.run_debate(context)

        return {
            "summary": result.to_summary(),
            "detail": result.to_dict(),
        }
    except Exception as e:
        logger.error(f"辩论失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick")
async def quick_analysis():
    """快速分析 (不走辩论，直接出信号)"""
    try:
        df = cache.get(key="gold_intl", fetch_fn=fetch_gold_price, source="intl", period="1y")

        signal = generate_signal(df)
        indicators = get_indicator_summary(df)

        return {
            "signal": signal.to_dict(),
            "indicators": indicators,
        }
    except Exception as e:
        logger.error(f"快速分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
