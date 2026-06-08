"""FastAPI 主入口单元测试 — 根路由 /health /stats"""

from pathlib import Path

from fastapi.testclient import TestClient

from gold_agent.main import _count_parquet_files, _format_duration, app, settings

client = TestClient(app)


class TestRoot:
    """根路由测试"""

    def test_root_returns_info(self):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "GoldAgent"
        assert "docs" in data
        assert "endpoints" in data


class TestHealth:
    """健康检查端点"""

    def test_health_returns_status(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert "services" in data
        assert "websocket" in data
        assert "config" in data


class TestStats:
    """系统统计端点"""

    def test_stats_returns_expected_structure(self):
        resp = client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "websocket" in data
        assert "system" in data
        assert "cache" in data
        assert "fetch_runs" in data
        assert data["system"]["version"] == "0.1.0"
        assert "uptime" in data["system"]
        assert "recent" in data["fetch_runs"]
        assert "summary" in data["fetch_runs"]
        assert data["fetch_runs"]["filters"]["limit"] == 12

    def test_cache_stats(self):
        resp = client.get("/stats")
        data = resp.json()
        assert isinstance(data["cache"], dict)
        assert "gold_intl_1y" in data["cache"]
        assert "gold_intl_1mo" in data["cache"]
        assert "macro_yfinance_1y" in data["cache"]


class TestFormatDuration:
    """_format_duration 辅助函数"""

    def test_seconds_only(self):
        assert _format_duration(45) == "0h 0m 45s"

    def test_minutes(self):
        assert _format_duration(3661) == "1h 1m 1s"

    def test_days(self):
        assert _format_duration(90000) == "1d 1h 0m"

    def test_exact_day(self):
        assert _format_duration(86400) == "1d 0h 0m"

    def test_zero(self):
        assert _format_duration(0) == "0h 0m 0s"


class TestCountParquetFiles:
    """_count_parquet_files 辅助函数"""

    def test_nonexistent_dir_returns_zero(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            original = settings.parquet_dir
            settings.parquet_dir = Path(tmp)
            try:
                assert _count_parquet_files("nonexistent") == 0
            finally:
                settings.parquet_dir = original

    def test_empty_dir_returns_zero(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            original = settings.parquet_dir
            settings.parquet_dir = Path(tmp)
            try:
                (Path(tmp) / "test_key").mkdir()
                assert _count_parquet_files("test_key") == 0
            finally:
                settings.parquet_dir = original

    def test_counts_parquet_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            original = settings.parquet_dir
            settings.parquet_dir = Path(tmp)
            try:
                subdir = Path(tmp) / "gold_intl_1y"
                subdir.mkdir()
                (subdir / "2024-01.parquet").touch()
                (subdir / "2024-02.parquet").touch()
                (subdir / "README.md").touch()
                assert _count_parquet_files("gold_intl_1y") == 2
            finally:
                settings.parquet_dir = original
