# Error Handling

> How errors are handled in this project.

---

## Overview

<!--
Document your project's error handling conventions here.

Questions to answer:
- What error types do you define?
- How are errors propagated?
- How are errors logged?
- How are errors returned to clients?
-->

(To be filled by the team)

---

## Error Types

<!-- Custom error classes/types -->

(To be filled by the team)

---

## Error Handling Patterns

<!-- Try-catch patterns, error propagation -->

(To be filled by the team)

---

## API Error Responses

<!-- Standard error response format -->

(To be filled by the team)

---

## Data Source Resilience

External data sources are fragile. Always plan for fallbacks.

| Source | Issue | Solution |
|--------|-------|----------|
| FRED gold series (GOLDAMGBD228NLBM) | Series removed from FRED as of 2025 | Use yfinance gold price (`GC=F` or XAUUSD=x) instead |
| IMF SDMX API (dataservices.imf.org) | API decommissioned (NXDOMAIN) | Use static snapshot data for central bank reserves |
| Kitco RSS feed | 404 / discontinued | Replaced with mining.com/feed |
| akshare fx_spot_quote() | No date column (real-time snapshot) | Use dedicated `fetch_china_fx()` with try/except, returns empty on failure |

**Pattern**: every data collector `fetch_xxx(**kwargs) -> pd.DataFrame` wraps in try/except, returns empty DataFrame on failure. Called via `DataCache.get()` for TTL-based caching.

## Common Mistakes

<!-- Error handling mistakes your team has made -->

(To be filled by the team)
