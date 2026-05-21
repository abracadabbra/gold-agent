# 行情数据展示优化

## Goal

系统性地优化行情数据展示，覆盖数据维度、展示方式、性能体验、信息布局四个方向，提升 Dashboard 的实用性和用户体验。

## Requirements

### A. 数据维度
- [ ] **数据源切换** — 行情图卡支持切换 intl（COMEX 黄金期货）/ GLD（SPDR ETF）/ SHFE（上海金交所 Au99.99）
- [ ] **时间周期选择** — 图表上方加 1月/3月/6月/1年/5年 快速切换
- [ ] **国内外价差对比** — 国际金价与上海金价叠加显示，直观展示溢价/折价
- [ ] **均线叠加** — K线图上叠加 MA20/MA50/MA200

### B. 展示方式
- [ ] **K线图** — 折线改为红绿K线（candlestick chart）
- [ ] **日期标注简化** — 图表 X 轴只显示日期（如 MM-DD），去掉多余信息
- [ ] **图表交互增强** — 十字准星、缩放、拖拽
- [ ] **指标联动** — RSI/MACD/布林带作为子图嵌入行情图下方，无需切换 tab

### C. 性能/加载体验
- [ ] **自动刷新机制** — 定时自动刷新关键数据（金价、信号），可配置刷新间隔
- [ ] **加载性能优化** — 优化骨架屏过渡效果、并行请求策略
- [ ] **缓存策略** — 切换 tab/页面返回时保留已有数据，避免不必要的重新加载

### D. 信息密度/布局
- [ ] **卡片分组** — 按功能区分类（行情指标 / 宏观数据 / 补充数据 / 工具），可用 tab 或折叠面板组织
- [ ] **核心指标突出** — 最新金价、交易信号等关键信息更显眼
- [ ] **可定制布局** — 用户可选显示/隐藏特定卡片
- [ ] **移动端适配** — 优化手机端浏览体验

## Acceptance Criteria

- [ ] 所有需求确认后形成 `design.md` 和 `implement.md`
- [ ] 实施后 lint/typecheck 通过
- [ ] 现有功能不受影响（回测、辩论等卡片正常工作）

## Out of Scope

- 不修改后端数据采集逻辑（`data/gold_price.py`）
- 不修改数据库结构
- 不修改 WebSocket 推送逻辑

## Technical Notes

- 当前代码路径: `frontend/src/app/dashboard/page.tsx`
- 后端 API:
  - `GET /api/analysis/gold?source=intl|gld|shfe&period=1y|3mo|1mo|6mo|2y|5y`
  - `GET /api/analysis/indicators?source=intl&period=1y`
  - `GET /api/analysis/signal`, `/prediction`, `/news`, `/macro`, `/extraData`, `/calendar`, `/debate`, `/backtest`
- 组件库: Recharts（需确认 K线 实现方案）
- 已有 `fetch_all_gold()` 可一次性获取三个来源数据
