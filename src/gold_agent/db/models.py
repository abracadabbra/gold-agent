"""SQLAlchemy 模型 — 黄金分析系统数据库设计"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class GoldPrice(Base):
    """金价数据表"""
    __tablename__ = "gold_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, index=True)
    source = Column(String(50), nullable=False)  # xauusd, etf, spot_cny
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float, nullable=False)
    volume = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 复合索引：按数据源和日期查询
    __table_args__ = (
        Index('idx_source_date', 'source', 'date'),
    )

    def __repr__(self):
        return f"<GoldPrice(date={self.date}, source={self.source}, close={self.close})>"


class TechnicalIndicator(Base):
    """技术指标表"""
    __tablename__ = "technical_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, index=True)
    source = Column(String(50), nullable=False)

    # 移动平均线
    ma5 = Column(Float)
    ma10 = Column(Float)
    ma20 = Column(Float)
    ma60 = Column(Float)
    ema12 = Column(Float)
    ema26 = Column(Float)

    # MACD
    macd_line = Column(Float)
    macd_signal = Column(Float)
    macd_hist = Column(Float)

    # 振荡器
    rsi14 = Column(Float)
    stoch_k = Column(Float)
    stoch_d = Column(Float)

    # 波动率
    bb_upper = Column(Float)
    bb_mid = Column(Float)
    bb_lower = Column(Float)
    atr14 = Column(Float)

    # 趋势强度
    adx = Column(Float)
    supertrend = Column(Float)
    supertrend_dir = Column(Integer)  # 1=看多, -1=看空

    # 成交量
    obv = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_indicator_source_date', 'source', 'date'),
    )

    def __repr__(self):
        return f"<TechnicalIndicator(date={self.date}, source={self.source}, rsi={self.rsi14})>"


class TradeSignal(Base):
    """交易信号表"""
    __tablename__ = "trade_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, index=True)
    source = Column(String(50), nullable=False)
    signal_type = Column(String(20), nullable=False)  # strong_buy, buy, neutral, sell, strong_sell
    score = Column(Float, nullable=False)  # -100 到 +100
    confidence = Column(Float, nullable=False)  # 0 到 1
    reasons = Column(JSON)  # 信号依据列表
    stop_loss = Column(Float)
    take_profit = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TradeSignal(date={self.date}, signal={self.signal_type}, score={self.score})>"


class Prediction(Base):
    """预测结果表"""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_date = Column(DateTime, nullable=False, index=True)  # 预测日期
    target_date = Column(DateTime, nullable=False)  # 目标日期
    source = Column(String(50), nullable=False)
    predicted_price = Column(Float, nullable=False)
    lower_bound = Column(Float)
    upper_bound = Column(Float)
    trend_direction = Column(String(10))  # up, down
    trend_value = Column(Float)
    changepoints = Column(JSON)  # 变化点列表
    components = Column(JSON)  # 趋势、周期等组件
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_prediction_date', 'prediction_date', 'target_date'),
    )

    def __repr__(self):
        return f"<Prediction(target={self.target_date}, price={self.predicted_price})>"


class DebateResult(Base):
    """辩论结果表"""
    __tablename__ = "debate_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, index=True)

    # 看多方
    bull_stance = Column(String(20))
    bull_confidence = Column(Integer)
    bull_arguments = Column(JSON)
    bull_price_target = Column(JSON)
    bull_key_risk = Column(Text)

    # 看空方
    bear_stance = Column(String(20))
    bear_confidence = Column(Integer)
    bear_arguments = Column(JSON)
    bear_price_target = Column(JSON)
    bear_counter_to_bull = Column(Text)
    bear_key_risk = Column(Text)

    # 数据审计
    audit_bull_claims = Column(JSON)
    audit_bear_claims = Column(JSON)
    audit_missed_data = Column(JSON)
    audit_overall_assessment = Column(Text)

    # 仲裁裁决
    verdict = Column(String(20))  # bullish, bearish, sideways
    verdict_confidence = Column(Integer)
    verdict_price_range = Column(JSON)
    verdict_time_horizon = Column(String(10))
    verdict_key_reasons = Column(JSON)
    verdict_risk_warnings = Column(JSON)
    verdict_data_quality_score = Column(Integer)
    verdict_quant_signal = Column(Text)
    verdict_llm_signal = Column(Text)
    verdict_final_advice = Column(Text)

    # 元数据
    context_data = Column(JSON)  # 输入的上下文数据
    raw_responses = Column(JSON)  # 原始LLM响应
    tokens_used = Column(Integer)  # 总token使用量
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DebateResult(date={self.date}, verdict={self.verdict})>"


class BacktestResult(Base):
    """回测结果表"""
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_date = Column(DateTime, nullable=False, index=True)
    strategy = Column(String(50), nullable=False)
    period = Column(String(10), nullable=False)  # 1y, 2y, 5y
    initial_cash = Column(Float, nullable=False)
    final_value = Column(Float, nullable=False)
    total_return = Column(Float, nullable=False)  # 百分比
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    win_rate = Column(Float)
    equity_curve = Column(JSON)  # 资金曲线数据
    trade_log = Column(JSON)  # 交易记录
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BacktestResult(strategy={self.strategy}, return={self.total_return})>"


class MacroData(Base):
    """宏观经济数据表"""
    __tablename__ = "macro_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, index=True)
    indicator = Column(String(50), nullable=False)  # usd_index, us_10y, vix, cpi, fed_rate
    value = Column(Float, nullable=False)
    source = Column(String(20), nullable=False)  # yfinance, fred
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_macro_indicator_date', 'indicator', 'date'),
    )

    def __repr__(self):
        return f"<MacroData(date={self.date}, indicator={self.indicator}, value={self.value})>"


class NewsArticle(Base):
    """新闻文章表"""
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    published_date = Column(DateTime, index=True)
    title = Column(String(500), nullable=False)
    link = Column(String(1000))
    source = Column(String(50))  # google_news, reuters, kitco
    sentiment_score = Column(Float)  # -1 到 +1
    sentiment_label = Column(String(20))  # bullish, bearish, neutral
    bull_hits = Column(JSON)  # 看多关键词
    bear_hits = Column(JSON)  # 看空关键词
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<NewsArticle(title={self.title[:50]}..., sentiment={self.sentiment_label})>"


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemConfig(key={self.key})>"


# 数据库初始化辅助函数
def create_tables(engine):
    """创建所有表"""
    Base.metadata.create_all(engine)


def get_table_stats(session):
    """获取各表记录数统计"""
    tables = [
        GoldPrice, TechnicalIndicator, TradeSignal, Prediction,
        DebateResult, BacktestResult, MacroData, NewsArticle
    ]

    stats = {}
    for table in tables:
        try:
            count = session.query(table).count()
            stats[table.__tablename__] = count
        except Exception as e:
            stats[table.__tablename__] = f"Error: {e}"

    return stats
