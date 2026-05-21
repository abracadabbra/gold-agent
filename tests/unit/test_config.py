"""配置模块单元测试"""

from pathlib import Path

from gold_agent.config import Settings


def test_default_values(monkeypatch):
    """测试 Settings 默认值（独立于 .env 和环境变量）"""
    for key in [
        "OPENAI_API_KEY", "OPENAI_BASE_URL", "LLM_MODEL_BULL", "LLM_MODEL_BEAR",
        "LLM_MODEL_AUDITOR", "LLM_MODEL_ARBITRATOR", "FRED_API_KEY",
        "DATABASE_URL", "REDIS_URL", "DATA_CACHE_DIR", "PARQUET_DIR",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.openai_base_url == "https://api.openai.com/v1"
    assert s.llm_model_bull == "gpt-5.5"
    assert s.llm_model_bear == "claude-4.7-opus"
    assert s.llm_model_auditor == "gpt-5.5-mini"
    assert s.llm_model_arbitrator == "gpt-5.5"
    assert s.openai_api_key == ""
    assert s.fred_api_key == ""
    assert s.database_url == "sqlite:///./data/gold_agent.db"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.data_cache_dir == Path("./data/cache")
    assert s.parquet_dir == Path("./data/parquet")


def test_env_override(monkeypatch):
    """测试环境变量覆盖默认值"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("FRED_API_KEY", "fred-test-key")
    monkeypatch.setenv("LLM_MODEL_BULL", "gpt-4o")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test_db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6380/1")
    monkeypatch.setenv("DATA_CACHE_DIR", "/tmp/test_cache")
    monkeypatch.setenv("PARQUET_DIR", "/tmp/test_parquet")

    s = Settings()
    assert s.openai_api_key == "sk-test-key"
    assert s.fred_api_key == "fred-test-key"
    assert s.llm_model_bull == "gpt-4o"
    assert s.database_url == "postgresql+asyncpg://user:pass@localhost:5432/test_db"
    assert s.redis_url == "redis://localhost:6380/1"
    assert s.data_cache_dir == Path("/tmp/test_cache")
    assert s.parquet_dir == Path("/tmp/test_parquet")


def test_ensure_dirs_creates_paths(tmp_path):
    """ensure_dirs 创建配置的目录"""
    cache_dir = tmp_path / "cache"
    parquet_dir = tmp_path / "parquet"

    s = Settings(data_cache_dir=cache_dir, parquet_dir=parquet_dir)
    s.ensure_dirs()

    assert cache_dir.exists()
    assert cache_dir.is_dir()
    assert parquet_dir.exists()
    assert parquet_dir.is_dir()


def test_ensure_dirs_is_idempotent(tmp_path):
    """ensure_dirs 是幂等的（重复调用不报错）"""
    cache_dir = tmp_path / "data" / "cache"
    parquet_dir = tmp_path / "data" / "parquet"

    s = Settings(data_cache_dir=cache_dir, parquet_dir=parquet_dir)
    s.ensure_dirs()
    s.ensure_dirs()  # 第二次调用不应报错

    assert cache_dir.exists()
    assert parquet_dir.exists()


def test_ensure_dirs_existing_paths(tmp_path):
    """ensure_dirs 在目录已存在时也能正常工作"""
    existing = tmp_path / "existing"
    existing.mkdir(parents=True, exist_ok=True)

    s = Settings(data_cache_dir=existing, parquet_dir=existing / "parquet")
    s.ensure_dirs()

    assert existing.exists()
    assert (existing / "parquet").exists()


def test_path_types():
    """测试路径字段类型为 Path"""
    s = Settings()
    assert isinstance(s.data_cache_dir, Path)
    assert isinstance(s.parquet_dir, Path)
