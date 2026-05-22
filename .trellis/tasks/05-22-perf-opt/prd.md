# performance-optimization: 全面性能审计与优化

## Goal

减少 Dashboard 加载时间和后端响应延迟，消除重复/冗余请求，优化前端打包体积。

## 已发现的瓶颈 (从审计报告)

| # | 瓶颈 | 类型 | 影响 |
|---|------|------|------|
| 1 | 7 次重复 `extraData()` 调用 | 前端请求 | **高** — 6 次多余 HTTP 往返 |
| 2 | WebSocket 导致全面刷新 | 前端模式 | **高** — 增量更新触发 17 次重新请求 |
| 3 | `extra_data.py` 后端顺序获取 14 个数据源 | 后端瀑布 | **高** — 15~20s 串行等待 |
| 4 | 辩论 `_build_context()` 顺序获取 4 个数据源 | 后端瀑布 | **中高** — 额外延迟 |
| 5 | 打包含 `recharts` + `lightweight-charts` ~700KB | 前端体积 | **中** — 无代码分割 |
| 6 | `gold()` 和 `signal()` 各重复请求 2 次 | 前端请求 | **中** — 2 次多余往返 |

## Requirements

1. 消除重复的 API 调用（extraData 7→1, gold/signal 2→1）
2. 后端 extra_data 并行化（asyncio.gather）
3. WebSocket 增量更新替代全局刷新
4. 辩论 _build_context 并行化
5. recharts 动态导入减少首屏体积
6. 自动刷新策略优化

## Out of Scope

- Redis 缓存分布式锁（当前单实例无竞争风险）
- LLM 调用本身的加速（依赖外部 API）
- React Query/SWR 引入（维护成本 > 收益）

## Acceptance Criteria

- [ ] extraData 仅调用 1 次，7 个卡片共享数据
- [ ] gold/signal 各仅调用 1 次
- [ ] extra_data.py 后端并行获取，延迟减至 1/3
- [ ] WebSocket 推送按频道更新对应卡片
- [ ] recharts 动态加载，首屏 JS 减少 ~400KB
- [ ] lint/typecheck 无新错误

## Technical Approach

**Phase 1 — 前端请求去重**（高收益/低风险）
- 父组件加载 extraData，通过 props 下发或 Context 共享
- gold/signal 提升到父组件或同一组件内复用

**Phase 2 — 后端并行化**
- extra_data.py: 14 个 fetch 用 asyncio.gather 并行
- debate.py: _build_context 用 asyncio.gather 并行获取金价+宏观+新闻

**Phase 3 — WebSocket 增量更新**
- useWebSocket 回调按 channel 调用特定卡片刷新，而非全局 refresh()

**Phase 4 — 打包优化**
- 动态 import() 加载 PredictionChartCard

## Implementation Plan

1. 前端请求去重 + recharts 动态导入
2. 后端并行化
3. WebSocket 增量更新
