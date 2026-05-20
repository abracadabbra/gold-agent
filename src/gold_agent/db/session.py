"""数据库会话管理 — SQLAlchemy sync engine + session"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from gold_agent.config import settings

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
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
