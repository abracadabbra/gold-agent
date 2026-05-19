# Implementation Plan: 新增金价报告数据源

## Order of Execution

### Phase 1: Backend — Data Collectors (7 files)

Each file in `src/gold_agent/data/`, one per data source.

**1.1 `geopol.py` — GPR Index (Trivial)**
- [ ] Add `fetch_geopol()` → `pd.read_excel(url)` on `https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls`
- [ ] Normalize columns, add `date` column, sort
- [ ] Verify: `DataCache.get(key="geopol", fetch_fn=fetch_geopol)` returns data

**1.2 `fed_watch.py` — FedWatch (Easy)**
- [ ] Install `cme-fedwatch`
- [ ] Add `fetch_fedwatch()` → call `get_probabilities()`
- [ ] Parse nested dict into flat DataFrame
- [ ] Verify: `DataCache.get(key="fedwatch", fetch_fn=fetch_fedwatch)` returns data

**1.3 `china_macro.py` — Chinese Macro (Easy)**
- [ ] Add `fetch_china_cpi()` → `ak.macro_china_cpi()`
- [ ] Add `fetch_china_ppi()` → `ak.macro_china_producer_price_index()`
- [ ] Add `fetch_china_pmi()` → `ak.macro_china_pmi()`
- [ ] Add `fetch_china_m2()` → `ak.macro_china_money_supply()`
- [ ] Add `fetch_china_gdp()` → `ak.macro_china_gdp()`
- [ ] Add `fetch_china_lpr()` → `ak.bond_zh_lpr()`
- [ ] Add `fetch_china_fx()` → `ak.fx_spot_quote()`
- [ ] Add unified `fetch_all_china_macro()` → calls all above, caches per-key
- [ ] Verify each key via `DataCache.get()`

**1.4 `cot.py` — CFTC COT (Easy)**
- [ ] Install `cot-reports`
- [ ] Add `fetch_cot()` → `cot.cot_year()` filtered to gold market code `088691`
- [ ] Normalize columns to English names
- [ ] Verify via `DataCache.get()` with TTL=86400

**1.5 `etf_flow.py` — ETF Flow (Medium)**
- [ ] WGC XLSX download: find the direct download URL from WGC Goldhub
- [ ] Add `fetch_etf_flow()` → download XLSX → parse with pandas
- [ ] Handle login wall if needed (may need requests session)
- [ ] Fall back to yfinance `GLD` / `IAU` daily holding estimates
- [ ] Verify via `DataCache.get()`

**1.6 `central_bank.py` — Central Bank Reserves (Medium)**
- [ ] Implement IMF IFS SDMX REST API caller
- [ ] Identify correct dataflow and gold reserve series codes
- [ ] Parse SDMX JSON → flat DataFrame (country, date, tonnes, usd)
- [ ] Add TOP10 country filter
- [ ] Verify via `DataCache.get()`

**1.7 `aisc.py` — AISC (Medium)**
- [ ] WGC XLSX download: find the production cost data URL
- [ ] Add `fetch_aisc()` → download → parse
- [ ] Verify via `DataCache.get()`

### Phase 2: Backend — API + Config

**2.1 Install dependencies**
- [ ] `pip install cot-reports cme-fedwatch`
- [ ] Add to `pyproject.toml` (dev deps or main deps)
- [ ] Run `pip install -e ".[dev]"` to sync

**2.2 API endpoint**
- [ ] Create `src/gold_agent/api/extra_data.py`
- [ ] Add `GET /api/analysis/extra` → parallel fetch all 7 sources
- [ ] Handle partial failures (one data source error doesn't break others)
- [ ] Return unified JSON response

**2.3 Register in main.py**
- [ ] Import `extra_data_router` in `main.py`
- [ ] `app.include_router(extra_data_router)`
- [ ] Update `/stats` endpoint cache key counts for new data types

### Phase 3: Frontend

**3.1 Types**
- [ ] Add `CentralBankResponse`, `CotResponse`, `EtfFlowResponse`, `GeopolResponse`, `FedWatchResponse`, `ChinaMacroResponse`, `AiscResponse`, `ExtraDataResponse` in `types.ts`

**3.2 API client**
- [ ] Add `api.extraData()` → `fetchJson<ExtraDataResponse>('/api/analysis/extra')`

**3.3 Dashboard cards**
- [ ] Create `CentralBankCard.tsx`
- [ ] Create `CotCard.tsx`
- [ ] Create `EtfFlowCard.tsx`
- [ ] Create `GeopolCard.tsx`
- [ ] Create `FedWatchCard.tsx`
- [ ] Create `ChinaMacroCard.tsx`
- [ ] Create `AiscCard.tsx`
- [ ] Add all cards to `page.tsx` layout grid

**3.4 Verify**
- [ ] `npm run lint` passes
- [ ] All cards render with real data

### Phase 4: Tests & Quality

**4.1 Unit tests**
- [ ] `tests/unit/test_geopol.py` — mock `pd.read_excel`
- [ ] `tests/unit/test_fedwatch.py` — mock `get_probabilities`
- [ ] `tests/unit/test_cot.py` — mock `cot.cot_year`
- [ ] `tests/unit/test_china_macro.py` — mock akshare calls
- [ ] `tests/unit/test_etf_flow.py` — mock download
- [ ] `tests/unit/test_central_bank.py` — mock requests
- [ ] `tests/unit/test_aisc.py` — mock download
- [ ] `tests/unit/test_extra_api.py` — mock cache.get, verify API response shape

**4.2 Quality checks**
- [ ] `ruff check src/ tests/`
- [ ] `mypy src/`
- [ ] `pytest`

## Validation Commands

```bash
# Backend
cd /Users/shentao/IdeaProjects/gold-agent
ruff check src/gold_agent/data/geopol.py
mypy src/gold_agent/data/geopol.py
pytest tests/ -v -k "geopol or fedwatch or cot or china or etf or central or aisc or extra"

# Frontend
cd /Users/shentao/IdeaProjects/gold-agent/frontend
npm run lint

# Full stack
cd /Users/shentao/IdeaProjects/gold-agent
ruff check src/ tests/
mypy src/
pytest
```

## Rollback Points

- Phase 1.1-1.3: simple rollback, just remove one file
- Phase 2: if API changes cause other failures, revert extra_data.py + main.py router registration
- Phase 3: if frontend breaks, revert dashboard page.tsx to previous version

## Total Estimated Size

- Backend: ~600 lines (7 data files + 1 API file)
- Frontend: ~500 lines (types + api + 7 card components)
- Tests: ~400 lines
