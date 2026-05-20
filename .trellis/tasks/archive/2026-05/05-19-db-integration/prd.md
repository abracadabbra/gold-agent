# 数据库接入（SQLite）

## Goal

将 ORM 表从定义状态接入运行时数据流，实现数据持久化到 SQLite。

## Requirements

1. 默认数据库从 PostgreSQL 切为 SQLite（零依赖，文件级）
2. async SQLAlchemy session 管理
3. 服务启动时自动建表
4. 数据写入：在缓存层写入 Parquet 后同步写 DB
5. 基础查询接口：按时间范围/来源获取数据
6. 去重：同一数据（同日期+同来源）不重复写入

## Acceptance Criteria

- [ ] 服务启动时日志可见 `创建数据库表: 9/9`
- [ ] API 请求后对应表有数据（`GoldPrice`, `TradeSignal`, `MacroData`, `NewsArticle` 等）
- [ ] 重复请求不会产生重复行
- [ ] `ruff check src/` 通过
- [ ] 无需 Docker 即可运行

## Out of Scope

- 数据迁移（无旧数据）
- ORM 做复杂查询（仅写入 + 基础查询）
- Debate / Backtest 结果写入（当前触发频率低，后续再做）
