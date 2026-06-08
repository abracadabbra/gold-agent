"""数据库会话管理 — SQLAlchemy sync engine + session"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from gold_agent.config import settings

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


_SQLITE_UPSERT_INDEXES: tuple[tuple[str, str, tuple[str, ...], str | None], ...] = (
    ("gold_prices", "uq_gold_prices_source_date", ("source", "date"), None),
    (
        "technical_indicators",
        "uq_technical_indicators_source_date",
        ("source", "date"),
        None,
    ),
    ("trade_signals", "uq_trade_signals_source_date", ("source", "date"), None),
    (
        "macro_data",
        "uq_macro_data_source_indicator_date",
        ("source", "indicator", "date"),
        None,
    ),
    (
        "news_articles",
        "uq_news_articles_source_link",
        ("source", "link"),
        "source IS NOT NULL AND link IS NOT NULL",
    ),
)


def _ensure_sqlite_upsert_indexes(bind: Engine) -> None:
    """Backfill SQLite unique indexes needed by ON CONFLICT upserts.

    ``Base.metadata.create_all`` creates missing tables, but it does not alter existing
    SQLite tables when a new unique constraint is added to the model. Local dev
    databases created before the upsert migration therefore need a lightweight
    compatibility pass at startup.
    """
    if bind.dialect.name != "sqlite":
        return

    with bind.begin() as conn:
        for table, index_name, columns, where in _SQLITE_UPSERT_INDEXES:
            partition = ", ".join(columns)
            filter_clause = f"WHERE {where}" if where else ""
            conn.execute(
                text(
                    f"""
                    DELETE FROM {table}
                    WHERE id IN (
                        SELECT id
                        FROM (
                            SELECT
                                id,
                                ROW_NUMBER() OVER (
                                    PARTITION BY {partition}
                                    ORDER BY id DESC
                                ) AS rn
                            FROM {table}
                            {filter_clause}
                        ) ranked
                        WHERE ranked.rn > 1
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS {index_name}
                    ON {table} ({partition})
                    """
                )
            )


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: 获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库: 创建所有表"""
    from gold_agent.db.models import Base
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_upsert_indexes(engine)
