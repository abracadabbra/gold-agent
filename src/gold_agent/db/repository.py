"""数据仓库 — 数据持久化到 DB"""

import logging
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from gold_agent.db.models import GoldPrice, TechnicalIndicator, TradeSignal, MacroData, NewsArticle

logger = logging.getLogger(__name__)


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """将 DataFrame 转为 dict 列表，处理 NaN 和 NaT"""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == "datetime64[ns]":
            df[col] = df[col].where(df[col].notna(), None)
        elif df[col].dtype == "object":
            df[col] = df[col].where(df[col].notna(), None)
    return df.where(df.notna(), None).to_dict(orient="records")


def save_gold_prices(db: Session, records: list[dict]) -> int:
    """批量写入金价数据，按 (date, source) 去重"""
    saved = 0
    for rec in records:
        date = pd.to_datetime(rec.get("date")).to_pydatetime()
        source = rec.get("source", "intl")
        existing = db.query(GoldPrice).filter(
            GoldPrice.date == date, GoldPrice.source == source
        ).first()
        if not existing:
            db.add(GoldPrice(
                date=date,
                source=source,
                open=rec.get("open"),
                high=rec.get("high"),
                low=rec.get("low"),
                close=rec.get("close"),
                volume=rec.get("volume"),
            ))
            saved += 1
    if saved:
        db.commit()
        logger.debug(f"DB 写入 GoldPrice: {saved} 行")
    return saved


def save_technical_indicators(db: Session, records: list[dict]) -> int:
    """批量写入技术指标，按 (date, source) 去重"""
    saved = 0
    for rec in records:
        date = pd.to_datetime(rec.get("date")).to_pydatetime()
        source = rec.get("source", "intl")
        existing = db.query(TechnicalIndicator).filter(
            TechnicalIndicator.date == date, TechnicalIndicator.source == source
        ).first()
        if not existing:
            db.add(TechnicalIndicator(
                date=date,
                source=source,
                ma5=rec.get("ma5"),
                ma10=rec.get("ma10"),
                ma20=rec.get("ma20"),
                ma60=rec.get("ma60"),
                ema12=rec.get("ema12"),
                ema26=rec.get("ema26"),
                macd_line=rec.get("macd_line"),
                macd_signal=rec.get("macd_signal"),
                macd_hist=rec.get("macd_histogram"),
                rsi14=rec.get("rsi14"),
                stoch_k=rec.get("stoch_k"),
                stoch_d=rec.get("stoch_d"),
                bb_upper=rec.get("bb_upper"),
                bb_mid=rec.get("bb_middle"),
                bb_lower=rec.get("bb_lower"),
                atr14=rec.get("atr14"),
                adx=rec.get("adx"),
                supertrend=rec.get("supertrend"),
                supertrend_dir=rec.get("supertrend_direction"),
                obv=rec.get("obv"),
            ))
            saved += 1
    if saved:
        db.commit()
        logger.debug(f"DB 写入 TechnicalIndicator: {saved} 行")
    return saved


def save_trade_signal(db: Session, signal: dict) -> bool:
    """写入单条交易信号"""
    date = pd.to_datetime(signal.get("date", datetime.utcnow())).to_pydatetime()
    source = signal.get("source", "intl")
    existing = db.query(TradeSignal).filter(
        TradeSignal.date == date, TradeSignal.source == source
    ).first()
    if existing:
        return False
    db.add(TradeSignal(
        date=date,
        source=source,
        signal_type=signal.get("signal", "neutral"),
        score=signal.get("score", 0),
        confidence=signal.get("confidence", 0.5),
        reasons=signal.get("reasons", []),
        stop_loss=signal.get("stop_loss"),
        take_profit=signal.get("take_profit"),
    ))
    db.commit()
    logger.debug(f"DB 写入 TradeSignal: {signal.get('signal')} @ {date}")
    return True


def save_macro_data(db: Session, records: list[dict], indicator_col: str = "indicator") -> int:
    """批量写入宏观数据，按 (date, indicator) 去重"""
    saved = 0
    for rec in records:
        date = pd.to_datetime(rec.get("date")).to_pydatetime()
        indicator = rec.get(indicator_col) or rec.get("indicator", "")
        value = rec.get("value") or rec.get(rec.get(indicator_col, ""))
        source = rec.get("source", "yfinance")

        if not indicator or value is None:
            continue

        existing = db.query(MacroData).filter(
            MacroData.date == date, MacroData.indicator == indicator
        ).first()
        if not existing:
            db.add(MacroData(
                date=date,
                indicator=indicator,
                value=float(value),
                source=source,
            ))
            saved += 1
    if saved:
        db.commit()
        logger.debug(f"DB 写入 MacroData: {saved} 行")
    return saved


def save_news_articles(db: Session, records: list[dict]) -> int:
    """批量写入新闻，按 title 去重"""
    saved = 0
    for rec in records:
        title = rec.get("title", "").strip()
        if not title:
            continue
        existing = db.query(NewsArticle).filter(NewsArticle.title == title).first()
        if not existing:
            pub_date = rec.get("published_date")
            published = pd.to_datetime(pub_date).to_pydatetime() if pub_date else None
            db.add(NewsArticle(
                published_date=published,
                title=title,
                link=rec.get("link"),
                source=rec.get("source"),
                sentiment_score=rec.get("sentiment_score"),
                sentiment_label=rec.get("sentiment_label"),
            ))
            saved += 1
    if saved:
        db.commit()
        logger.debug(f"DB 写入 NewsArticle: {saved} 行")
    return saved


def get_table_stats(db: Session) -> dict:
    """获取各表记录数"""
    from gold_agent.db.models import get_table_stats
    return get_table_stats(db)
