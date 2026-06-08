"""数据缓存层 — 本地 Parquet + 可选 Redis"""

import glob
import json
import time
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd
import logging
logger = logging.getLogger(__name__)

from gold_agent.config import settings
from gold_agent.data.quality import dataframe_meta
from gold_agent.db.repository import save_data_fetch_run
from gold_agent.db.session import SessionLocal


class DataCache:
    """
    两级缓存: 本地 Parquet (持久化) + Redis (热数据)

    - Parquet: 按年月分区存储历史数据，避免重复拉取
    - Redis: 实时数据缓存，TTL 过期自动刷新
    """

    def __init__(self):
        self.data_dir = settings.parquet_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.redis_url = settings.redis_url
        self.cache_ttl = 300  # 5 minutes default
        self._redis = None

    @property
    def redis(self):
        """延迟连接 Redis"""
        if self._redis is None:
            try:
                import redis
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("Redis 连接成功")
            except Exception as e:
                logger.warning(f"Redis 不可用 ({e})，仅使用本地缓存")
                self._redis = False  # 标记为不可用
        return self._redis if self._redis is not False else None

    # ---- Parquet 持久化 ----

    def _parquet_path(self, key: str, dt: pd.Timestamp | None = None) -> Path:
        """生成 Parquet 文件路径: data/cache/{key}/{YYYY-MM}.parquet"""
        if dt is None:
            dt = pd.Timestamp.now()
        partition = dt.strftime("%Y-%m")
        path = self.data_dir / key / f"{partition}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save_parquet(self, key: str, df: pd.DataFrame) -> Path:
        """保存 DataFrame 到 Parquet，按日期分区"""
        if df.empty:
            logger.warning(f"跳过空 DataFrame 保存: {key}")
            return Path()

        # 按月分组保存
        if "date" in df.columns:
            for period, group in df.groupby(df["date"].dt.to_period("M")):
                path = self._parquet_path(key, pd.Timestamp(str(period)))
                group.to_parquet(path, index=False, engine="pyarrow")
                logger.debug(f"保存 {key}/{period}: {len(group)} 行 -> {path}")
        else:
            path = self._parquet_path(key)
            df.to_parquet(path, index=False, engine="pyarrow")

        return self.data_dir / key

    def load_parquet(self, key: str, months: int = 12) -> pd.DataFrame:
        """加载最近 N 个月的 Parquet 数据"""
        pattern = self.data_dir / key / "*.parquet"
        files = sorted(glob.glob(str(pattern)))

        if not files:
            logger.info(f"本地缓存为空: {key}")
            return pd.DataFrame()

        # 只取最近 N 个月
        files = files[-months:]

        dfs = [pd.read_parquet(f) for f in files]
        try:
            df = pd.concat(dfs, ignore_index=True).drop_duplicates()
        except TypeError:
            df = pd.concat(dfs, ignore_index=True)
            logger.warning(f"{key}: 无法去重（含不可哈希列），跳过 drop_duplicates")

        if "date" in df.columns:
            df = df.sort_values("date").reset_index(drop=True)

        logger.info(f"从本地缓存加载 {key}: {len(df)} 行, {len(files)} 个分区")
        return df

    # ---- Redis 热缓存 ----

    def _redis_key(self, key: str) -> str:
        return f"gold_agent:{key}"

    def _redis_meta_key(self, key: str) -> str:
        return f"{self._redis_key(key)}:meta"

    def get_redis(self, key: str) -> pd.DataFrame | None:
        """从 Redis 读取缓存"""
        if not self.redis:
            return None

        rkey = self._redis_key(key)
        data = self.redis.get(rkey)
        if data is None:
            return None

        try:
            records = json.loads(data)
            df = pd.DataFrame(records)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
            logger.debug(f"Redis 缓存命中: {key} ({len(df)} 行)")
            return df
        except Exception as e:
            logger.warning(f"Redis 反序列化失败: {e}")
            return None

    def get_redis_cached_at(self, key: str) -> datetime | None:
        """读取 Redis 侧缓存写入时间。"""
        if not self.redis:
            return None

        rkey = self._redis_meta_key(key)
        value = self.redis.get(rkey)
        if value is None:
            return None

        try:
            ts = pd.to_datetime(value, errors="coerce")
            if pd.isna(ts):
                return None
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.tz_localize(UTC)
            else:
                ts = ts.tz_convert(UTC)
            return ts.to_pydatetime()
        except Exception:
            return None

    def set_redis(self, key: str, df: pd.DataFrame, ttl: int | None = None) -> bool:
        """写入 Redis 缓存"""
        if not self.redis or df.empty:
            return False

        rkey = self._redis_key(key)
        meta_key = self._redis_meta_key(key)
        try:
            data = df.copy()
            if "date" in data.columns:
                data["date"] = data["date"].astype(str)
            effective_ttl = ttl or self.cache_ttl
            cached_at = datetime.now(UTC).isoformat()
            self.redis.setex(rkey, effective_ttl, json.dumps(data.to_dict(orient="records")))
            self.redis.setex(meta_key, effective_ttl, cached_at)
            logger.debug(f"Redis 缓存写入: {key} (TTL={effective_ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"Redis 写入失败: {e}")
            return False

    def _parquet_cached_at(self, key: str, months: int = 12) -> datetime | None:
        """读取最近参与加载的 Parquet 分区最新 mtime，近似作为缓存写入时间。"""
        pattern = self.data_dir / key / "*.parquet"
        files = sorted(glob.glob(str(pattern)))
        if not files:
            return None
        files = files[-months:]
        latest_mtime = max(Path(f).stat().st_mtime for f in files)
        return datetime.fromtimestamp(latest_mtime, UTC)

    # ---- 新鲜度检查 ----

    @staticmethod
    def _is_stale(df: pd.DataFrame, max_stale_days: float | None) -> bool:
        """检查 DataFrame 数据是否超过最大允许过期（支持小数天，0.1 ≈ 2.4h）"""
        if max_stale_days is None or "date" not in df.columns:
            return False
        latest = df["date"].max()
        if pd.isna(latest):
            return False
        elapsed_hours = (pd.Timestamp.now() - latest).total_seconds() / 3600
        return elapsed_hours > max_stale_days * 24

    # ---- 统一接口 ----

    @staticmethod
    def _fetcher_name(fetch_fn) -> str:
        return getattr(fetch_fn, "__name__", fetch_fn.__class__.__name__)

    def _record_fetch_run(
        self,
        *,
        key: str,
        fetch_fn,
        status: str,
        record_count: int,
        started_at: datetime,
        finished_at: datetime,
        error_message: str | None = None,
    ) -> None:
        session = None
        try:
            session = SessionLocal()
            save_data_fetch_run(
                session,
                {
                    "cache_key": key,
                    "fetcher": self._fetcher_name(fetch_fn),
                    "status": status,
                    "record_count": record_count,
                    "duration_ms": round((finished_at - started_at).total_seconds() * 1000, 3),
                    "error_message": error_message,
                    "started_at": started_at,
                    "finished_at": finished_at,
                },
            )
        except Exception as e:
            logger.warning(f"任务状态记录失败 ({key}): {e}")
        finally:
            if session is not None:
                session.close()

    def _fetch_and_store(
        self,
        key: str,
        fetch_fn,
        db_save_fn=None,
        ttl: int | None = None,
        **kwargs
    ) -> pd.DataFrame:
        logger.info(f"缓存未命中，调用 fetch_fn: {key}")
        started_at = datetime.now(UTC)
        started_perf = time.perf_counter()
        try:
            df = fetch_fn(**kwargs)
        except Exception as e:
            finished_at = datetime.now(UTC)
            self._record_fetch_run(
                key=key,
                fetch_fn=fetch_fn,
                status="failure",
                record_count=0,
                started_at=started_at,
                finished_at=finished_at,
                error_message=str(e),
            )
            raise

        finished_at = datetime.now(UTC)
        duration_ms = (time.perf_counter() - started_perf) * 1000
        persist_error: str | None = None
        if not df.empty:
            self.save_parquet(key, df)
            self.set_redis(key, df, ttl=ttl)
            if db_save_fn:
                try:
                    records = df.to_dict(orient="records")
                    db_save_fn(records)
                except Exception as e:
                    persist_error = str(e)
                    logger.warning(f"DB 保存回调失败 ({key}): {e}")

        status = "success" if not df.empty else "empty"
        if persist_error:
            status = "persist_failure"
        self._record_fetch_run(
            key=key,
            fetch_fn=fetch_fn,
            status=status,
            record_count=len(df),
            started_at=started_at,
            finished_at=finished_at,
            error_message=persist_error,
        )
        logger.debug(f"{key} 拉取耗时 {duration_ms:.3f}ms, records={len(df)}")
        return df

    def get(
        self,
        key: str,
        fetch_fn,
        use_cache: bool = True,
        db_save_fn=None,
        max_stale_days: float | None = None,
        ttl: int | None = None,
        months: int = 12,
        **kwargs
    ) -> pd.DataFrame:
        """
        统一缓存获取: 先 Redis → 再 Parquet → 最后调 fetch_fn

        Args:
            key: 缓存键名
            fetch_fn: 数据获取函数 (返回 DataFrame)
            use_cache: 是否使用缓存
            db_save_fn: 可选的 DB 保存回调，传入 (records: list[dict])
            max_stale_days: Parquet 数据最大允许过期天数，None=不过期检查
            ttl: Redis TTL（秒），None 使用实例默认值
            months: 从 Parquet 加载最近 N 个月数据
            **kwargs: 传递给 fetch_fn 的参数
        """
        # 1. 尝试 Redis（带新鲜度检查）
        if use_cache:
            cached = self.get_redis(key)
            if cached is not None and not cached.empty:
                if not self._is_stale(cached, max_stale_days):
                    return cached
                logger.info(f"Redis 缓存数据过期 ({key})，跳过")

        # 2. 尝试 Parquet
        if use_cache:
            cached = self.load_parquet(key, months=months)
            if not cached.empty:
                if self._is_stale(cached, max_stale_days):
                    if "date" in cached.columns:
                        latest = cached["date"].max()
                        logger.info(
                            f"Parquet 缓存过期 ({key}): 最新 {latest.date()}, "
                            f"超过 {max_stale_days} 天"
                        )
                else:
                    self.set_redis(key, cached, ttl=ttl)
                    return cached

        # 3. 调用获取函数
        return self._fetch_and_store(
            key,
            fetch_fn,
            db_save_fn=db_save_fn,
            ttl=ttl,
            **kwargs,
        )

    def get_with_meta(
        self,
        key: str,
        fetch_fn,
        use_cache: bool = True,
        db_save_fn=None,
        max_stale_days: float | None = None,
        ttl: int | None = None,
        months: int = 12,
        expected_frequency: str | None = None,
        **kwargs
    ) -> tuple[pd.DataFrame, dict]:
        """Like get(), but also returns freshness and data-quality metadata."""
        source_status = "unavailable"

        if use_cache:
            cached = self.get_redis(key)
            if cached is not None and not cached.empty:
                if not self._is_stale(cached, max_stale_days):
                    cached_at = self.get_redis_cached_at(key) or self._parquet_cached_at(
                        key, months=months,
                    )
                    return cached, dataframe_meta(
                        cached,
                        max_stale_days=max_stale_days,
                        source_status="cache",
                        fetched_at=cached_at,
                        cached_at=cached_at,
                        expected_frequency=expected_frequency,
                    )
                logger.info(f"Redis 缓存数据过期 ({key})，跳过")

        if use_cache:
            cached = self.load_parquet(key, months=months)
            if not cached.empty:
                if self._is_stale(cached, max_stale_days):
                    if "date" in cached.columns:
                        latest = cached["date"].max()
                        logger.info(
                            f"Parquet 缓存过期 ({key}): 最新 {latest.date()}, "
                            f"超过 {max_stale_days} 天"
                        )
                else:
                    self.set_redis(key, cached, ttl=ttl)
                    cached_at = self._parquet_cached_at(key, months=months)
                    return cached, dataframe_meta(
                        cached,
                        max_stale_days=max_stale_days,
                        source_status="cache",
                        fetched_at=cached_at,
                        cached_at=cached_at,
                        expected_frequency=expected_frequency,
                    )

        df = self._fetch_and_store(
            key,
            fetch_fn,
            db_save_fn=db_save_fn,
            ttl=ttl,
            **kwargs,
        )
        if not df.empty:
            source_status = "live"

        return df, dataframe_meta(
            df,
            max_stale_days=max_stale_days,
            source_status=source_status,
            expected_frequency=expected_frequency,
        )


# 全局缓存实例
cache = DataCache()
