# Data 层测试

## Goal

为 `src/gold_agent/data/` 模块补充单元测试：gold_price, macro, news, cache。

## Modules to test

- `data/gold_price.py` — yfinance/akshare 金价获取函数
- `data/macro.py` — FRED + yfinance 宏观数据获取
- `data/news.py` — RSS 新闻抓取和情绪分析
- `data/cache.py` — DataCache 三级缓存（Redis + Parquet + fetch）

## Approach

- Mock 外部依赖（yfinance, akshare, FRED, httpx, redis）
- 不依赖真实网络/数据库
- 使用 pytest fixtures 提供 mock 数据
- 对 cache.py 的 3 级缓存回退逻辑做分支覆盖

## Acceptance Criteria

- [ ] gold_price 测试：mock yfinance/akshare 返回假数据，验证 DataFrame 结构
- [ ] macro 测试：mock FRED/yfinance，验证列名和日期格式
- [ ] news 测试：mock RSS 响应，验证情绪评分计算
- [ ] cache 测试：覆盖 Redis 命中 → Parquet 命中 → fetch_fn 调用链
- [ ] ruff check 通过
