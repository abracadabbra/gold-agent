"""初始迁移: 创建所有 9 张表

Revision ID: 001
Revises:
Create Date: 2026-05-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # gold_prices
    op.create_table(
        "gold_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_source_date", "gold_prices", ["source", "date"])
    op.create_index(op.f("ix_gold_prices_date"), "gold_prices", ["date"])

    # technical_indicators
    op.create_table(
        "technical_indicators",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("ma5", sa.Float(), nullable=True),
        sa.Column("ma10", sa.Float(), nullable=True),
        sa.Column("ma20", sa.Float(), nullable=True),
        sa.Column("ma60", sa.Float(), nullable=True),
        sa.Column("ema12", sa.Float(), nullable=True),
        sa.Column("ema26", sa.Float(), nullable=True),
        sa.Column("macd_line", sa.Float(), nullable=True),
        sa.Column("macd_signal", sa.Float(), nullable=True),
        sa.Column("macd_hist", sa.Float(), nullable=True),
        sa.Column("rsi14", sa.Float(), nullable=True),
        sa.Column("stoch_k", sa.Float(), nullable=True),
        sa.Column("stoch_d", sa.Float(), nullable=True),
        sa.Column("bb_upper", sa.Float(), nullable=True),
        sa.Column("bb_mid", sa.Float(), nullable=True),
        sa.Column("bb_lower", sa.Float(), nullable=True),
        sa.Column("atr14", sa.Float(), nullable=True),
        sa.Column("adx", sa.Float(), nullable=True),
        sa.Column("supertrend", sa.Float(), nullable=True),
        sa.Column("supertrend_dir", sa.Integer(), nullable=True),
        sa.Column("obv", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_indicator_source_date", "technical_indicators", ["source", "date"])
    op.create_index(op.f("ix_technical_indicators_date"), "technical_indicators", ["date"])

    # trade_signals
    op.create_table(
        "trade_signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("signal_type", sa.String(20), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasons", postgresql.JSON(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    sa.Index("ix_trade_signals_date", "date"),
    op.create_index(op.f("ix_trade_signals_date"), "trade_signals", ["date"])

    # predictions
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prediction_date", sa.DateTime(), nullable=False),
        sa.Column("target_date", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("predicted_price", sa.Float(), nullable=False),
        sa.Column("lower_bound", sa.Float(), nullable=True),
        sa.Column("upper_bound", sa.Float(), nullable=True),
        sa.Column("trend_direction", sa.String(10), nullable=True),
        sa.Column("trend_value", sa.Float(), nullable=True),
        sa.Column("changepoints", postgresql.JSON(), nullable=True),
        sa.Column("components", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_prediction_date", "predictions", ["prediction_date", "target_date"])
    op.create_index(op.f("ix_predictions_prediction_date"), "predictions", ["prediction_date"])

    # debate_results
    op.create_table(
        "debate_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("bull_stance", sa.String(20), nullable=True),
        sa.Column("bull_confidence", sa.Integer(), nullable=True),
        sa.Column("bull_arguments", postgresql.JSON(), nullable=True),
        sa.Column("bull_price_target", postgresql.JSON(), nullable=True),
        sa.Column("bull_key_risk", sa.Text(), nullable=True),
        sa.Column("bear_stance", sa.String(20), nullable=True),
        sa.Column("bear_confidence", sa.Integer(), nullable=True),
        sa.Column("bear_arguments", postgresql.JSON(), nullable=True),
        sa.Column("bear_price_target", postgresql.JSON(), nullable=True),
        sa.Column("bear_counter_to_bull", sa.Text(), nullable=True),
        sa.Column("bear_key_risk", sa.Text(), nullable=True),
        sa.Column("audit_bull_claims", postgresql.JSON(), nullable=True),
        sa.Column("audit_bear_claims", postgresql.JSON(), nullable=True),
        sa.Column("audit_missed_data", postgresql.JSON(), nullable=True),
        sa.Column("audit_overall_assessment", sa.Text(), nullable=True),
        sa.Column("verdict", sa.String(20), nullable=True),
        sa.Column("verdict_confidence", sa.Integer(), nullable=True),
        sa.Column("verdict_price_range", postgresql.JSON(), nullable=True),
        sa.Column("verdict_time_horizon", sa.String(10), nullable=True),
        sa.Column("verdict_key_reasons", postgresql.JSON(), nullable=True),
        sa.Column("verdict_risk_warnings", postgresql.JSON(), nullable=True),
        sa.Column("verdict_data_quality_score", sa.Integer(), nullable=True),
        sa.Column("verdict_quant_signal", sa.Text(), nullable=True),
        sa.Column("verdict_llm_signal", sa.Text(), nullable=True),
        sa.Column("verdict_final_advice", sa.Text(), nullable=True),
        sa.Column("context_data", postgresql.JSON(), nullable=True),
        sa.Column("raw_responses", postgresql.JSON(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_debate_results_date"), "debate_results", ["date"])

    # backtest_results
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_date", sa.DateTime(), nullable=False),
        sa.Column("strategy", sa.String(50), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("initial_cash", sa.Float(), nullable=False),
        sa.Column("final_value", sa.Float(), nullable=False),
        sa.Column("total_return", sa.Float(), nullable=False),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=True),
        sa.Column("winning_trades", sa.Integer(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("equity_curve", postgresql.JSON(), nullable=True),
        sa.Column("trade_log", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_backtest_results_run_date"), "backtest_results", ["run_date"])

    # macro_data
    op.create_table(
        "macro_data",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("indicator", sa.String(50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_macro_indicator_date", "macro_data", ["indicator", "date"])
    op.create_index(op.f("ix_macro_data_date"), "macro_data", ["date"])

    # news_articles
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("published_date", sa.DateTime(), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("link", sa.String(1000), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("sentiment_label", sa.String(20), nullable=True),
        sa.Column("bull_hits", postgresql.JSON(), nullable=True),
        sa.Column("bear_hits", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_news_articles_published_date"), "news_articles", ["published_date"])

    # system_config
    op.create_table(
        "system_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", postgresql.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("system_config")
    op.drop_table("news_articles")
    op.drop_table("macro_data")
    op.drop_table("backtest_results")
    op.drop_table("debate_results")
    op.drop_table("predictions")
    op.drop_table("trade_signals")
    op.drop_table("technical_indicators")
    op.drop_table("gold_prices")
