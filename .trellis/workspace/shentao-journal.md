
## 2026-05-22 — SSE streaming debate

### Changes
- **`debate/engine.py`**: Added `stream_debate()` async generator yielding `(stage_name, round)` per stage
- **`api/debate.py`**: New `GET /api/debate/run/stream` SSE endpoint pushing bull→bear→audit→verdict→complete events
- **`frontend/page.tsx`**: `DebateCard` uses `EventSource` for progressive display — stage progress bar + instant CollapseSection expansion per completed stage
- **`frontend/page.tsx`**: `BacktestCard` added `TitleWithHelp` + full-width layout (`md:col-span-2 xl:col-span-3`)

### Verified
- SSE streams correctly: 5 events (4 stage + 1 complete), each sends immediately after LLM call
- Ruff: 0 errors
- Frontend build: 0 new errors (pre-existing `signal_type` type error unchanged)
- All 4 stages complete, final `complete` event includes full debate result

### Commit
`d8cc820 feat(debate): SSE streaming debate with real-time per-stage display`
