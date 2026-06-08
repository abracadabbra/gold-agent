"""数据库模型单元测试"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from gold_agent.db.models import (
    BacktestResult,
    DataFetchRun,
    DebateResult,
    GoldPrice,
    MacroData,
    NewsArticle,
    Prediction,
    SystemConfig,
    TechnicalIndicator,
    TradeSignal,
    create_tables,
    get_table_stats,
)


class TestGoldPrice:
    """GoldPrice 模型测试"""

    def test_creation(self):
        """测试模型实例化"""
        gp = GoldPrice(
            date=datetime(2024, 1, 1),
            source="xauusd",
            open=2000.0,
            high=2010.0,
            low=1990.0,
            close=2005.0,
            volume=10000,
        )
        assert gp.source == "xauusd"
        assert gp.close == 2005.0
        assert gp.open == 2000.0
        assert gp.high == 2010.0
        assert gp.low == 1990.0
        assert gp.volume == 10000

    def test_repr(self):
        """测试 __repr__ 输出"""
        gp = GoldPrice(
            date=datetime(2024, 1, 1),
            source="xauusd",
            close=2005.0,
        )
        expected = "<GoldPrice(date=2024-01-01 00:00:00, source=xauusd, close=2005.0)>"
        assert repr(gp) == expected

    def test_unique_constraint_exists(self):
        constraints = list(GoldPrice.__table__.constraints)
        assert any(
            getattr(constraint, "name", "") == "uq_gold_prices_source_date"
            for constraint in constraints
        )


class TestTechnicalIndicator:
    """TechnicalIndicator 模型测试"""

    def test_creation(self):
        """测试模型实例化"""
        ti = TechnicalIndicator(
            date=datetime(2024, 1, 1),
            source="xauusd",
            ma5=2010.0,
            ma10=2005.0,
            ma20=2000.0,
            rsi14=55.5,
            macd_line=10.0,
            macd_signal=8.0,
            macd_hist=2.0,
            adx=25.0,
            supertrend_dir=1,
        )
        assert ti.source == "xauusd"
        assert ti.ma5 == 2010.0
        assert ti.rsi14 == 55.5
        assert ti.supertrend_dir == 1

    def test_repr(self):
        """测试 __repr__ 输出"""
        ti = TechnicalIndicator(
            date=datetime(2024, 1, 1),
            source="xauusd",
            rsi14=55.5,
        )
        expected = "<TechnicalIndicator(date=2024-01-01 00:00:00, source=xauusd, rsi=55.5)>"
        assert repr(ti) == expected

    def test_unique_constraint_exists(self):
        constraints = list(TechnicalIndicator.__table__.constraints)
        assert any(
            getattr(constraint, "name", "") == "uq_technical_indicators_source_date"
            for constraint in constraints
        )


class TestTradeSignal:
    """TradeSignal 模型测试"""

    def test_creation(self):
        """测试模型实例化"""
        ts = TradeSignal(
            date=datetime(2024, 1, 1),
            source="xauusd",
            signal_type="strong_buy",
            score=85.0,
            confidence=0.8,
            reasons=["RSI超卖", "布林带触及下轨"],
            stop_loss=1950.0,
            take_profit=2100.0,
        )
        assert ts.signal_type == "strong_buy"
        assert ts.score == 85.0
        assert ts.confidence == 0.8
        assert len(ts.reasons) == 2
        assert ts.stop_loss == 1950.0
        assert ts.take_profit == 2100.0

    def test_repr(self):
        """测试 __repr__ 输出"""
        ts = TradeSignal(
            date=datetime(2024, 1, 1),
            source="xauusd",
            signal_type="buy",
            score=50.0,
            confidence=0.6,
        )
        expected = "<TradeSignal(date=2024-01-01 00:00:00, signal=buy, score=50.0)>"
        assert repr(ts) == expected

    def test_unique_constraint_exists(self):
        constraints = list(TradeSignal.__table__.constraints)
        assert any(
            getattr(constraint, "name", "") == "uq_trade_signals_source_date"
            for constraint in constraints
        )


class TestPrediction:
    """Prediction 模型测试"""

    def test_creation(self):
        """测试模型实例化"""
        pred = Prediction(
            prediction_date=datetime(2024, 1, 1),
            target_date=datetime(2024, 1, 10),
            source="prophet",
            predicted_price=2100.0,
            lower_bound=2050.0,
            upper_bound=2150.0,
            trend_direction="up",
            trend_value=100.0,
        )
        assert pred.source == "prophet"
        assert pred.predicted_price == 2100.0
        assert pred.trend_direction == "up"

    def test_repr(self):
        """测试 __repr__ 输出"""
        pred = Prediction(
            prediction_date=datetime(2024, 1, 1),
            target_date=datetime(2024, 1, 10),
            source="prophet",
            predicted_price=2100.0,
        )
        expected = "<Prediction(target=2024-01-10 00:00:00, price=2100.0)>"
        assert repr(pred) == expected


class TestDebateResult:
    """DebateResult 模型测试"""

    def test_creation(self):
        """测试模型实例化"""
        dr = DebateResult(
            date=datetime(2024, 1, 1),
            verdict="bullish",
            verdict_confidence=75,
            verdict_data_quality_score=80,
            tokens_used=5000,
        )
        assert dr.verdict == "bullish"
        assert dr.verdict_confidence == 75
        assert dr.tokens_used == 5000

    def test_repr(self):
        """测试 __repr__ 输出"""
        dr = DebateResult(
            date=datetime(2024, 1, 1),
            verdict="bullish",
        )
        expected = "<DebateResult(date=2024-01-01 00:00:00, verdict=bullish)>"
        assert repr(dr) == expected


class TestBacktestResult:
    """BacktestResult 模型测试"""

    def test_creation(self):
        """测试模型实例化"""
        br = BacktestResult(
            run_date=datetime(2024, 1, 1),
            strategy="ma_crossover",
            period="2y",
            initial_cash=100000.0,
            final_value=120000.0,
            total_return=20.0,
            max_drawdown=-15.0,
            sharpe_ratio=1.5,
            total_trades=50,
            winning_trades=30,
            win_rate=0.6,
        )
        assert br.strategy == "ma_crossover"
        assert br.initial_cash == 100000.0
        assert br.total_return == 20.0
        assert br.sharpe_ratio == 1.5
        assert br.win_rate == 0.6

    def test_repr(self):
        """测试 __repr__ 输出"""
        br = BacktestResult(
            run_date=datetime(2024, 1, 1),
            strategy="ma_crossover",
            initial_cash=100000.0,
            final_value=120000.0,
            total_return=20.0,
        )
        expected = "<BacktestResult(strategy=ma_crossover, return=20.0)>"
        assert repr(br) == expected


class TestMacroData:
    """MacroData 模型测试"""

    def test_creation(self):
        """测试模型实例化"""
        md = MacroData(
            date=datetime(2024, 1, 1),
            indicator="usd_index",
            value=104.5,
            source="yfinance",
        )
        assert md.indicator == "usd_index"
        assert md.value == 104.5
        assert md.source == "yfinance"

    def test_repr(self):
        """测试 __repr__ 输出"""
        md = MacroData(
            date=datetime(2024, 1, 1),
            indicator="usd_index",
            value=104.5,
            source="yfinance",
        )
        expected = "<MacroData(date=2024-01-01 00:00:00, indicator=usd_index, value=104.5)>"
        assert repr(md) == expected

    def test_unique_constraint_exists(self):
        constraints = list(MacroData.__table__.constraints)
        assert any(
            getattr(constraint, "name", "") == "uq_macro_data_source_indicator_date"
            for constraint in constraints
        )


class TestNewsArticle:
    """NewsArticle 模型测试"""

    def test_creation(self):
        """测试模型实例化"""
        na = NewsArticle(
            published_date=datetime(2024, 1, 1),
            title="金价突破历史新高",
            link="https://example.com/gold-news",
            source="google_news",
            sentiment_score=0.8,
            sentiment_label="bullish",
            bull_hits=["避险", "通胀"],
            bear_hits=["加息"],
        )
        assert "金价" in na.title
        assert na.sentiment_score == 0.8
        assert na.sentiment_label == "bullish"
        assert "避险" in na.bull_hits

    def test_title_truncation_in_repr(self):
        """测试 __repr__ 对长标题的截断"""
        na = NewsArticle(
            published_date=datetime(2024, 1, 1),
            title="这是一篇非常长的新闻标题" * 10,
            sentiment_label="bullish",
        )
        # __repr__ 截断标题到 ~50 字符
        assert len(na.title) > 50
        assert repr(na).startswith("<NewsArticle(title=")

    def test_repr(self):
        """测试 __repr__ 输出"""
        na = NewsArticle(
            published_date=datetime(2024, 1, 1),
            title="金价突破历史新高",
            sentiment_label="bullish",
        )
        assert repr(na) == "<NewsArticle(title=金价突破历史新高..., sentiment=bullish)>"

    def test_unique_constraint_exists(self):
        constraints = list(NewsArticle.__table__.constraints)
        assert any(
            getattr(constraint, "name", "") == "uq_news_articles_source_link"
            for constraint in constraints
        )


class TestSystemConfig:
    """SystemConfig 模型测试"""

    def test_creation(self):
        """测试模型实例化"""
        sc = SystemConfig(
            key="debate_llm_config",
            value={"model": "gpt-4", "temperature": 0.7},
            description="辩论 LLM 配置",
        )
        assert sc.key == "debate_llm_config"
        assert sc.value == {"model": "gpt-4", "temperature": 0.7}
        assert sc.description == "辩论 LLM 配置"

    def test_repr(self):
        """测试 __repr__ 输出"""
        sc = SystemConfig(
            key="debate_llm_config",
            value={"model": "gpt-4"},
        )
        expected = "<SystemConfig(key=debate_llm_config)>"
        assert repr(sc) == expected


class TestDataFetchRun:
    """DataFetchRun 模型测试"""

    def test_creation(self):
        started_at = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
        finished_at = datetime(2024, 1, 1, 10, 1, tzinfo=UTC)
        run = DataFetchRun(
            cache_key="gold_intl_1y",
            fetcher="fetch_gold_price",
            status="success",
            record_count=365,
            duration_ms=1234.5,
            started_at=started_at,
            finished_at=finished_at,
        )
        assert run.cache_key == "gold_intl_1y"
        assert run.fetcher == "fetch_gold_price"
        assert run.status == "success"
        assert run.record_count == 365

    def test_repr(self):
        run = DataFetchRun(
            cache_key="macro_yfinance_1y",
            fetcher="fetch_macro_yfinance",
            status="failure",
            record_count=0,
            duration_ms=50.0,
            started_at=datetime(2024, 1, 1, tzinfo=UTC),
            finished_at=datetime(2024, 1, 1, 0, 0, 1, tzinfo=UTC),
        )
        assert (
            repr(run)
            == "<DataFetchRun(cache_key=macro_yfinance_1y, status=failure, records=0)>"
        )


class TestHelperFunctions:
    """辅助函数测试"""

    def test_create_tables(self):
        """create_tables 委托给 Base.metadata.create_all"""
        engine = MagicMock()
        with patch("gold_agent.db.models.Base.metadata.create_all") as mock_create:
            create_tables(engine)
            mock_create.assert_called_once_with(engine)

    def test_get_table_stats(self):
        """get_table_stats 返回各表行数统计"""
        session = MagicMock()
        mock_query = MagicMock()
        session.query.return_value = mock_query
        # 每张表依次返回不同的行数
        mock_query.count.side_effect = [100, 200, 50, 10, 5, 20, 300, 150, 12]

        stats = get_table_stats(session)

        assert stats["gold_prices"] == 100
        assert stats["technical_indicators"] == 200
        assert stats["trade_signals"] == 50
        assert stats["predictions"] == 10
        assert stats["debate_results"] == 5
        assert stats["backtest_results"] == 20
        assert stats["macro_data"] == 300
        assert stats["news_articles"] == 150
        assert stats["data_fetch_runs"] == 12
        # SystemConfig 不在 get_table_stats 的统计范围内
        assert "system_config" not in stats

    def test_create_tables_uses_engine(self):
        """create_tables 使用传入的 engine"""
        engine = MagicMock()
        with patch("gold_agent.db.models.Base.metadata.create_all") as mock_create:
            create_tables(engine)
            mock_create.assert_called_once()
            # 验证传入的参数就是 engine
            args, _ = mock_create.call_args
            assert args[0] is engine

    def test_utcnow(self):
        """_utcnow 返回当前 UTC 时间（覆盖 line 12）"""
        from gold_agent.db.models import _utcnow
        now = _utcnow()
        assert now.tzinfo is not None
        assert now.tzinfo == UTC
        # Should be close to current time
        diff = abs((datetime.now(UTC) - now).total_seconds())
        assert diff < 10

    def test_get_table_stats_error(self):
        """get_table_stats 中查询异常时捕获错误（覆盖 lines 276-277）"""
        session = MagicMock()
        session.query.side_effect = Exception("DB connection error")

        stats = get_table_stats(session)

        # All tables should have error messages
        for name in ["gold_prices", "technical_indicators", "trade_signals",
                      "predictions", "debate_results", "backtest_results",
                      "macro_data", "news_articles", "data_fetch_runs"]:
            assert name in stats
            assert "Error" in str(stats[name])
