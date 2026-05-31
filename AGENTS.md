# GoldAgent - Agent Instructions

## Quick start
```bash
pip install -e ".[dev]"           # install + dev deps
uvicorn gold_agent.main:app --reload --host 0.0.0.0 --port 8001  # dev server
pytest                            # run tests (asyncio_mode=auto)
ruff check src/ tests/            # lint (line-length=100)
mypy src/                         # typecheck
docker-compose up -d              # full stack (app + postgres + redis)
```

## Package layout
- `src/gold_agent/` — main package (hatchling build, `src/` layout)
- `gold_agent.main:app` — FastAPI entrypoint
- `gold_agent.config` — pydantic-settings, loaded from `.env`
- `gold_agent.data.*` — data collection (yfinance, akshare, FRED, RSS)
- `gold_agent.quant.*` — indicators, signals, Prophet prediction, backtesting
- `gold_agent.debate.*` — multi-agent LLM debate (bull/bear/auditor/arbitrator)
- `gold_agent.api.*` — FastAPI routers (analysis, debate, backtest, websocket)
- `gold_agent.db.models` — SQLAlchemy ORM models (9 tables)
- `tests/unit/` — pytest tests, async mode on by default

## Conventions
- **Logging**: mixed — `loguru` in `quant/indicators.py`, stdlib `logging` elsewhere
- **Imports**: full path (`gold_agent.quant.indicators import ...`), no re-exports in `__init__.py`
- **`pandas-ta`**: optional dependency — code has pure-pandas fallback in `indicators.py`
- **Caching**: 3-tier — Redis (5min TTL) → Parquet (monthly partitions) → live fetch
- **Cache pattern**: `cache.get(key="gold_intl", fetch_fn=fetch_gold_price, source="intl", period="1y")`
- **Debate**: each role has a separate model configurable in `.env` (gpt-4.1 / claude-sonnet-4 / gpt-4.1-mini)
- **WebSocket**: `/ws/{client_id}`, subscribe/ping channels, `ConnectionManager` singleton

## Important quirks
- `main.py:122` — `if __name__ == "__main__"` block: use `uvicorn` CLI, not `python src/gold_agent/main.py`
- `/stats` endpoint has placeholder text (not wired to real metrics) — keep as-is unless explicitly changing
- `tests/unit/` covers all 31 source files (100%), 333 tests total
- Docker compose has PostgreSQL + Redis healthchecks; app waits on both
- No CI workflows configured

## Frontend (Next.js 16 + React 19)
- Source: `frontend/src/app/dashboard/`
- Tests: `frontend/src/__tests__/`, Jest 30 + `@testing-library/react`
- Run: `cd frontend && npm test` (39 tests)
- Config: `frontend/jest.config.js` (uses `next/jest` transformer)
- Path alias `@/` maps to `src/` — keep `moduleNameMapper` in sync with `tsconfig.json`
- Test naming: `*.test.ts` or `*.test.tsx` in `src/__tests__/`

<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->
