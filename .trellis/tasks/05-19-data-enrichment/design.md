# Technical Design: 新增金价报告数据源

## Architecture

### Data Layer — 新增文件

```
src/gold_agent/data/
├── cache.py              # 已有，复用
├── central_bank.py       # [NEW] 央行储备 (IMF IFS API)
├── cot.py                # [NEW] CFTC COT (cot_reports)
├── etf_flow.py           # [NEW] ETF 流量 (WGC XLSX)
├── geopol.py             # [NEW] GPR 指数 (静态 XLS)
├── fed_watch.py          # [NEW] FedWatch (cme-fedwatch)
├── china_macro.py        # [NEW] 中国宏观 (akshare)
├── aisc.py               # [NEW] 生产成本 (WGC XLSX)
```

### API Layer — 新增端点

```
src/gold_agent/api/
├── analysis.py     # 已有
├── extra_data.py   # [NEW] GET /api/analysis/extra — 聚合 7 类数据
```

- `main.py` 注册新 router
- `/stats` 端点新增 cache key 计数

### Frontend — 新增展示

```
frontend/src/lib/
├── types.py                # [MODIFY] 新增 7 个 Response 接口
├── api.ts                  # [MODIFY] 新增 api.extraData() 方法

frontend/src/app/dashboard/
├── page.tsx                # [MODIFY] 新增引用 + 布局
├── CentralBankCard.tsx     # [NEW] 央行储备卡片
├── CotCard.tsx             # [NEW] COT 持仓卡片
├── EtfFlowCard.tsx         # [NEW] ETF 流量卡片
├── GeopolCard.tsx          # [NEW] GPR 指数卡片
├── FedWatchCard.tsx        # [NEW] FedWatch 卡片
├── ChinaMacroCard.tsx      # [NEW] 中国宏观卡片
├── AiscCard.tsx            # [NEW] 生产成本卡片
```

### Data Flow

```
fetch_xxx(**kwargs)
  → 调用外部 API / 库 / 文件下载
  → 返回 pd.DataFrame(columns=[...])

DataCache.get(key="xxx", fetch_fn=fetch_xxx, **kwargs)
  → Redis TTL → Parquet → fetch_fn
  → 返回 pd.DataFrame

GET /api/analysis/extra
  → 并行调用多个 cache.get()
  → 聚合 JSON 返回

Frontend api.extraData()
  → 渲染各卡片组件
```

## Data Specification

### 1. Central Bank Reserves

```python
# fetch function
def fetch_central_bank_reserves(
    countries: list[str] | None = None,
    start_year: int = 2020,
) -> pd.DataFrame:
    """
    Returns columns: country, date, gold_reserves_tonnes, gold_reserves_usd, rank
    Source: IMF IFS REST API (http://dataservices.imf.org)
    API: no key required, SDMX JSON format
    """

# cache key: "central_bank_reserves"
# TTL: 7 days (monthly data)
```

IMPORTANT: The IMF IFS SDMX API path for gold reserves data. Need to identify the right dataflow. IFS dataflow ID is typically `IFS`. The gold reserves measure code could be `FID` (Foreign International Depository - Gold) or similar.

### 2. CFTC COT

```python
def fetch_cot(
    year: int | None = None,
) -> pd.DataFrame:
    """
    Returns columns: date, exchange, commodity, open_interest, 
                     producer_long, producer_short, 
                     swap_long, swap_short,
                     managed_money_long, managed_money_short,
                     other_long, other_short
    Source: cot_reports library
    COMEX Gold market code: 088691
    """

# cache key: "cot"
# TTL: 1 day (weekly data, updated Friday)
```

Library: `cot_reports`

```python
from cot_reports import cot
cot.cot_year(year=2024, cot_report_type='legacy_fut')
```

### 3. ETF Flow

```python
def fetch_etf_flow(
    months: int = 12,
) -> pd.DataFrame:
    """
    Returns columns: date, fund_name, region, holdings_tonnes, 
                     flow_tonnes, flow_usd, aum_usd
    Source: WGC Goldhub XLSX download
    """

# cache key: "etf_flow"
# TTL: 7 days (monthly data)
```

Download URL from WGC: Need to find the actual download link pattern. Might be from `https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows`.

### 4. GPR Index

```python
def fetch_geopol(
    variant: str = "global",
) -> pd.DataFrame:
    """
    Returns columns: date, gpr_index, gpr_threats, gpr_acts
                     (plus country-specific if variant != "global")
    Source: https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls
    """

# cache key: "geopol"
# TTL: 1 day
```

### 5. FedWatch

```python
def fetch_fedwatch() -> pd.DataFrame:
    """
    Returns columns: meeting_date, current_rate, 
                     cut_prob, hold_prob, hike_prob
    Source: cme-fedwatch library
    """

# cache key: "fedwatch"
# TTL: 6 hours
```

Library: `cme-fedwatch`

```python
from cme_fedwatch import get_probabilities
data = get_probabilities("next")
```

### 6. China Macro

```python
def fetch_china_macro(
    indicators: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Returns dict of DataFrames, keyed by indicator name.
    Available indicators: cpi, ppi, pmi, m2, gdp, lpr, usd_cny
    
    Each DataFrame columns: date, value (and unit where applicable)
    Source: akshare (already installed)
    """

# cache keys: "china_cpi", "china_ppi", "china_pmi", etc.
# TTL: 7 days (monthly data)
```

akshare function mapping:
| 数据 | akshare 函数 |
|------|-------------|
| CPI | `ak.macro_china_cpi()` |
| PPI | `ak.macro_china_producer_price_index()` |
| PMI | `ak.macro_china_pmi()` |
| M2 | `ak.macro_china_money_supply()` |
| GDP | `ak.macro_china_gdp()` |
| LPR | `ak.bond_zh_lpr()` |
| USD/CNY | `ak.fx_spot_quote()` |

### 7. AISC

```python
def fetch_aisc() -> pd.DataFrame:
    """
    Returns columns: year, quarter, global_avg_aisc, region, note
    Source: WGC Goldhub XLSX download (quarterly)
    """

# cache key: "aisc"
# TTL: 30 days (quarterly data)
```

## API Response Format

`GET /api/analysis/extra` returns:

```json
{
  "central_bank": { "records": 10, "data": [...] },
  "cot": { "records": 52, "latest": {...}, "data": [...] },
  "etf_flow": { "records": 12, "latest_month": "...", "data": [...] },
  "geopol": { "records": 200, "latest": {...}, "data": [...] },
  "fedwatch": { "next_meeting": "2026-06-17", "probabilities": {...}, "raw": [...] },
  "china_macro": { "cpi": { "records": 60, "latest": ... }, "pmi": {...}, ... },
  "aisc": { "records": 20, "latest": {...}, "data": [...] }
}
```

## Cache TTL Strategy

| Data | Frequency | Redis TTL | Parquet Keep |
|------|-----------|-----------|-------------|
| central_bank | Monthly | 7 days | 5 years |
| cot | Weekly (Fri) | 1 day | 2 years |
| etf_flow | Monthly | 7 days | 3 years |
| geopol | Weekly | 1 day | 5 years |
| fedwatch | Daily | 6 hours | 1 year |
| china_macro | Monthly | 7 days | 5 years |
| aisc | Quarterly | 30 days | 10 years |

## Error Handling

- 外部 API 超时 → 静默降级，返回空 DataFrame
- 文件下载失败 → 依赖 Parquet 缓存兜底
- 数据格式变更 → 抛出明确错误日志 + 不影响其他数据源
- 每个 fetcher 独立 try/except，一个数据源失败不影响其他

## Dependencies to Install

```toml
[project.optional-dependencies]
dev = [
    "cot-reports",    # CFTC COT
    "cme-fedwatch",   # FedWatch
]
```

Or add to `[project.dependencies]` if not optional.
