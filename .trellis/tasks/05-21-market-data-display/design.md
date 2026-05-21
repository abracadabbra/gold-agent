# 行情数据展示优化 — 技术设计

## 总体架构

所有改动集中在 `frontend/src/app/dashboard/page.tsx`，后端 API 已支持所需数据维度（source/period 参数）。无需修改后端逻辑。

## 子任务划分

### Child 1: 行情图重构
重构 `PriceChartCard`，支持多源/多周期/K线/均线/价差/指标联动。

### Child 2: 加载体验优化
自动刷新机制、骨架屏细节优化、避免不必要的重复请求。

### Child 3: 布局优化
卡片分组、核心指标突出、移动端适配。

---

## Child 1 详细设计

### 数据流

```
PriceChartCard
  ├── SourceSwitcher → [intl | gld | shfe]
  ├── PeriodSelector → [1mo | 3mo | 6mo | 1y | 5y]
  │
  ├── [主图] K线图 + 成交量柱
  │     ├── MA20/MA50/MA200 叠加线
  │     └── 十字准星交互
  │
  ├── [副图区] 价差图 / 指标图
  │     ├── 国际 vs 国内价差折线
  │     └── RSI / MACD / 布林带
  │
  └── StatsBar: 最新价、涨跌幅、最高/最低
```

### 请求策略

- `source` 或 `period` 变更 → 重新请求 `GET /api/analysis/gold` + `indicators`
- 数据缓存在前端 state，切换 source 时保留其它 source 的数据（避免来回切换重复加载）
- 所有请求并行发出

### 图表库选择

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Recharts 自定义 K线** | 已有依赖，学习成本低 | K线需自定义 Rectangle，交互（缩放/十字准星）工程量较大 |
| **lightweight-charts (TradingView)** | 原生 K线/成交量/MA/十字准星；轻量（~50KB）；金融图表专用 | 新增依赖；设计风格需对齐 |

**推荐：lightweight-charts** — K线/均线/十字准星都是开箱即用，比 Recharts 自定义实现工作量小得多。

### 组件结构

```
PriceChartCard
  ├── Toolbar
  │   ├── SourceSwitcher
  │   └── PeriodSelector
  ├── StatsBar (最新价, 涨跌%, 最高, 最低)
  ├── MainChart (lightweight-charts)
  │   ├── CandlestickSeries (主K线)
  │   ├── LineSeries (MA20/50/200)
  │   └── HistogramSeries (成交量)
  ├── SubChart (lightweight-charts 第二个实例)
  │   ├── 价差模式: LineSeries (intl - shfe 价差)
  │   └── 指标模式: LineSeries (RSI / MACD / BB 位置)
  └── TabSwitch: [价差] / [RSI] / [MACD] / [布林带]
```

### State

```typescript
interface PriceChartState {
  source: 'intl' | 'gld' | 'shfe';
  period: '1mo' | '3mo' | '6mo' | '1y' | '5y';
  subTab: 'spread' | 'rsi' | 'macd' | 'bb';
  data: Record<string, GoldData>;  // 按 source 缓存
}
```

### 价差逻辑

- 需要同时获取 `intl` 和 `shfe` 两个来源
- 日期对齐后做价差计算（前端或后端均可，前端计算更灵活）
- 价差 = shfe_close / 美元汇率 - intl_close（或直接展示比值）

---

## Child 2 详细设计

### 自动刷新

- 使用 `setInterval` + `useRef` 管理定时器
- 默认间隔 60s，可通过配置文件调整
- 仅刷新关键卡片（行情图、信号），非全量刷新
- 页面不可见时（`document.hidden`）暂停定时器

### 骨架屏优化

- 当前已有 `LoadingSkeleton` 组件，单卡片独立显示
- 改进：首次加载时展示整页骨架屏骨架（3-4个占位块），后续更新只显示单卡片加载

### 缓存策略

- 当前 `useApi` hook 每次执行都重置 `data` 为 `null`
- 改进：保留上次成功数据，加载时显示旧数据 + 加载指示器，避免 UI 闪烁
- 组件卸载时不清理数据，重新挂载时先显示缓存数据

---

## Child 3 详细设计

### 卡片分组

```
顶层 Tab 导航（或垂直分段）:
  ├── 行情概览 (金价图 + 指标 + 信号)
  ├── 宏观数据 (宏观 + 中国宏观 + FedWatch + 新闻)
  ├── 补充数据 (央行储备 / COT / ETF / 地缘 / AISC)
  └── 工具 (辩论引擎 / 回测 / 财经日历)
```

- 使用 URL hash 或 state 记录当前 tab
- 非活跃 tab 的卡片延迟加载或缓存数据

### 核心指标突出

- 顶部显示一条 "指标栏"：最新金价（大字体）+ 涨跌方向 + 信号 + 更新时间
- 这个指标栏在所有 tab 顶部固定显示

### 移动端适配

- 确保 `ResponsiveContainer` 在移动端合理缩放
- 卡片在小屏幕上改为单列布局
- 图表高度在手机上适当降低

---

## 兼容性分析

### 向后兼容
- 所有修改在 `PriceChartCard` 内部，不影响其它卡片
- `DebateCard`、`BacktestCard`、`MacroCard`、`NewsCard` 等无改动
- 布局改动仅在 DashboardPage 层面调整 grid

### 数据兼容
- 后端 API 不变，只改前端消费方式
- 缓存策略使用已有数据，不改变后端缓存逻辑
