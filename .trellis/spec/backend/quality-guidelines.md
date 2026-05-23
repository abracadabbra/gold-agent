# Quality Guidelines

> Code quality standards for backend development.

---

## Required Patterns

### Data Collector Pattern

Every data collector in `src/gold_agent/data/` must follow:

```python
def fetch_xxx(param1: str = "default", param2: int = 10) -> pd.DataFrame:
    """One-line description of what this fetches.

    Source: <data source name>
    Frequency: <daily/weekly/monthly>
    """
    try:
        # Fetch data from external source
        data = some_library_or_api.call()
        result = pd.DataFrame(data)

        if result.empty:
            logger.warning("xxx fetch returned empty data")
            return result

        # Ensure 'date' column exists and is datetime
        if "date" not in result.columns:
            # Find date-like column and rename
            ...

        result["date"] = pd.to_datetime(result["date"])
        result = result.sort_values("date").reset_index(drop=True)
        logger.info(f"xxx fetched: {len(result)} rows")
        return result

    except Exception as e:
        logger.error(f"xxx fetch failed: {e}")
        return pd.DataFrame()  # Never raise — caller handles empty gracefully
```

### Cache Integration

All data collectors must be called via `DataCache`:

```python
from gold_agent.data.cache import cache

df = cache.get(
    key="xxx",              # snake_case cache key
    fetch_fn=fetch_xxx,     # the fetch function (not called directly)
    param1="value",
)
```

### Cross-Layer Data Flow

```
data/xxx.py:  fetch_xxx() -> pd.DataFrame
       ↓
cache.py:     DataCache.get(key="xxx", fetch_fn=fetch_xxx)
       ↓
api/*.py:     GET /api/... -> calls cache.get() -> returns JSON
       ↓
frontend:     api.xxx() -> renders card
```

### Domestic Source Whitelist (Cross-Layer Contract)

The `DOMESTIC_SOURCES` list in `news.py` and the `DOMESTIC_SOURCES` array in `page.tsx` must be kept in sync. When adding a new domestic RSS feed:

1. Add the feed to `RSS_FEEDS` in `news.py` with a domestic source name
2. Add that source name to `DOMESTIC_SOURCES` in `news.py`
3. Add the same source name to `DOMESTIC_SOURCES` in `frontend/src/app/page.tsx`

The frontend uses this whitelist to split news into domestic/foreign display sections.

### Per-Source Fault Isolation

In API endpoints that aggregate multiple data sources, each source must be wrapped in its own try/except:

```python
results = {}
for key, fetch_fn in sources.items():
    try:
        cache.cache_ttl = TTL_MAP[key]
        results[key] = cache.get(key=key, fetch_fn=fetch_fn)
    except Exception as e:
        logger.error(f"{key} failed: {e}")
        results[key] = pd.DataFrame()
    finally:
        cache.cache_ttl = 300  # restore default
```

---

## Testing Requirements

### Data Collector Tests

Every `fetch_xxx()` function must have unit tests:

- **Happy path**: Mock the external call, verify DataFrame shape and columns
- **Empty response**: Mock returns empty → verify function returns empty DataFrame
- **Exception handling**: Mock raises → verify function returns empty DataFrame (not raises)
- **Date normalization**: Verify `date` column exists and is datetime type

```python
@patch("gold_agent.data.xxx.some_library_function")
def test_fetch_xxx_success(mock_fn):
    mock_fn.return_value = [...]
    df = fetch_xxx()
    assert not df.empty
    assert "date" in df.columns
    assert df["date"].dtype == "datetime64[ns]"
```

### API Endpoint Tests

Test the aggregation endpoint with mocked cache:

```python
@patch("gold_agent.api.xxx.cache.get")
def test_extra_api_partial_failure(mock_cache):
    """One failing source shouldn't break the whole response"""
    mock_cache.side_effect = [pd.DataFrame(...), Exception(), pd.DataFrame(...)]
    # ... verify response still returns successfully
```

---

## Forbidden Patterns

1. **Directly calling fetch functions** — always go through `DataCache.get()` to benefit from caching
2. **Raising exceptions from fetch functions** — return empty DataFrame instead; let the caller decide severity
3. **Hardcoded TTL in data files** — TTL should be set at the API layer, not in the data collector
4. **Web scraping HTML** — prefer pip libraries, official APIs, or structured file downloads
5. **Deep nesting** — keep data files flat (one file = one data source)

---

## Code Review Checklist

- [ ] Does the data collector return `pd.DataFrame` with a `date` column?
- [ ] Are all external calls wrapped in try/except returning empty DataFrame?
- [ ] Is the cache key unique and consistent between data file and API layer?
- [ ] Are new cache keys added to the `/stats` endpoint counter?
- [ ] Are new API routers registered in `main.py`?
- [ ] Do frontend types match the API response shape?
- [ ] Do tests cover happy path, empty response, and exception cases?
- [ ] Ruff and mypy pass without new errors?
