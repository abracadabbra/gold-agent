"""配置管理 — 从 .env 和环境变量加载所有配置"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ──
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model_bull: str = "gpt-5.5"
    llm_model_bear: str = "claude-4.7-opus"
    llm_model_auditor: str = "gpt-5.5-mini"
    llm_model_arbitrator: str = "gpt-5.5"

    # ── FRED ──
    fred_api_key: str = ""

    # ── 数据库 ──
    database_url: str = "sqlite:///./data/gold_agent.db"
    redis_url: str = "redis://localhost:6379/0"

    # ── 缓存路径 ──
    data_cache_dir: Path = Path("./data/cache")
    parquet_dir: Path = Path("./data/parquet")

    def ensure_dirs(self):
        """创建必要的本地目录"""
        self.data_cache_dir.mkdir(parents=True, exist_ok=True)
        self.parquet_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
