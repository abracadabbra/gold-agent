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
        cache._record_fetch_run = MagicMock()
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
        calls = fresh_cache._redis.setex.call_args_list
        assert len(calls) == 2
        data_args = calls[0].args
        meta_args = calls[1].args
        assert data_args[0] == "gold_agent:test_key"
        assert data_args[1] == 300  # TTL
        assert meta_args[0] == "gold_agent:test_key:meta"
        assert meta_args[1] == 300

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


class TestDataCacheStaleness:
    """测试 DataCache._is_stale 新鲜度检查"""

    def test_none_max_stale_never_stale(self, fresh_cache):
        """max_stale_days=None 时永远不认为过期"""
        old_df = pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=3, freq="D"),
            "close": [1000.0, 1010.0, 1005.0],
        })
        assert not fresh_cache._is_stale(old_df, None)

    def test_no_date_column_never_stale(self, fresh_cache):
        """无 date 列时不检查新鲜度"""
        df = pd.DataFrame({"close": [2000.0]})
        assert not fresh_cache._is_stale(df, 1)

    def test_stale_exceeds_days(self, fresh_cache):
        """超过 max_stale_days 的数据被视为过期"""
        old_df = pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=3, freq="D"),
            "close": [1000.0] * 3,
        })
        assert fresh_cache._is_stale(old_df, 0.1)  # 0.1 day ≈ 2.4h

    def test_fresh_data_not_stale(self, fresh_cache):
        """max_stale_days 范围内的数据不被视为过期"""
        import datetime
        today = datetime.date.today()
        fresh_df = pd.DataFrame({
            "date": pd.date_range(today, periods=3, freq="h"),
            "close": [2000.0, 2005.0, 2010.0],
        })
        assert not fresh_cache._is_stale(fresh_df, 1)

    def test_hours_precision(self, fresh_cache):
        """验证 0.1 天 ≈ 2.4 小时的精度"""
        import datetime
        now = datetime.datetime.now()
        # 数据来自 3 小时前 — 在 0.1 天(2.4h)边界之上
        three_hours_ago = now - datetime.timedelta(hours=3)
        df = pd.DataFrame({
            "date": pd.date_range(three_hours_ago, periods=1, freq="h"),
            "close": [2000.0],
        })
        assert fresh_cache._is_stale(df, 0.1)

        # 数据来自 1 小时前 — 在 0.1 天边界之内
        one_hour_ago = now - datetime.timedelta(hours=1)
        df2 = pd.DataFrame({
            "date": pd.date_range(one_hour_ago, periods=1, freq="h"),
            "close": [2000.0],
        })
        assert not fresh_cache._is_stale(df2, 0.1)

    def test_redis_stale_skips_to_parquet(self, fresh_cache):
        """Redis 数据过期时跳过，尝试 Parquet"""
        fresh_cache._redis = MagicMock()
        import datetime
        today = datetime.date.today()
        old_json = json.dumps([{"date": str(today - datetime.timedelta(days=10)), "close": 2000.0}])
        fresh_cache._redis.get.return_value = old_json

        parquet_called = False
        orig_load = fresh_cache.load_parquet

        def tracking_load(key, months=12):
            nonlocal parquet_called
            parquet_called = True
            return orig_load(key, months=months)

        fresh_cache.load_parquet = tracking_load

        fetch_called = False
        def mock_fetch(**kwargs):
            nonlocal fetch_called
            fetch_called = True
            return pd.DataFrame({
                "date": pd.date_range(today - datetime.timedelta(days=1), periods=2, freq="D"),
                "close": [2020.0, 2030.0],
            })

        fresh_cache.get("test_key", fetch_fn=mock_fetch, max_stale_days=1)
        assert fetch_called  # Redis stale + Parquet empty → fetch

    def test_redis_fresh_returns_directly(self, fresh_cache):
        """Redis 数据新鲜时直接返回，不调 fetch_fn"""
        fresh_cache._redis = MagicMock()
        import datetime
        today = datetime.date.today()
        fresh_json = json.dumps([{"date": str(today), "close": 2000.0}])
        fresh_cache._redis.get.return_value = fresh_json

        def failing_fetch(**kwargs):
            raise AssertionError("不应调用 fetch_fn")

        result = fresh_cache.get("test_key", fetch_fn=failing_fetch, max_stale_days=1)
        assert not result.empty
        assert result["close"].iloc[0] == 2000.0


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

    def test_get_passes_months_to_load_parquet(self, fresh_cache):
        """DataCache.get 应将 months 参数传给 Parquet 读取层"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.get.return_value = None
        mock_loaded = pd.DataFrame({"close": [2000.0]})

        with patch.object(fresh_cache, "load_parquet", return_value=mock_loaded) as mock_load:
            result = fresh_cache.get("test_key", fetch_fn=MagicMock(), months=24)

        mock_load.assert_called_once_with("test_key", months=24)
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
        fresh_cache._record_fetch_run.assert_called_once()

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

    def test_get_with_meta_redis_hit(self, fresh_cache):
        """get_with_meta 在 Redis 命中时返回 cache metadata"""
        fresh_cache._redis = MagicMock()
        fresh_json = json.dumps([{"date": "2024-01-01", "close": 2000.0}])
        fresh_cache._redis.get.side_effect = [
            fresh_json,
            "2024-01-01T08:30:00+00:00",
        ]

        df, meta = fresh_cache.get_with_meta(
            "test_key",
            fetch_fn=MagicMock(),
            max_stale_days=9999,
            expected_frequency="daily",
        )

        assert not df.empty
        assert meta["source_status"] == "cache"
        assert meta["fetched_at"] == "2024-01-01T08:30:00+00:00"
        assert meta["cached_at"] == "2024-01-01T08:30:00+00:00"
        assert meta["row_count"] == 1
        assert meta["expected_frequency"] == "daily"

    def test_get_with_meta_fetch_path(self, fresh_cache):
        """get_with_meta 在缓存未命中时返回 live metadata"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.get.return_value = None

        def mock_fetch(**kwargs):
            return pd.DataFrame({
                "date": pd.date_range("2024-01-05", periods=2, freq="D"),
                "close": [2020.0, 2030.0],
            })

        df, meta = fresh_cache.get_with_meta(
            "test_key",
            fetch_fn=mock_fetch,
            max_stale_days=9999,
            expected_frequency="daily",
        )

        assert not df.empty
        assert meta["source_status"] == "live"
        assert meta["cached_at"] is None
        assert meta["row_count"] == 2
        assert meta["quality_score"] == 100
        fresh_cache._record_fetch_run.assert_called_once()
        assert fresh_cache._record_fetch_run.call_args.kwargs["status"] == "success"

    def test_get_with_meta_empty_fetch(self, fresh_cache):
        """get_with_meta 在 fetch 返回空数据时标记 unavailable"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.get.return_value = None

        df, meta = fresh_cache.get_with_meta(
            "test_key",
            fetch_fn=lambda **kwargs: pd.DataFrame(),
            expected_frequency="daily",
        )

        assert df.empty
        assert meta["source_status"] == "unavailable"
        assert meta["cached_at"] is None
        assert meta["row_count"] == 0
        fresh_cache._record_fetch_run.assert_called_once()
        assert fresh_cache._record_fetch_run.call_args.kwargs["status"] == "empty"

    def test_get_with_meta_parquet_hit_uses_file_mtime(self, fresh_cache):
        """Parquet 命中时返回近似缓存写入时间。"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.get.return_value = None

        df_source = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=2, freq="D"),
            "close": [2000.0, 2010.0],
        })
        fresh_cache.save_parquet("test_key", df_source)

        parquet_file = next((fresh_cache.data_dir / "test_key").glob("*.parquet"))
        ts = pd.Timestamp("2024-02-01T08:30:00+00:00").timestamp()
        parquet_file.touch()
        import os
        os.utime(parquet_file, (ts, ts))

        df, meta = fresh_cache.get_with_meta(
            "test_key",
            fetch_fn=MagicMock(),
            max_stale_days=9999,
            expected_frequency="daily",
        )

        assert not df.empty
        assert meta["source_status"] == "cache"
        assert meta["cached_at"] == "2024-02-01T08:30:00+00:00"

    # =============================================================
    # Edge case: Redis 反序列化失败
    # =============================================================

    def test_get_redis_deserialize_fail(self, fresh_cache):
        """get_redis 在 JSON 反序列化失败时应返回 None"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.get.return_value = "invalid json{{{"

        result = fresh_cache.get_redis("test_key")

        assert result is None

    # =============================================================
    # Edge case: Redis 写入失败
    # =============================================================

    def test_set_redis_write_failure(self, fresh_cache):
        """set_redis 在 Redis 写入异常时应返回 False"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.setex.side_effect = ConnectionError("Redis write failed")

        df = pd.DataFrame({"close": [2000.0]})
        result = fresh_cache.set_redis("test_key", df)

        assert result is False
        fresh_cache._redis.setex.assert_called_once()

    def test_set_redis_with_date_column(self, fresh_cache):
        """set_redis 含 date 列时应转为字符串"""
        fresh_cache._redis = MagicMock()

        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=2, freq="D"),
            "close": [2000.0, 2010.0],
        })
        result = fresh_cache.set_redis("test_key", df, ttl=600)

        assert result is True
        data_args = fresh_cache._redis.setex.call_args_list[0].args
        meta_args = fresh_cache._redis.setex.call_args_list[1].args
        assert data_args[1] == 600  # Custom TTL
        assert meta_args[1] == 600
        data = json.loads(data_args[2])
        assert data[0]["date"] == "2024-01-01"  # 日期已转为字符串

    # =============================================================
    # Edge case: load_parquet TypeError on drop_duplicates
    # =============================================================

    def test_load_parquet_type_error_drop_duplicates(self, fresh_cache):
        """load_parquet 在 drop_duplicates 遇到不可哈希列时应降级"""
        # 保存两个月的数据产生两个 parquet 文件，让 glob 能匹配到多个
        df_jan = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "close": [1.0, 2.0, 3.0],
        })
        df_feb = pd.DataFrame({
            "date": pd.date_range("2024-02-01", periods=3, freq="D"),
            "close": [4.0, 5.0, 6.0],
        })
        fresh_cache.save_parquet("test_key", df_jan)
        fresh_cache.save_parquet("test_key", df_feb)

        # 模拟读取含 list 列的 DataFrame，导致 drop_duplicates 抛出 TypeError
        with patch("pandas.read_parquet") as mock_read:
            mock_read.side_effect = [
                pd.DataFrame({
                    "nested": [[1]],
                    "date": [pd.Timestamp("2024-01-01")],
                    "close": [1.0],
                }),
                pd.DataFrame({
                    "nested": [[2]],
                    "date": [pd.Timestamp("2024-01-02")],
                    "close": [2.0],
                }),
            ]
            result = fresh_cache.load_parquet("test_key")

        assert not result.empty
        assert len(result) == 2  # 合并成功但未去重

    # =============================================================
    # Edge case: _is_stale 最新日期为 NaT
    # =============================================================

    def test_is_stale_nan_latest_date(self, fresh_cache):
        """_is_stale 在最新日期为 NaT 时应返回 False"""
        df = pd.DataFrame({
            "date": pd.Series([pd.NaT, pd.NaT]),
            "close": [1.0, 2.0],
        })
        assert not fresh_cache._is_stale(df, 1)

    # =============================================================
    # Edge case: Parquet 数据过期
    # =============================================================

    def test_parquet_stale_calls_fetch(self, fresh_cache):
        """Parquet 数据过期时应调用 fetch_fn 获取新数据"""
        fresh_cache._redis = False  # Redis 不可用
        import datetime

        old_date = datetime.datetime.now() - datetime.timedelta(days=30)
        stale_df = pd.DataFrame({
            "date": pd.date_range(old_date, periods=3, freq="D"),
            "close": [1000.0, 1010.0, 1005.0],
        })
        fresh_cache.save_parquet("stale_key", stale_df)

        fetch_called = False

        def mock_fetch(**kwargs):
            nonlocal fetch_called
            fetch_called = True
            return pd.DataFrame({
                "date": pd.date_range(
                    datetime.datetime.now(), periods=2, freq="D"
                ),
                "close": [2000.0, 2010.0],
            })

        result = fresh_cache.get(
            "stale_key", fetch_fn=mock_fetch, max_stale_days=1
        )

        assert fetch_called
        assert result["close"].iloc[0] == 2000.0

    # =============================================================
    # Edge case: db_save_fn 异常
    # =============================================================

    def test_db_save_fn_failure(self, fresh_cache):
        """db_save_fn 异常应被捕获，不阻止正常流程"""
        fresh_cache._redis = False  # Redis 不可用

        fetch_called = False

        def mock_fetch(**kwargs):
            nonlocal fetch_called
            fetch_called = True
            return pd.DataFrame({
                "date": pd.date_range("2024-06-01", periods=2, freq="D"),
                "close": [2000.0, 2010.0],
            })

        def failing_db_save(records):
            raise ValueError("DB save error")

        # 不应抛出异常
        result = fresh_cache.get(
            "test_key", fetch_fn=mock_fetch, db_save_fn=failing_db_save
        )

        assert fetch_called
        assert not result.empty
        fresh_cache._record_fetch_run.assert_called_once()
        assert fresh_cache._record_fetch_run.call_args.kwargs["status"] == "persist_failure"
        assert fresh_cache._record_fetch_run.call_args.kwargs["record_count"] == 2
        assert "DB save error" in fresh_cache._record_fetch_run.call_args.kwargs["error_message"]

    def test_db_save_fn_success(self, fresh_cache):
        """db_save_fn 正常调用"""
        fresh_cache._redis = False
        db_save_called = False

        def mock_fetch(**kwargs):
            return pd.DataFrame({
                "date": pd.date_range("2024-06-01", periods=2, freq="D"),
                "close": [2000.0, 2010.0],
            })

        def success_db_save(records):
            nonlocal db_save_called
            db_save_called = True
            assert len(records) == 2

        result = fresh_cache.get(
            "test_key", fetch_fn=mock_fetch, db_save_fn=success_db_save
        )

        assert db_save_called
        assert not result.empty

    def test_cache_hit_does_not_record_fetch_run(self, fresh_cache):
        """缓存命中时不记录数据采集运行状态"""
        fresh_cache._redis = MagicMock()
        fresh_cache._redis.get.return_value = json.dumps([{"close": 2000.0}])

        result = fresh_cache.get("test_key", fetch_fn=MagicMock())

        assert not result.empty
        fresh_cache._record_fetch_run.assert_not_called()

    def test_record_fetch_run_success(self, fresh_cache):
        """真实 fetch 成功时记录任务状态"""
        fresh_cache._record_fetch_run = DataCache._record_fetch_run.__get__(fresh_cache, DataCache)
        mock_session = MagicMock()

        with patch("gold_agent.data.cache.SessionLocal", return_value=mock_session), patch(
            "gold_agent.data.cache.save_data_fetch_run"
        ) as mock_save:
            df = fresh_cache.get(
                "test_key",
                fetch_fn=lambda **kwargs: pd.DataFrame({"close": [2000.0, 2010.0]}),
                use_cache=False,
            )

        assert len(df) == 2
        mock_save.assert_called_once()
        run = mock_save.call_args.args[1]
        assert run["cache_key"] == "test_key"
        assert run["status"] == "success"
        assert run["record_count"] == 2
        assert run["fetcher"] == "<lambda>"
        assert run["duration_ms"] >= 0
        mock_session.close.assert_called_once()

    def test_record_fetch_run_failure(self, fresh_cache):
        """真实 fetch 失败时记录失败状态并继续抛异常"""
        fresh_cache._record_fetch_run = DataCache._record_fetch_run.__get__(fresh_cache, DataCache)
        mock_session = MagicMock()

        with patch("gold_agent.data.cache.SessionLocal", return_value=mock_session), patch(
            "gold_agent.data.cache.save_data_fetch_run"
        ) as mock_save:
            with pytest.raises(RuntimeError, match="boom"):
                fresh_cache.get(
                    "test_key",
                    fetch_fn=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
                    use_cache=False,
                )

        mock_save.assert_called_once()
        run = mock_save.call_args.args[1]
        assert run["cache_key"] == "test_key"
        assert run["status"] == "failure"
        assert run["record_count"] == 0
        assert run["error_message"] == "boom"
        mock_session.close.assert_called_once()
