# 首页报告页动态度改造

## Goal

将首页 `/` 报告页从主要硬编码数据改造为 API 实时数据驱动，保持现有布局和组件结构。

## Requirements

- 所有可映射区块从 API 获取实时数据，不再使用硬编码假数据
- 不改后端，只改前端 `page.tsx`
- 保留现有视觉样式和组件结构
- 加载状态处理（loading/error fallback）
- 情景分析区块仍然保留，从 prediction + signal 数据生成

## Acceptance Criteria

- [ ] 修复 `signal_type` → `signal` 字段名 bug，信号标签显示正确
- [ ] 顶部指标（多头/空头/置信度/止盈止损）全部来自 API
- [ ] 宏观摘要显示实时收益率（us_10y, us_2y, tips_yield）
- [ ] 技术面区块用 indicators summary 替换硬编码
- [ ] K线快照显示实时最新价 + 支撑/压力位
- [ ] 国外/国内新闻从 news API 按 source 分离
- [ ] 三情景从 prediction + signal 实时生成（含正确日期）
- [ ] 反向风险用 signal.reasons 填充
- [ ] 加载中显示骨架屏，API 失败时有 fallback

## Definition of Done

- Lint / typecheck / build green
- 信号标签不再是"偏空"（修复 bug）
- 显示的日期是当前日期，而非 2026-05-06

## Decision (ADR-lite)

**Context**: 报告页 14 个区块大部分硬编码假数据，需要动态化
**Decision**: 不改后端，前端复用现有 API（signal/gold/indicators/macro/news/predict）拼装数据
**Consequences**: 前端需要一定的数据变换逻辑（数值→叙述文本），但避免了后端的耦合变更

## Out of Scope

- 新增后端 API 端点
- 布局 / 样式改动
- 参考链接区块（无 API 数据源）
- 风险事件区块（采集状态无 API 对应）

## Technical Notes

### API 调用清单（7 个）
```
api.signal()       → signal / score / confidence / stop_loss / take_profit / reasons
api.quick()        → signal + indicators markdown
api.gold()         → latest_price / data
api.indicators()   → summary 文本 + indicators 字典
api.macro()        → realtime (us_10y/us_2y/vix) + official (cpi/fed_rate/tips_yield)
api.news()         → news[] 含 title/source/sentiment
api.prediction()   → forecast (yhat/yhat_lower/yhat_upper) + trend + history
```

### 区块数据映射

| 区块 | API | 数据变换 |
|------|-----|---------|
| 信号标签 | signal.signal | `sell` → `labelMap['sell']` |
| 多头/空头概率 | signal.score | `max(0, score)%` / `max(0, -score)%` |
| 置信度 | signal.confidence | `(confidence * 100).toFixed(0)%` |
| 止盈/止损 | signal.take_profit / stop_loss | 直接显示 |
| K线快照 | gold.latest_price + indicators.summary | 提取支撑/压力位 |
| 宏观摘要 | macro.realtime.us_10y / us_2y + official.tips_yield | 格式化最新值 |
| 技术面 | indicators.summary | 直接替换 |
| 国外宏观 | macro.official (cpi/fed_rate/m2) | 格式化 FRED 数据 |
| 国内新闻 | news.news 过滤 `source=google_news_cn` | 取 title |
| 国外新闻 | news.news 过滤非中文源 | 取 title |
| 明日情景 | prediction 第 1 天 + signal support/resistance | 模板生成 |
| 后日情景 | prediction 第 2 天 + signal support/resistance | 模板生成 |
| 核心依据 | signal.reasons + indicators.summary | 合并为要点列表 |
| 反向风险 | signal.reasons 过滤器 | 提取风险类要点 |
