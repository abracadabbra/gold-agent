# Dashboard 数据可视化图表

## Goal

为 dashboard 引入 Recharts 图表库，将金价、信号、指标、预测数据从纯表格升级为可视化图表，提升数据可读性。

## Requirements

### 图表组件

1. **PriceChart** — 金价走势折线图
   - 主 y 轴：close 价折线（金色）
   - 辅 y 轴：成交量柱状图（半透明灰色）
   - X 轴：日期（展示最近 100 条）
   - 数据：`/api/analysis/gold`
   - 可选：Tooltip 悬浮显示 O/H/L/C

2. **SignalGauge** — 信号评分水平柱
   - 水平条形 + 渐变填充（-100 红 → 0 灰 → +100 绿）
   - 指针标记当前 score
   - 同时显示 confidence、stop_loss、take_profit
   - 数据：`/api/analysis/signal`

3. **IndicatorChart** — MACD / RSI 图表
   - Tab 切换：MACD / RSI / 布林带
   - MACD：柱状图 (histogram) + MACD 线 + 信号线
   - RSI：折线 + 参考线 (30 超卖 / 70 超买)
   - 布林带：区间填充 + 价格线
   - 数据：`/api/analysis/indicators`

4. **PredictionChart** — 预测区间带状图
   - 置信区间填充 (yhat_lower ~ yhat_upper)
   - 预测值折线 (yhat)
   - 数据：`/api/analysis/predict`

### 集成要求

- 图表组件直接内联在 `page.tsx`（不拆独立文件，一致性优先）
- 替换对应 card 中的 DataTable 为图表 + 保留最新几行摘要
- 遵循现有 loading skeleton / error / empty 状态约定
- 图表宽度自适应，使用 `ResponsiveContainer`

### 约束

- 仅使用 Recharts 官方组件，不写自定义 SVG
- 不引入 K 线图（candlestick）
- 不实现拖拽缩放
- 不实现多图联动 crosshair

## Acceptance Criteria

- [ ] `npm install recharts` 安装成功，lint 无新增错误
- [ ] PriceChart 正确渲染金价折线 + 成交量柱，无数据时显示"无数据"
- [ ] SignalGauge 正确显示评分条、confidence、SL/TP
- [ ] IndicatorChart 三个 tab 切换正常工作
- [ ] PredictionChart 正确显示预测区间带状
- [ ] 所有图表在大屏/小屏下自适应
- [ ] `npm run lint` 0 errors 0 warnings
- [ ] `npm run build` 成功（无 TypeScript 错误）

## Out of Scope

- K 线图
- 图表导出 / 截图
- WebSocket 实时更新图表
- 多图表联动
- 自定义主题色（沿用现有 CSS 变量）
