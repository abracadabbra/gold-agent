"""数据缓存层 — 本地 Parquet + 可选 Redis"""

from pathlib import Path

import pandas as pd
import logging
logger = logging.getLogger(__name__)

from gold_agent.config import settings


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
        files = sorted(self.data_dir / key / f"{pd.Timestamp.now().strftime('%Y-%m')}.parquet"
                       for _ in range(1))

        # 实际用 glob
        import glob
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

    def get_redis(self, key: str) -> pd.DataFrame | None:
        """从 Redis 读取缓存"""
        if not self.redis:
            return None

        rkey = self._redis_key(key)
        data = self.redis.get(rkey)
        if data is None:
            return None

        try:
            import json
            records = json.loads(data)
            df = pd.DataFrame(records)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
            logger.debug(f"Redis 缓存命中: {key} ({len(df)} 行)")
            return df
        except Exception as e:
            logger.warning(f"Redis 反序列化失败: {e}")
            return None

    def set_redis(self, key: str, df: pd.DataFrame, ttl: int | None = None) -> bool:
        """写入 Redis 缓存"""
        if not self.redis or df.empty:
            return False

        rkey = self._redis_key(key)
        try:
            import json
            data = df.copy()
            if "date" in data.columns:
                data["date"] = data["date"].astype(str)
            effective_ttl = ttl or self.cache_ttl
            self.redis.setex(rkey, effective_ttl, json.dumps(data.to_dict(orient="records")))
            logger.debug(f"Redis 缓存写入: {key} (TTL={effective_ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"Redis 写入失败: {e}")
            return False

    # ---- 统一接口 ----

    def get(
        self,
        key: str,
        fetch_fn,
        use_cache: bool = True,
        db_save_fn=None,
        max_stale_days: int | None = None,
        ttl: int | None = None,
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
            **kwargs: 传递给 fetch_fn 的参数
        """
        # 1. 尝试 Redis
        if use_cache:
            cached = self.get_redis(key)
            if cached is not None and not cached.empty:
                return cached

        # 2. 尝试 Parquet
        if use_cache:
            cached = self.load_parquet(key)
            if not cached.empty:
                if max_stale_days is not None and "date" in cached.columns:
                    latest = cached["date"].max()
                    if pd.notna(latest) and (pd.Timestamp.now() - latest).days > max_stale_days:
                        logger.info(
                            f"Parquet 缓存过期 ({key}): 最新 {latest.date()}, "
                            f"超过 {max_stale_days} 天"
                        )
                    else:
                        self.set_redis(key, cached, ttl=ttl)
                        return cached
                else:
                    self.set_redis(key, cached, ttl=ttl)
                    return cached

        # 3. 调用获取函数
        logger.info(f"缓存未命中，调用 fetch_fn: {key}")
        df = fetch_fn(**kwargs)

        if not df.empty:
            self.save_parquet(key, df)
            self.set_redis(key, df, ttl=ttl)
            if db_save_fn:
                try:
                    records = df.to_dict(orient="records")
                    db_save_fn(records)
                except Exception as e:
                    logger.warning(f"DB 保存回调失败 ({key}): {e}")

        return df


# 全局缓存实例
cache = DataCache()
