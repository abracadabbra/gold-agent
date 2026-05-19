# Directory Structure

> How backend code is organized in this project.

---

## Overview

The backend follows a flat package layout under `src/gold_agent/`. Each major concern (data collection, quantitative analysis, API, debate) gets its own top-level package. No deep nesting.

---

## Directory Layout

```
src/gold_agent/
├── main.py             # FastAPI entrypoint + lifespan + health/stats endpoints
├── config.py           # pydantic-settings, loaded from .env
├── data/               # Data collection layer
│   ├── cache.py        # 3-tier cache: Redis → Parquet → fetch_fn
│   ├── gold_price.py   # Gold price from yfinance + akshare
│   ├── macro.py        # US macro from yfinance + FRED
│   ├── news.py         # News sentiment from RSS
│   ├── geopol.py       # GPR index from static XLS
│   ├── fed_watch.py    # FedWatch from cme-fedwatch library
│   ├── china_macro.py  # Chinese macro from akshare
│   ├── cot.py          # CFTC COT from cot_reports library
│   ├── etf_flow.py     # Gold ETF flow from WGC XLSX
│   ├── central_bank.py # Central bank reserves from IMF IFS API
│   └── aisc.py         # AISC production cost from WGC XLSX
├── quant/              # Quantitative analysis
│   ├── indicators.py   # Technical indicators (pandas-ta + pure pandas fallback)
│   ├── signals.py      # Trading signal generation (weighted scoring)
│   ├── predictor.py    # Prophet time-series prediction
│   └── backtest/       # Backtesting engine
│       └── engine.py   # Strategy runner + analyzer
├── debate/             # Multi-agent LLM debate
│   ├── roles.py        # Bull/bear/auditor/arbitrator agents
│   └── orchestrator.py # Debate flow controller
├── api/                # FastAPI routers
│   ├── analysis.py     # GET /api/analysis/{gold,indicators,signal,predict,macro,news}
│   ├── extra_data.py   # GET /api/analysis/extra (supplementary data sources)
│   ├── debate.py       # POST /api/debate/run, GET /api/debate/quick
│   ├── backtest.py     # GET /api/backtest/{strategies,run}
│   └── websocket.py    # WS /ws/{client_id} with pub/sub channels
└── db/                 # SQLAlchemy ORM models
    ├── models.py       # 9 tables (gold_prices, signals, predictions, etc.)
    └── __init__.py
```

---

## Module Organization

### Adding a New Data Source

Each data source is a single file in `src/gold_agent/data/` with:

1. One public fetch function: `fetch_xxx(**kwargs) -> pd.DataFrame`
2. The DataFrame must have a `date` column (datetime type)
3. All external calls wrapped in try/except, returning empty DataFrame on failure
4. Accessed via `DataCache.get(key="xxx", fetch_fn=fetch_xxx, **kwargs)`

Then add to the API layer:
1. A new handler in `src/gold_agent/api/extra_data.py` (for supplementary data)
2. Or a new endpoint file for major data categories
3. Register the router in `main.py`
4. Add cache key to `/stats` counter list

### Adding a New API Endpoint

Create a file in `src/gold_agent/api/` with a `router = APIRouter(...)`. Register via `app.include_router(router)` in `main.py`.

---

## Naming Conventions

- Files: `snake_case.py` (matching the single-function pattern)
- Functions: `fetch_xxx()` for data collectors
- API handlers: `get_xxx()` or `post_xxx()`
- Cache keys: `snake_case` matching the data source name (e.g. `gold_intl`, `central_bank_reserves`)
- Router variables: `xxx_router` (e.g. `analysis_router`, `extra_data_router`)

---

## Examples

- `src/gold_agent/data/macro.py` — reference for a well-structured data collector (yfinance + FRED API, DataFrame normalization, error handling)
- `src/gold_agent/data/geopol.py` — simplest data collector (single XLS download, minimal processing)
- `src/gold_agent/api/extra_data.py` — pattern for aggregating multiple data sources with per-source fault isolation
