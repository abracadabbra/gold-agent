# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (Python)
```bash
pip install -e ".[dev]"           # install with dev deps
uvicorn gold_agent.main:app --reload --host 0.0.0.0 --port 8000  # dev server
pytest                            # run all tests (asyncio_mode=auto)
pytest tests/unit/test_indicators.py  # single test file
ruff check src/ tests/            # lint (line-length=100, target py312)
mypy src/                         # type check
```

### Frontend (Next.js)
```bash
cd frontend
npm run dev       # dev server (port 3000)
npm run build     # production build (run this to verify changes, NOT from project root)
npm run lint      # eslint
```

**Important**: Frontend commands must be run from `frontend/` directory, not the project root.

### Docker
```bash
docker-compose up -d              # full stack: app + PostgreSQL + Redis + frontend
docker-compose logs -f app        # view backend logs
```

## Architecture

**Gold AI** is a gold market analysis platform with an LLM-powered debate engine as its core differentiator.

### Data Flow
```
External APIs → DataCache (Redis 5min → Parquet monthly → live fetch)
    → Quant analysis (indicators, signals, prediction)
    → LLM debate (4 agents: bull/bear/auditor/arbitrator)
    → REST/WebSocket → Next.js frontend
```

### Backend (`src/gold_agent/`)
- **Entrypoint**: `gold_agent.main:app` (FastAPI with async lifespan)
- **Config**: `gold_agent.config.settings` — Pydantic BaseSettings from `.env`
- **Data layer** (`data/`): 11 collectors — gold_price, macro, news, china_macro, central_bank, cot, etf_flow, fed_watch, geopol, aisc, calendar
- **Cache** (`data/cache.py`): 2-tier — Redis (hot, 5min TTL) then Parquet (cold, monthly partitions). Pattern: `cache.get(key="gold_intl", fetch_fn=fetch_gold_price, source="intl", period="1y")`
- **Quant** (`quant/`): `indicators.py` (18 technical indicators, pandas-ta with pure-pandas fallback), `signals.py` (multi-indicator scoring -100 to +100), `predictor.py` (Prophet forecasting), `backtest/engine.py` (backtrader wrapper)
- **Debate** (`debate/`): 4-round sequential LLM debate — bull → bear → auditor → arbitrator. Each round feeds previous outputs as context. SSE streaming via `stream_debate()`
- **API** (`api/`): 4 routers — `/api/analysis` (gold, indicators, signal, predict, macro, news), `/api/debate` (run, stream, quick), `/api/backtest` (strategies, run), `/api/analysis/extra` (13 supplementary data sources)
- **WebSocket** (`api/websocket.py`): `/ws/{client_id}`, pub/sub channels (price, signal, news, debate, system), background periodic push tasks
- **Database** (`db/`): 9 SQLAlchemy ORM tables, sync sessions despite async FastAPI

### Frontend (`frontend/`)
- **Framework**: Next.js 16.2.6 (App Router), React 19, TypeScript 5, Tailwind CSS 4
- **Pages**: `page.tsx` (report/landing), `dashboard/page.tsx` (full data dashboard with 17+ cards)
- **State**: No external state lib — hooks only. Custom `useApi` hook in `shared.tsx`. `api.ts` client has 5-min response cache + request deduplication
- **Charts**: `lightweight-charts` (TradingView) for candlestick, `recharts` for other visualizations
- **All pages are `'use client'`** — no SSR data fetching

### Key API Routes
| Route | Purpose |
|-------|---------|
| `GET /api/analysis/gold?source=intl&period=1y` | Gold price OHLCV data |
| `GET /api/analysis/indicators?source=intl` | Technical indicators |
| `GET /api/analysis/signal` | Trade signal (-100 to +100) |
| `GET /api/analysis/predict?days=7` | Prophet price prediction |
| `GET /api/analysis/macro` | Macro data (yfinance + FRED) |
| `GET /api/analysis/news` | News sentiment |
| `GET /api/analysis/extra` | 13 supplementary data sources |
| `POST /api/debate/run` | Full 4-agent debate |
| `GET /api/debate/run/stream` | SSE streaming debate |
| `GET /api/debate/quick` | Quick signal without debate |
| `GET /api/backtest/run?strategy=golden_cross` | Run backtest |
| `WS /ws/{client_id}` | Real-time WebSocket |

## Conventions

- **Python version**: >= 3.12 (hatchling build, src/ layout)
- **Logging**: mixed — `loguru` in `quant/indicators.py`, stdlib `logging` elsewhere
- **Imports**: full path (`gold_agent.quant.indicators import ...`), no re-exports in `__init__.py`
- **Data collectors**: all follow `def fetch_xxx(**kwargs) -> pd.DataFrame`, returning empty DataFrame on failure
- **Debate agent models**: each role has a separate model configurable in `.env` (bull, bear, auditor, arbitrator)
- **Frontend API base**: `NEXT_PUBLIC_API_BASE` env var (defaults to `http://localhost:8000`)

## Quirks

- `main.py` — use `uvicorn` CLI, not `python src/gold_agent/main.py`
- `/stats` endpoint has placeholder text (not wired to real metrics) — keep as-is unless explicitly changing
- `pandas-ta` is optional — code has pure-pandas fallback in `indicators.py`
- Docker compose has PostgreSQL + Redis healthchecks; app waits on both
- Database defaults to SQLite locally, PostgreSQL in Docker/production
- Session management is synchronous SQLAlchemy despite async FastAPI
- **Next.js 16 has breaking changes** — frontend `AGENTS.md` warns to read `node_modules/next/dist/docs/` before writing Next.js code
