# WebSocket 后端定时推送

## Goal

补完 `websocket.py` 中 `periodic_price_push` 空实现，注册 background task 到 `main.py` lifespan，实现后端定时采集数据并通过 WebSocket 推送。

## Requirements

1. `periodic_price_push(60)` — 每 60s 采集最新金价推送
2. `periodic_signal_push(60)` — 每 60s 采集最新信号推送
3. `periodic_news_push(300)` — 每 300s 采集最新新闻推送
4. lifespan 中注册为 asyncio background task，服务关闭时优雅取消
5. 日志记录推送状态（成功 / 无订阅者 / 失败）

## Acceptance Criteria

- [ ] 服务启动后，日志可见 `periodic_price_push` 按间隔执行
- [ ] 每个推送独立 try/except，一个失败不影响其他
- [ ] 服务关闭时 tasks 正确取消（无 asyncio 异常）
- [ ] `ruff check src/` 无新增错误
- [ ] `mypy src/` 无新增类型错误

## Out of Scope

- 前端 WebSocket 连接
- 新增数据源（extra_data）的推送
