"""Migration contract tests."""

from pathlib import Path


def test_data_quality_migration_contains_phase5_contracts():
    migration = Path("alembic/versions/002_data_quality_persistence_contracts.py")
    source = migration.read_text(encoding="utf-8")

    assert 'revision: str = "002"' in source
    assert 'down_revision: str | None = "001"' in source
    assert "data_fetch_runs" in source
    assert "idx_data_fetch_runs_key_started" in source

    for constraint in [
        "uq_gold_prices_source_date",
        "uq_technical_indicators_source_date",
        "uq_trade_signals_source_date",
        "uq_macro_data_source_indicator_date",
        "uq_news_articles_source_link",
    ]:
        assert constraint in source


def test_data_quality_migration_dedupes_before_unique_constraints():
    migration = Path("alembic/versions/002_data_quality_persistence_contracts.py")
    source = migration.read_text(encoding="utf-8")

    dedupe_pos = source.index('_dedupe("gold_prices"')
    constraint_pos = source.index('"uq_gold_prices_source_date"')

    assert dedupe_pos < constraint_pos
    assert "ROW_NUMBER() OVER" in source
