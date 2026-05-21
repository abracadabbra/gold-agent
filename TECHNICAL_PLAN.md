# GoldAgent — 项目技术方案

> 黄金市场综合分析系统：数据采集、量化分析、LLM 辩论、实时推送、前端可视化

---

## 1. 项目概述

### 1.1 目标

构建一套面向黄金市场的全栈分析系统，覆盖：

| 能力 | 说明 |
|------|------|
| **数据采集** | 15+ 数据源（实时行情、宏观指标、持仓、ETF、新闻情绪、央行储备、生产成本） |
| **量化分析** | 18 项技术指标、信号生成、Prophet 时序预测、Backtrader 回测 |
| **LLM 辩论** | 4 Agent 异步辩论（看多、看空、审计、仲裁），基于真实数据交叉验证 |
| **WebSocket 推送** | 价格（60s）、信号（60s）、新闻（300s）实时推送到前端 |
| **前端仪表盘** | 17 个数据卡片，Recharts 图表，支持"全部刷新"联动 |
| **数据库持久化** | 9 张 ORM 表，upsert 去重，SQLite/PostgreSQL 双模式 |

### 1.2 架构总览

```
┌──────────────────────────────────────────────────────────┐
│                       Frontend (Next.js 16)              │
│  dashboard/page.tsx — 17 数据卡片 + Recharts 图表        │
└──────────────────────┬───────────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────▼───────────────────────────────────┐
│                   Backend (FastAPI)                       │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌───────┐ ┌───────────────┐  │
│  │ Analysis │ │  Debate  │ │WS Push│ │  Extra Data   │  │
│  │  Router  │ │  Router  │ │Router │ │    Router     │  │
│  └────┬─────┘ └────┬─────┘ └───┬───┘ └──────┬────────┘  │
│       │            │           │             │           │
│  ┌────▼────────────▼───────────▼─────────────▼────────┐  │
│  │               Business Layer                        │  │
│  │  Quant (indicators/signals/predict/backtest)        │  │
│  │  Debate (agents/prompts/llm/engine)                 │  │
│  └────┬────────────────────────────────────────────────┘  │
│       │                                                   │
│  ┌────▼────────────────────────────────────────────────┐  │
│  │           Data Collection Layer                      │  │
│  │  yfinance │ akshare │ FRED │ cot_reports │ WGC XLSX │  │
│  │  cme_fedwatch │ httpx RSS │ IMF IFS snapshot        │  │
│  │       ┌──────────────┐                               │  │
│  │       │  DataCache   │                               │  │
│  │       │ Redis+Parquet│                               │  │
│  │       └──────────────┘                               │  │
│  └────┬────────────────────────────────────────────────┘  │
│       │                                                   │
│  ┌────▼────────────────────────────────────────────────┐  │
│  │         Database (SQLite / PostgreSQL)               │  │
│  │  9 ORM tables · upsert by (date, source) or title   │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 1.3 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 语言 | Python | ≥ 3.12 |
| Web 框架 | FastAPI | ≥ 0.115 |
| ASGI | uvicorn | latest |
| ORM | SQLAlchemy | ≥ 2.0 |
| 数据库 | SQLite (dev) / PostgreSQL (prod) | — |
| 缓存 | Redis + Parquet | — |
| 数据采集 | yfinance, akshare, fredapi | — |
| 量化 | pandas-ta, prophet, backtrader | — |
| LLM | openai (OpenAI 兼容 API) | ≥ 1.60 |
| 前端 | Next.js | 16.2.6 |
| 图表 | Recharts | 3.8.1 |
| CSS | Tailwind CSS | 4 |

---

## 2. 数据采集层

### 2.1 架构模式

所有数据 collector 遵循统一模式：

```python
def fetch_xxx(**kwargs) -> pd.DataFrame:
    try:
        # ... data source specific logic ...
        return df
    except Exception:
        logger.warning(f"[xxx] 采集失败: {e}")
        return pd.DataFrame()
```

统一通过 `DataCache.get()` 调用：

```python
cache.get(key="gold_intl", fetch_fn=fetch_gold_price, source="intl", period="1y")
```

### 2.2 缓存架构 (`DataCache`)

```
DataCache.get(key, fetch_fn, ...)
  ├── 1) Redis 命中 ──→ 反序列化 JSON ──→ 返回
  ├── 2) Parquet 命中 ──→ 读 parquet ──→ 回填 Redis ──→ 返回
  └── 3) 未命中 ──→ fetch_fn() ──→ 存 Parquet ──→ 回填 Redis ──→ 返回
```

- **Redis**: 热缓存，TTL 5 分钟，JSON 序列化
- **Parquet**: 持久化，按 `date` 列的 `YYYY-MM` 分区存储
- **失效策略**: Redis 失败降级为纯本地，无主动失效机制

### 2.3 数据源清单

#### 2.3.1 实时金价 — `data/gold_price.py`

| 函数 | 源 | 频率 | 列 |
|------|-----|------|-----|
| `fetch_gold_xauusd` | yfinance `GC=F` | 日 | date, OHLC, volume |
| `fetch_gold_etf` | yfinance `GLD` | 日 | date, OHLC, volume |
| `fetch_gold_spot_akshare` | akshare `spot_golden_benchmark_sge` | 日 | date, OHLC, volume |

#### 2.3.2 宏观指标 — `data/macro.py`

**yfinance (实时)**:

| 指标 | Ticker | 中文 |
|------|--------|------|
| usd_index | DX-Y.NYB | 美元指数 |
| us_10y | ^TNX | 10Y 美债收益率 |
| us_2y | ^IRX | 2Y 美债收益率 |
| vix | ^VIX | 恐慌指数 |
| sp500 | ^GSPC | 标普 500 |
| crude_oil | CL=F | WTI 原油 |

**FRED (官方统计)**:

| 指标 | Series ID | 备注 |
|------|-----------|------|
| cpi | CPIAUCSL | CPI 同比 |
| fed_rate | FEDFUNDS | 联邦基金利率 |
| m2 | M2SL | M2 货币供应量 |
| us_10y_yield | DGS10 | 10Y 美债日频 |
| us_2y_yield | DGS2 | 2Y 美债日频 |
| tips_yield | DFII10 | TIPS 实际利率 |

> **注意**: 原 `GOLDAMGBD228NLBM` (伦敦金定盘价) 已于 2025 年从 FRED 移除。金价数据通过 yfinance 获取。

#### 2.3.3 中国宏观 — `data/china_macro.py`

| 函数 | akshare 源 | 数据 |
|------|-----------|------|
| `fetch_china_cpi` | macro_china_cpi | 消费者物价指数 |
| `fetch_china_ppi` | macro_china_ppi | 生产者物价指数 |
| `fetch_china_pmi` | macro_china_pmi | 制造业 PMI |
| `fetch_china_m2` | macro_china_money_supply | 货币供应量 |
| `fetch_china_gdp` | macro_china_gdp | 季度 GDP |
| `fetch_china_lpr` | macro_china_lpr | 贷款基准利率 |
| `fetch_china_fx` | fx_spot_quote | USD/CNY 实时汇率 (无日期列，特殊处理) |

#### 2.3.4 补充数据 (7 大源) — `data/cot.py`, `etf_flow.py`, `geopol.py`, `fed_watch.py`, `aisc.py`, `central_bank.py`, `calendar.py`

| 模块 | 源 | 频率 | 缓存 TTL |
|------|-----|------|----------|
| COT | cot_reports 库 | 周 | 1 天 |
| ETF 流量 | WGC XLSX / yfinance 兜底 | 日 | 7 天 |
| GPR 指数 | matteoiacoviello.com XLS | 月 | 1 天 |
| FedWatch | cme_fedwatch 库 | 日 | 6 小时 |
| AISC | WGC XLSX | 季 | 30 天 |
| 央行储备 | WGC/IMF IFS 静态快照 | 月 (静态) | 7 天 |
| 财经日历 | Mock 数据 | — | — |

#### 2.3.5 新闻情绪 — `data/news.py`

**RSS 源**:
- Google News (gold)
- Reuters (via Google News RSS)
- Mining.com/feed

**情绪分析**: 关键词匹配（中英文），评分 [-1, +1]，三分类 (bullish/neutral/bearish)

### 2.4 已知数据源问题

| 源 | 问题 | 状态 |
|----|------|------|
| FRED `GOLDAMGBD228NLBM` | 已从 FRED 移除 | 已移除，改用 yfinance |
| IMF SDMX API | 服务下线 (NXDOMAIN) | 已切换为静态快照 |
| Kitco RSS | 404 | 已切换为 mining.com |
| akshare `fx_spot_quote` | 无日期列，实时快照 | 已添加专用 handler |
| cot_reports / cme_fedwatch | 可选依赖，未安装则返回空 | 保持现状 |

---

## 3. 量化分析层

### 3.1 技术指标 — `quant/indicators.py`

**输入**: OHLCV DataFrame (日频)

**输出**: `IndicatorResult` dataclass (18 个指标)

| 分类 | 指标 | 实现 |
|------|------|------|
| 趋势 | MA5/10/20/60, EMA12/26 | pandas-ta → 纯 pandas 回退 |
| MACD | macd_line, signal, hist | pandas-ta → 纯 pandas 回退 |
| 振荡器 | RSI14, Stoch %K/%D | pandas-ta → 纯 pandas 回退 |
| 波动率 | BB upper/mid/lower, ATR14 | pandas-ta (BB 回退完整) |
| 趋势强度 | ADX | pandas-ta → 纯 pandas 回退 |
| 成交量 | OBV | pandas-ta (无纯 pandas 回退) |
| 其他 | Supertrend | pandas-ta (无纯 pandas 回退) |

### 3.2 信号生成 — `quant/signals.py`

**评分规则** (总分 -100 ~ +100):

| 条件 | 分值 |
|------|------|
| MA5 > MA20 | +20 / -20 |
| MA20 > MA60 | +10 / -10 |
| RSI < 30 / > 70 | +15 / -15 |
| MACD 金叉 / 死叉 | +15 / -15 |
| 价格触 BB 下轨 / 上轨 | +10 / -10 |
| Supertrend 转多 / 转空 | +20 / -20 |
| ADX > 25 确认趋势 | +10 / -10 |

**分类**: ≥50 STRONG_BUY / ≥20 BUY / ≤-20 SELL / ≤-50 STRONG_SELL

### 3.3 Prophet 预测 — `quant/predictor.py`

- 至少 30 天数据
- daily + weekly + yearly seasonality
- 支持外部回归因子 (USD/VIX/国债收益率等)，未来值用最后一行填充
- `changepoint_prior_scale=0.05`
- 返回: forecast DataFrame + trend + changepoints + components

### 3.4 回测 — `quant/backtest/engine.py`

- 基于 Backtrader
- 内置策略: `golden_cross` (MA20/MA60 + RSI 过滤 + ATR 止损)
- 分析器: SharpeRatio, DrawDown, TradeAnalyzer
- 佣金: 0.1%

---

## 4. LLM 辩论层

### 4.1 架构

```
DebateEngine.run_debate(data_context)
  ├── 1) Advocate (看多, temp=0.7)      ← 构建看多论点
  ├── 2) Challenger (看空, temp=0.7)    ← 反驳 + 看空论点
  ├── 3) Auditor (审计, temp=0.2)       ← 验证数据准确性
  └── 4) Arbitrator (仲裁, temp=0.4)    ← 综合裁决
```

**输出**: `DebateResult` (rounds, bull_argument, bear_argument, audit_result, final_verdict)

### 4.2 辩论上下文

辩论输入汇总以下数据:
- 金价 OHLCV + 技术指标摘要
- 交易信号 (类型/得分/置信度/理由)
- Prophet 预测 (方向/均值/区间)
- 宏观指标最新值 (CPI/Fed Rate/M2/VIX 等)
- 新闻情绪 Top 10

### 4.3 已知问题

- `to_summary()` 中 bear 参数打印了 `self.bull_argument`（bug）
- 4 个 Agent 串行执行（可优化为并行）
- 默认模型名 `gpt-5.5` 超前

---

## 5. API 路由层

### 5.1 路由一览

| 路径 | 方法 | 模块 | 说明 |
|------|------|------|------|
| `/` | GET | main | API 欢迎页 |
| `/health` | GET | main | 健康检查 |
| `/stats` | GET | main | 系统统计 |
| `/api/analysis/gold` | GET | analysis | 金价 OHLCV |
| `/api/analysis/indicators` | GET | analysis | 技术指标 |
| `/api/analysis/signal` | GET | analysis | 交易信号 |
| `/api/analysis/predict` | GET | analysis | Prophet 预测 |
| `/api/analysis/macro` | GET | analysis | 宏观指标 |
| `/api/analysis/news` | GET | analysis | 新闻情绪 |
| `/api/analysis/extra` | GET | extra_data | 7 大补充数据 |
| `/api/analysis/calendar` | GET | extra_data | 财经日历 |
| `/api/debate/run` | POST | debate | 运行辩论 |
| `/api/debate/quick` | GET | debate | 快速分析 |
| `/api/backtest/strategies` | GET | backtest | 策略列表 |
| `/api/backtest/run` | GET | backtest | 运行回测 |
| `/ws/{client_id}` | WS | websocket | WebSocket 推送 |

### 5.2 WebSocket 协议

```json
// 客户端 → 服务端
{"type": "subscribe",  "channel": "price|signal|news|debate|system"}
{"type": "unsubscribe", "channel": "..."}
{"type": "ping"}
{"type": "stats"}

// 服务端 → 客户端
{"type": "pong"}
{"type": "price",  "data": {...}, "timestamp": "..."}
{"type": "signal", "data": {...}, "timestamp": "..."}
{"type": "news",   "data": {...}, "timestamp": "..."}
```

### 5.3 定时推送任务

| 任务 | 间隔 | 动作 |
|------|------|------|
| `periodic_price_push` | 60s | 获取金价 → 写 DB → 广播 price 频道 |
| `periodic_signal_push` | 60s | 计算信号 → 写 DB → 广播 signal 频道 |
| `periodic_news_push` | 300s | 获取新闻 → 广播 news 频道 |

---

## 6. 数据库层

### 6.1 ORM 模型 (9 表)

| 表 | 唯一约束 | 关键字段 |
|----|---------|---------|
| `gold_prices` | (date, source) | date, source, open, high, low, close, volume |
| `technical_indicators` | (date, source) | ma5~ma60, rsi14, macd_line/signal/hist, bb_upper/mid/lower, atr14, adx |
| `trade_signals` | (date, source) | signal_type, score, confidence, reasons (JSON), stop_loss, take_profit |
| `predictions` | — | prediction_date, target_date, price_yhat, yhat_lower, yhat_upper |
| `debate_results` | date | bull/bear/audit/final 各字段 (JSON) |
| `backtest_results` | run_date | strategy, total_return, max_drawdown, sharpe_ratio |
| `macro_data` | (date, indicator) | date, indicator, value, source |
| `news_articles` | title | title, link, source, sentiment_score, sentiment_label |
| `system_config` | key | key, value (JSON), description |

### 6.2 upsert 策略

```python
# 通用模式: try insert → 冲突时 update
stmt = insert(Table).values(rows)
stmt = stmt.on_conflict_do_update(
    index_elements=[unique_key],
    set_={...updated fields...}
)
session.execute(stmt)
session.commit()
```

### 6.3 已知问题

- `session.py` 使用同步 engine (`create_engine`)，即使 database_url 含 `+asyncpg` 也不会用异步
- `repository.py` 中字段名 `macd_histogram` vs `IndicatorResult.to_dict()` 的 `macd_hist` 不匹配

---

## 7. 前端仪表盘

### 7.1 页面结构

17 个数据卡片，全部 inline 在 `dashboard/page.tsx`:

| 卡片 | 数据源 | 可视化 |
|------|--------|--------|
| SystemStatusCard | /health, /stats | 状态标签 |
| PriceChartCard | /analysis/gold | Recharts ComposedChart (OHLC + Volume) |
| SignalGaugeCard | /analysis/signal | Gauge + 置信度/止损/止盈 |
| IndicatorGaugeCard | /analysis/indicators | RSI/MACD/BB 三 tab gauge |
| PredictionChartCard | /analysis/predict | AreaChart + 置信区间 |
| MacroCard | /analysis/macro | 实时/官方 tab |
| NewsCard | /analysis/news | 列表 + 情绪标签 |
| DebateCard | /debate/quick | 手动触发 |
| BacktestCard | /backtest/* | 策略选择 + 结果 |
| CentralBankCard | /analysis/extra | 储备排名 |
| CotCard | /analysis/extra | 持仓数据 |
| EtfFlowCard | /analysis/extra | ETF 流量 |
| GeopolCard | /analysis/extra | GPR 指数 |
| FedWatchCard | /analysis/extra | 利率概率 |
| ChinaMacroCard | /analysis/extra | 7 指标 tab |
| AiscCard | /analysis/extra | AISC 成本 |
| CalendarCard | /analysis/calendar | 事件列表 + 下一事件 |

### 7.2 自定义 Hook

```typescript
function useApi<T>(fetcher: () => Promise<T>): {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}
```

### 7.3 已知问题

- `frontend/src/lib/` 目录被根 `.gitignore` 规则 `lib/` 忽略，需 `git add -f` 提交
- 前端 WebSocket 客户端尚未实现

---

## 8. 测试

### 8.1 测试覆盖

26 个 unit test 文件 + 1 个 integration test：

| 测试文件 | 覆盖模块 | 测试数 |
|---------|---------|--------|
| test_gold_price.py | data/gold_price.py | ~10 |
| test_macro.py | data/macro.py | ~10 |
| test_china_macro.py | data/china_macro.py | 10 |
| test_central_bank.py | data/central_bank.py | 6 |
| test_news.py | data/news.py | ~5 |
| test_cot.py | data/cot.py | ~5 |
| test_geopol.py | data/geopol.py | ~5 |
| test_fedwatch.py | data/fed_watch.py | ~5 |
| test_etf_flow.py | data/etf_flow.py | ~5 |
| test_aisc.py | data/aisc.py | ~5 |
| test_cache.py | data/cache.py | ~10 |
| test_indicators.py | quant/indicators.py | ~15 |
| test_signals.py | quant/signals.py | ~10 |
| test_predictor.py | quant/predictor.py | ~5 |
| test_backtest_engine.py | quant/backtest/engine.py | ~5 |
| test_debate_*.py | debate/*.py | ~15 |
| test_api_*.py | api/*.py | ~20 |
| test_extra_api.py | api/extra_data.py | 4 |
| test_config.py | config.py | ~5 |
| test_db_models.py | db/models.py | ~5 |
| test_app.py | integration | ~5 |

**当前状态**: 235 passed / 6 pre-existing failures

### 8.2 预存失败分析

| 测试 | 根因 | 修复难度 |
|------|------|---------|
| test_websocket::test_connect_adds_client | 连接管理测试环境问题 | 中 |
| test_websocket::test_get_stats_format | 同上 | 中 |
| test_config::test_default_values | 配置默认值变更 | 低 |
| test_macro::test_yfinance_raises_exception | mock patch 路径错误 | 低 |
| test_news::test_returns_dataframe_* | RSS 数据源内容变动 | 低 (mock 非网络) |

---

## 9. 已知问题清单

### 9.1 Bug

| # | 文件 | 行 | 问题 | 严重度 |
|---|------|-----|------|--------|
| B1 | debate/engine.py | 56 | `to_summary()` bear 参数打印 `self.bull_argument` | 中 |
| B2 | db/repository.py | 72 | `macd_histogram` vs `macd_hist` 字段名不匹配 | 中 |
| B3 | quant/backtest/engine.py | — | `equity_curve` 始终为空 | 低 |
| B4 | cache.py | 73-74 | 硬编码死代码 (被 glob 覆盖) | 低 |

### 9.2 设计问题

| # | 问题 | 说明 | 建议 |
|---|------|------|------|
| D1 | `_safe_fetch` 修改全局 `cache.cache_ttl` | 非线程安全 | 改为每次调用传参 |
| D2 | 辩论 Agent 串行执行 | 看多/看空可并行 | 用 `asyncio.gather` |
| D3 | Prophet 回归因子未来值用最后一行填充 | 不准确 | 考虑 ARIMA 预测回归因子 |
| D4 | news 接口未走 cache.get | 每次请求都拉 RSS | 添加缓存 |
| D5 | 日志不一致 | 部分模块用 loguru，其余用 logging | 统一标准库 logging |
| D6 | 前端 WS 未实现 | 后端推了前端没消费 | 添加 useWebSocket hook |

### 9.3 功能缺口

| # | 缺口 | 理由 | 状态 |
|---|------|------|------|
| G1 | 真实经济日历 API | 需付费 (~$50/mo) | 已 defer |
| G2 | FRED gold 替代 | yfinance 已覆盖但 macro.py 少 gold | 待解决 |
| G3 | CI 工作流 | 无 GitHub Actions | 待添加 |
| G4 | Integration 测试 | 当前仅 1 个 | 待扩展 |
| G5 | Landing 页 mock 回填 | page.tsx 是静态 mock | 待做 |
| G6 | Docker compose 前端 | 被注释掉了 | 需恢复 |

---

## 10. 路线图

### Phase A — 基础设施完善 (优先级高)
1. 🔲 修复 6 个 pre-existing 测试失败
2. 🔲 添加 CI (GitHub Actions)
3. 🔲 统一日志 (loguru → logging)
4. 🔲 修复 DebateEngine `to_summary()` bug

### Phase B — 数据增强 (优先级中)
1. 🔲 FRED gold 替代 (yfinance GC=F 加入 macro.py FRED 部分)
2. 🔲 日历 mock → 真实 API (探索免费替代: investing.com / ForexFactory)
3. 🔲 Central bank 动态更新机制

### Phase C — 前端完善 (优先级中)
1. 🔲 WebSocket 客户端 hook + 实时更新卡片
2. 🔲 Landing page 数据回填
3. 🔲 Docker compose 恢复前端

### Phase D — 质量提升 (优先级低)
1. 🔲 Integration 测试扩展
2. 🔲 Thread-safe cache TTL
3. 🔲 Parallel debate agents
4. 🔲 Prophet 回归因子改进

---

## 11. 开发者指南

### 11.1 本地开发

```bash
# 安装
pip install -e ".[dev]"

# 启动 (需先设 DATABASE_URL)
DATABASE_URL="sqlite:///./data/gold_agent.db" \
  uvicorn gold_agent.main:app --reload --host 0.0.0.0 --port 8001

# 测试
pytest

# 规范检查
ruff check src/ tests/
```

### 11.2 添加新数据源

1. 在 `src/gold_agent/data/` 下创建 `new_source.py`
2. 实现 `fetch_xxx(**kwargs) -> pd.DataFrame` (try/except 返回空)
3. 在 `extra_data.py` 的 `extra_data_collectors` 字典注册
4. 前端添加对应卡片
5. 添加测试文件

### 11.3 数据库变更

```bash
# PostgreSQL 迁移 (需 Docker)
alembic revision --autogenerate -m "description"
alembic upgrade head

# SQLite 开发模式: 直接改 models.py → app 启动自动 create_all
```

### 11.4 特殊注意事项

- `frontend/src/lib/` 被 `.gitignore` 规则 `lib/` 忽略 → 用 `git add -f`
- `if __name__ == "__main__"` 块用 `uvicorn` CLI，不用 `python src/main.py`
- config 中模型名 `gpt-5.5` 是超前占位，实际可用任何 OpenAI 兼容模型
- Docker compose 有 PostgreSQL + Redis healthcheck，app 启动时等待两者

---

## 12. 附录：目录结构

```
gold-agent/
├── .trellis/                    # Trellis 工作流
│   ├── spec/backend/            # 后端编码规范
│   ├── guides/                  # 思维指南
│   ├── tasks/                   # 任务管理
│   └── workspace/               # 开发者日志
├── src/gold_agent/
│   ├── config.py                # pydantic-settings 配置
│   ├── main.py                  # FastAPI 入口 + lifespan
│   ├── data/                    # 数据采集 (13 个 collector)
│   │   ├── cache.py
│   │   ├── gold_price.py
│   │   ├── macro.py
│   │   ├── china_macro.py
│   │   ├── news.py
│   │   ├── cot.py
│   │   ├── geopol.py
│   │   ├── fed_watch.py
│   │   ├── etf_flow.py
│   │   ├── aisc.py
│   │   ├── central_bank.py
│   │   └── calendar.py
│   ├── quant/                   # 量化分析
│   │   ├── indicators.py
│   │   ├── signals.py
│   │   ├── predictor.py
│   │   └── backtest/engine.py
│   ├── debate/                  # LLM 辩论
│   │   ├── agents.py
│   │   ├── prompts.py
│   │   ├── llm.py
│   │   └── engine.py
│   ├── api/                     # 路由
│   │   ├── analysis.py
│   │   ├── debate.py
│   │   ├── backtest.py
│   │   ├── extra_data.py
│   │   └── websocket.py
│   └── db/                      # 数据库
│       ├── models.py
│       ├── session.py
│       └── repository.py
├── frontend/                    # Next.js 前端
│   └── src/app/
│       ├── page.tsx             # Landing (静态 mock)
│       └── dashboard/
│           └── page.tsx         # 仪表盘 (17 卡片)
├── tests/                       # 测试
│   ├── unit/                    # 26 个文件
│   └── integration/             # 1 个文件
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
└── pyproject.toml
```
