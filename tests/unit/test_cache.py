"""数据缓存层单元测试 — DataCache 三级缓存"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from gold_agent.config import settings
from gold_agent.data.cache import DataCache


@pytest.fixture
def fresh_cache(tmp_path):
    """创建使用临时目录的 DataCache 实例"""
    with patch.object(settings, "parquet_dir", tmp_path / "parquet"):
        cache = DataCache()
        cache._redis = None  # 确保不依赖全局状态
        return cache


class TestDataCacheInit:
    """测试 DataCache 初始化"""

    def test_data_dir_created(self, tmp_path):
        """初始化时创建 parquet 目录"""
        parquet_dir = tmp_path / "custom_parquet"
        assert not parquet_dir.exists()

        with patch.object(settings, "parquet_dir", parquet_dir):
            cache = DataCache()

            assert parquet_dir.exists()
            assert cache.data_dir == parquet_dir

    def test_default_attributes(self, fresh_cache):
        """默认属性值正确"""
        assert fresh_cache.cache_ttl == 300
        assert fresh_cache._redis is None
        assert fresh_cache.redis_url == settings.redis_url


class TestDataCacheRedis:
    """测试 Redis 缓存操作"""

    def test_redis_property_lazy_connection(self, fresh_cache):
        """redis 属性应延迟连接"""
        with patch("redis.from_url") as mock_from_url:
            mock_redis = MagicMock()
            mock_from_url.return_value = mock_redis

            r = fresh_cache.redis

            assert r is not None
            mock_from_url.assert_called_once_with(
                settings.redis_url, decode_responses=True
            )
            mock_redis.ping.assert_called_once()

    def test_redis_property_connection_failure(self, fresh_cache):
        """连接失败时 redis 属性应返回 None"""
        with patch("redis.from_url") as mock_from_url:
            mock_from_url.side_effect = ConnectionError("Redis unavailable")

            r = fresh_cache.redis

            assert r is None
            # 失败后应缓存为 False，避免重试
            assert fresh_cache._redis is False

    def test_redis_property_cached(self, fresh_cache):
        """redis 属性应缓存已连接的实例"""
        mock_redis = MagicMock()
        fresh_cache._redis = mock_redis

        r = fresh_cache.redis

        assert r is mock_redis

    def test_redis_property_cached_false(self, fresh_cache):
        """_redis 为 False 时返回 None"""
        fresh_cache._redis = False

        r = fresh_cache.redis

        assert r is None

    def test_set_redis(self, fresh_cache):
        """设置 Redis 缓存"""
        fresh_cache._redis = MagicMock()

        df = pd.DataFrame({"close": [2000.0]})
        result = fresh_cache.set_redis("test_key", df)

        assert result is True
        rkey = "gold_agent:test_key"
        fresh_cache._redis.setex.assert_called_once()
        args, _ = fresh_cache._redis.setex.call_args
        assert args[0] == rkey
        assert args[1] == 300  # TTL

    def test_set_redis_empty_df(self, fresh_cache):
        """空 DataFrame 不应写入 Redis"""
        fresh_cache._redis = MagicMock()

        result = fresh_cache.set_redis("test_key", pd.DataFrame())

        assert result is False
        fresh_cache._redis.setex.assert_not_called()

    def test_set_redis_no_redis(self, fresh_cache):
        """Redis 不可用时 set_redis 返回 False"""
        fresh_cache._redis = False

        result = fresh_cache.set_redis("test_key", pd.DataFrame({"a": [1]}))

        assert result is False

    def test_get_redis_hit(self, fresh_cache):
        """get_redis 命中时返回 DataFrame"""
        fresh_cache._redis = MagicMock()
        fake_json = json.dumps([{"date": "2024-01-01", "close": 2000.0}])
        fresh_cache._redis.get.return_value = fake_json

        result = fresh_cache.get_redis("test_key")

        assert result is not None
        assert not result.empty
        assert result["close"].iloc[0] == 2000.0

    def test_get_redis_miss(self, fresh_cache):
        """get_redis 未命中时返回 None"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.get.return_value = None

        result = fresh_cache.get_redis("test_key")

        assert result is None

    def test_get_redis_no_redis(self, fresh_cache):
        """Redis 不可用时 get_redis 返回 None"""
        fresh_cache._redis = False

        result = fresh_cache.get_redis("test_key")

        assert result is None


class TestDataCacheParquet:
    """测试 Parquet 持久化"""

    def test_save_parquet_with_date(self, fresh_cache):
        """含 date 列的 DataFrame 按月分区保存"""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "close": [2000.0, 2010.0, 2005.0],
        })

        saved_path = fresh_cache.save_parquet("test_key", df)

        assert saved_path == fresh_cache.data_dir / "test_key"
        parquet_files = list((fresh_cache.data_dir / "test_key").glob("*.parquet"))
        assert len(parquet_files) == 1  # 所有数据在同一月
        assert "2024-01.parquet" in str(parquet_files[0])

    def test_save_parquet_without_date(self, fresh_cache):
        """无 date 列的 DataFrame 直接保存"""
        df = pd.DataFrame({"close": [2000.0, 2010.0]})

        saved_path = fresh_cache.save_parquet("test_key", df)

        assert saved_path == fresh_cache.data_dir / "test_key"
        parquet_files = list((fresh_cache.data_dir / "test_key").glob("*.parquet"))
        assert len(parquet_files) == 1

    def test_save_parquet_empty(self, fresh_cache):
        """空 DataFrame 跳过保存"""
        result = fresh_cache.save_parquet("test_key", pd.DataFrame())
        assert result == Path()
        assert not (fresh_cache.data_dir / "test_key").exists()

    def test_load_parquet_returns_data(self, fresh_cache):
        """保存后可以加载回相同数据"""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "close": [2000.0, 2010.0, 2005.0],
        })
        fresh_cache.save_parquet("test_key", df)

        loaded = fresh_cache.load_parquet("test_key")

        assert not loaded.empty
        assert len(loaded) == 3
        assert loaded["close"].iloc[0] == 2000.0
        assert "date" in loaded.columns

    def test_load_parquet_no_files(self, fresh_cache):
        """无缓存文件时返回空 DataFrame"""
        result = fresh_cache.load_parquet("nonexistent_key")
        assert result.empty

    def test_load_parquet_respects_months(self, fresh_cache):
        """load_parquet 的 months 参数限制加载月份数"""
        df_jan = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "close": [2000.0] * 5,
        })
        df_feb = pd.DataFrame({
            "date": pd.date_range("2024-02-01", periods=5, freq="D"),
            "close": [2010.0] * 5,
        })
        fresh_cache.save_parquet("test_key", df_jan)
        fresh_cache.save_parquet("test_key", df_feb)

        loaded = fresh_cache.load_parquet("test_key", months=1)

        # 只应加载最近的 1 个月
        assert len(loaded) == 5


class TestDataCacheGet:
    """测试 DataCache.get() 三级缓存回退逻辑"""

    def test_redis_hit_no_fetch(self, fresh_cache):
        """Redis 命中时直接返回，不调用 fetch_fn"""
        fresh_cache._redis = MagicMock()
        fake_json = json.dumps([{"close": 2000.0}])
        fresh_cache._redis.get.return_value = fake_json

        def failing_fetch(**kwargs):
            raise AssertionError("不应调用 fetch_fn")

        result = fresh_cache.get("test_key", fetch_fn=failing_fetch)

        assert not result.empty
        assert result["close"].iloc[0] == 2000.0

    def test_parquet_hit_no_fetch(self, fresh_cache):
        """Redis 未命中但 Parquet 命中时，从 Parquet 加载"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.get.return_value = None  # Redis miss

        # 先保存一些数据到 Parquet
        orig_df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "close": [2000.0, 2010.0, 2005.0],
        })
        fresh_cache.save_parquet("test_key", orig_df)

        def failing_fetch(**kwargs):
            raise AssertionError("不应调用 fetch_fn")

        result = fresh_cache.get("test_key", fetch_fn=failing_fetch)

        assert not result.empty
        assert len(result) == 3
        assert result["close"].iloc[0] == 2000.0

    def test_fetch_fn_called(self, fresh_cache):
        """Redis 和 Parquet 都未命中时调用 fetch_fn"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.get.return_value = None  # Redis miss
        # 不保存 Parquet 数据 → Parquet miss

        fetch_called = False

        def mock_fetch(**kwargs):
            nonlocal fetch_called
            fetch_called = True
            return pd.DataFrame({
                "date": pd.date_range("2024-01-05", periods=2, freq="D"),
                "close": [2020.0, 2030.0],
            })

        result = fresh_cache.get("test_key", fetch_fn=mock_fetch)

        assert fetch_called
        assert not result.empty
        assert result["close"].iloc[0] == 2020.0

    def test_fetch_fn_kwargs_passed(self, fresh_cache):
        """fetch_fn 应接收到 kwargs 参数"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.get.return_value = None

        def mock_fetch(**kwargs):
            assert kwargs.get("period") == "1y"
            return pd.DataFrame({"close": [2000.0]})

        result = fresh_cache.get(
            "test_key", fetch_fn=mock_fetch, period="1y"
        )

        assert not result.empty

    def test_use_cache_false_skips_cache(self, fresh_cache):
        """use_cache=False 时直接调用 fetch_fn"""
        fresh_cache._redis = MagicMock()
        # 即使 Redis 有数据也不应该读

        fetch_called = False

        def mock_fetch(**kwargs):
            nonlocal fetch_called
            fetch_called = True
            return pd.DataFrame({"close": [3000.0]})

        result = fresh_cache.get(
            "test_key", fetch_fn=mock_fetch, use_cache=False
        )

        assert fetch_called
        assert result["close"].iloc[0] == 3000.0
        fresh_cache._redis.get.assert_not_called()
