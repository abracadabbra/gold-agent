# Technical Design: Dashboard 数据可视化图表

## Architecture

### Dependency

```json
{
  "dependencies": {
    "recharts": "^2.15"
  }
}
```

Recharts v2.x 稳定版，纯 React 组件，无外部 DOM 依赖。

### 组件设计

所有图表组件内联在 `frontend/src/app/dashboard/page.tsx`，遵循以下模式：

```tsx
function ChartNameCard({ refreshKey }: { refreshKey: number }) {
  const { data, loading, error, execute } = useApi<ResponseType>(
    useCallback(() => api.xxx(), [refreshKey])
  );

  if (loading) return <SectionCard title="xxx"><LoadingSkeleton /></SectionCard>;
  if (error || !data) return <ErrorCard title="xxx" error={error || '无数据'} delay={N} onRetry={execute} />;
  if (!data.data?.length) return <SectionCard title="xxx" delay={N}><p className="muted-copy">无数据</p></SectionCard>;

  return (
    <SectionCard title="xxx" delay={N}>
      <ResponsiveContainer width="100%" height={300}>
        <SomeChart data={...}>...</SomeChart>
      </ResponsiveContainer>
      {/* 保留少量数据摘要 */}
    </SectionCard>
  );
}
```

### 图表规格

#### PriceChart

```
数据: api.gold() → GoldPriceResponse
输入: OhlcvPoint[] (close, volume, date)

Component: ComposedChart, 双 Y 轴
- Line: dataKey="close", stroke="#d4a849" (金色), dot=false
- Bar:  dataKey="volume", fill="rgba(128,128,128,0.3)", yAxisId="volume"
- YAxis1: close 价 (左)
- YAxis2: volume (右, 隐藏刻度标签)
- Tooltip: 显示 O/H/L/C/V
- XAxis: dataKey="date", 取最后 100 条
- height: 280px
```

#### SignalGauge

```
数据: api.signal() → SignalResponse
输入: score (-100~100), confidence (0~1)

可视化方案: 自定义 SVG（用 Recharts 的矩形无法实现渐变和指针）
或用 Recharts BarChart 水平条形:
- 一个 Bar dataKey="score", 使用 Cell 根据值着色

替代方案: 纯 CSS/SVG 实现，风格更灵活。推荐 CSS 实现：
- 水平条渐变背景 (linear-gradient: red → gray → green)
- 白色三角形指针定位在 score 位置
- 下方显示 confidence bar
```

**决定**: 用纯 CSS + div 实现，比分条形图视觉更好，代码更简单。

#### IndicatorChart

```
数据: api.indicators() → IndicatorsResponse
输入: indicators: Record<string, number>

Tab 切换:
  Tab1: MACD — 从 indicators 取 macd_line, macd_signal, macd_histogram
  Tab2: RSI — 取 rsi14, 加 ReferenceLine domain=[30, 70]
  Tab3: 布林带 — 取 bb_upper, bb_middle, bb_lower

每个 tab 用 ComposedChart 渲染，height=260
由于 indicators 只返回最新值（非序列），需要改后端或前端模拟。
```

**关键问题**: `GET /api/analysis/indicators` 只返回 **最新一条** 指标值，不是历史序列。图表需要时间序列数据。

**方案 A**: 后端改造 `/api/analysis/indicators` 返回指标历史序列（需要计算历史指标值）
**方案 B**: 前端只显示当前值的仪表盘/数字，不画时间序列折线图
**方案 C**: 前端用 GoldPriceCard 的 OHLCV 数据自己计算简单指标（不可行，缺少 MACD/RSI 所需窗口）

推荐 **方案 A**：修改后端 `compute_indicators()` 返回按日期排列的序列数据，API 返回结构改为 `{ dates: [...], indicators: { key: [values...] } }` 或 `{ data: [{ date, macd, rsi, ... }] }`。

但这是个大改动（影响 quant 层）。为控制范围：

**折衷**: IndicatorChart 只展示 RSI 仪表盘 + MACD 柱状摘要（最新值可视化），不展示历史趋势。后续需改 quant 层时才做时间序列版。

改为 `IndicatorGauge` 风格：
- RSI gauge (水平条, 30/70 标记)
- MACD 状态显示 (正/负柱)
- 布林带位置显示 (上轨/中轨/下轨)

#### PredictionChart

```
数据: api.prediction() → PredictionResponse
输入: PredictionPoint[] { ds, yhat, yhat_lower, yhat_upper }

Component: AreaChart
- Area: dataKey="yhat_upper" + "yhat_lower", fill 半透明, stroke="none"
- Line: dataKey="yhat", stroke="#d4a849"
- Tooltip: 显示预测值 + 区间
- XAxis: dataKey="ds"
- height: 280px
```

### 布局变更

```
grid md:grid-cols-2 xl:grid-cols-3

→ GoldPriceCard + SignalGaugeCard + NewsCard (row 1, current)
→ PriceChartCard (col-span-2, new, replaces IndicatorsCard position)
→ IndicatorGaugeCard (1 col, new) + PredictionChartCard (col-span-2, replaced)
→ MacroCard + BacktestCard (row 4, unchanged)
→ DebateCard (full width, unchanged)
→ 补充数据 (unchanged)
```

简化：减少 grid 变动，将图表嵌入或替换对应的现有 card。

- GoldPriceCard → 替换为 PriceChartCard（图表 + 最新价格摘要）
- SignalCard → 替换为 SignalGaugeCard（评分条 + confidence/SL/TP）
- IndicatorsCard → 替换为 IndicatorGaugeCard（RSI/MACD/BB 仪表盘）
- PredictionCard → 保留，增加 PredictionChartCard 图表

## Cache TTL

无新增数据源，复用现有 API 缓存。图表组件通过 `refreshKey` 统一刷新。
