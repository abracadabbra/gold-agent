"""数据库会话单元测试 — session.py"""

from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


class TestEngine:
    """测试 engine 创建"""

    def test_engine_created_with_sqlite_url(self):
        from gold_agent.db.session import engine
        assert str(engine.url).startswith("sqlite")


class TestSessionLocal:
    """测试 SessionLocal"""

    def test_session_local_is_callable(self):
        from gold_agent.db.session import SessionLocal
        assert callable(SessionLocal)

    def test_session_local_returns_session(self):
        from gold_agent.db.session import SessionLocal
        db = SessionLocal()
        try:
            assert isinstance(db, Session)
        finally:
            db.close()


class TestGetSession:
    """测试 get_session"""

    def test_yields_session_and_closes(self):
        from gold_agent.db.session import get_session
        gen = get_session()
        session = next(gen)
        assert isinstance(session, Session)
        with patch.object(session, "close") as mock_close:
            try:
                next(gen)
            except StopIteration:
                pass
            mock_close.assert_called_once()


class TestInitDB:
    """测试 init_db"""

    def test_calls_create_all(self):
        with patch("gold_agent.db.models.Base.metadata.create_all") as mock_create:
            with patch("gold_agent.db.session._ensure_sqlite_upsert_indexes") as mock_ensure:
                from gold_agent.db.session import init_db
                init_db()
                mock_create.assert_called_once()
                mock_ensure.assert_called_once()

    def test_sqlite_upsert_indexes_backfill_old_schema(self):
        from gold_agent.db.session import _ensure_sqlite_upsert_indexes

        db_engine = create_engine("sqlite:///:memory:")
        with db_engine.begin() as conn:
            conn.execute(text(
                """
                CREATE TABLE macro_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATETIME NOT NULL,
                    indicator VARCHAR(50) NOT NULL,
                    value FLOAT NOT NULL,
                    source VARCHAR(20) NOT NULL
                )
                """
            ))
            conn.execute(text(
                """
                INSERT INTO macro_data (date, indicator, value, source)
                VALUES
                    ('2024-01-01', 'tips_yield', 1.1, 'fred'),
                    ('2024-01-01', 'tips_yield', 1.2, 'fred')
                """
            ))

            for table in [
                "gold_prices",
                "technical_indicators",
                "trade_signals",
                "news_articles",
            ]:
                conn.execute(text(
                    f"""
                    CREATE TABLE {table} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date DATETIME,
                        source VARCHAR(50),
                        link VARCHAR(1000)
                    )
                    """
                ))

        _ensure_sqlite_upsert_indexes(db_engine)

        with db_engine.begin() as conn:
            rows = conn.execute(text("SELECT id, value FROM macro_data")).all()
            indexes = conn.execute(text("PRAGMA index_list('macro_data')")).mappings().all()

        assert rows == [(2, 1.2)]
        assert any(
            row["name"] == "uq_macro_data_source_indicator_date" and row["unique"] == 1
            for row in indexes
        )

        with db_engine.begin() as conn:
            conn.execute(text(
                """
                INSERT INTO macro_data (date, indicator, value, source)
                VALUES ('2024-01-01', 'tips_yield', 1.3, 'fred')
                ON CONFLICT(source, indicator, date)
                DO UPDATE SET value = excluded.value
                """
            ))
            value = conn.execute(text("SELECT value FROM macro_data")).scalar_one()

        assert value == 1.3
