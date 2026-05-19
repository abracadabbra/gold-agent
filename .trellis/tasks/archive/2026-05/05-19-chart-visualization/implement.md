# Implementation Plan: Dashboard 数据可视化图表

## Order of Execution

### Step 1: Install Recharts
- [ ] `cd frontend && npm install recharts`
- [ ] Verify: `npm run lint` passes

### Step 2: PriceChartCard — 金价走势图
- [ ] 在 `page.tsx` 中新增 `PriceChartCard` 组件
- [ ] `ComposedChart`: close 折线 (金色) + volume 柱 (半透明)
- [ ] 双 Y 轴 (close 左 / volume 右)
- [ ] Tooltip 显示 O/H/L/C/V
- [ ] 保留最新价格摘要（替换 GoldPriceCard）
- [ ] 验证渲染

### Step 3: SignalGaugeCard — 信号评分条
- [ ] 纯 CSS 渐变水平条（红 → 灰 → 绿）
- [ ] 白色三角形指针标记 score 位置
- [ ] 下方显示 confidence、stop_loss、take_profit
- [ ] 替换 SignalCard
- [ ] 验证渲染

### Step 4: IndicatorGaugeCard — 指标仪表盘
- [ ] Tab 切换：RSI / MACD / 布林带（非折线图，当前值可视化）
- [ ] RSI：水平条 + 30/70 标记线
- [ ] MACD：柱状图标 + 数值显示
- [ ] 布林带：显示价格相对位置（上轨/中轨/下轨百分比）
- [ ] 替换 IndicatorsCard
- [ ] 验证渲染

### Step 5: PredictionChartCard — 预测区间图
- [ ] `AreaChart`: yhat_lower~yhat_upper 置信区间
- [ ] `Line`: yhat 预测值折线
- [ ] Tooltip 显示预测值 + 区间
- [ ] 保留预测摘要文本
- [ ] 替换现有 PredictionCard
- [ ] 验证渲染

### Step 6: Final Verification
- [ ] `cd frontend && npm run lint` — 0 errors
- [ ] `cd frontend && npx tsc --noEmit` — 0 errors
- [ ] 手动检查所有图表渲染（Tablet / Desktop 布局）
- [ ] 验证 loading → data / loading → error 状态切换

## Validation Commands

```bash
cd /Users/shentao/IdeaProjects/gold-agent/frontend
npm run lint
npx tsc --noEmit
```

## Rollback Points

- Step 1 失败：`npm uninstall recharts`
- Step 2-5 单个组件问题：移除该组件函数，恢复原 card 函数
- 整体回退：`git checkout -- frontend/src/app/dashboard/page.tsx`

## 注意事项

- 所有图表组件内联在 `page.tsx`，不创建新文件
- 图表容器用 `ResponsiveContainer`，不加固定宽高
- 颜色用现有 CSS 变量：`var(--accent)` / `var(--danger)` / `var(--border)` 等
- 无数据 / loading / error 状态复用现有 `LoadingSkeleton` / `ErrorCard` 组件
