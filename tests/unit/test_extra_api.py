"""补充数据 API 端点单元测试"""

from unittest.mock import patch

import pandas as pd

from gold_agent.api.extra_data import get_calendar, get_extra_data


def _mock_df(columns: list[str], rows: int = 3):
    """创建模拟 DataFrame"""
    data = {}
    for col in columns:
        if col == "date":
            data[col] = pd.date_range("2024-01-01", periods=rows, freq="D")
        elif col in ("country", "fund_name", "region", "meeting_date"):
            data[col] = [f"{col}_{i}" for i in range(rows)]
        else:
            data[col] = [float(i + 1) for i in range(rows)]
    return pd.DataFrame(data)


class TestExtraDataAPI:
    """测试 /api/analysis/extra 端点"""

    async def test_all_sources_success(self):
        """所有数据源都成功返回"""
        with patch(
            "gold_agent.api.extra_data.cache.get_with_meta",
            return_value=(
                _mock_df(["date", "value"]),
                {"source_status": "cache", "quality_score": 88, "row_count": 3},
            ),
        ):
            result = await get_extra_data()

            assert "central_bank" in result
            assert "cot" in result
            assert "etf_flow" in result
            assert "geopol" in result
            assert "fedwatch" in result
            assert "china_macro" in result
            assert "aisc" in result
            # Check that non-dict china_macro entries all have ok status
            for key in ("central_bank", "cot", "etf_flow", "geopol", "fedwatch", "aisc"):
                assert result[key]["_status"] == "ok"
                assert result[key]["records"] == 3
                assert result[key]["meta"]["source_status"] == "cache"

    async def test_partial_failure(self):
        """部分数据源失败不影响其他"""
        call_count = [0]

        def mock_cache_get_with_meta(key, fetch_fn, **kwargs):
            call_count[0] += 1
            if key == "geopol":
                raise Exception("Geopol API error")
            return (
                _mock_df(["date", "value"]),
                {"source_status": "cache", "quality_score": 88, "row_count": 3},
            )

        with patch(
            "gold_agent.api.extra_data.cache.get_with_meta",
            side_effect=mock_cache_get_with_meta,
        ):
            result = await get_extra_data()

            assert result["geopol"]["_status"] == "error"
            assert result["geopol"]["meta"]["source_status"] == "unavailable"
            # Other sources should still work
            assert result["central_bank"]["_status"] == "ok"
            assert result["cot"]["_status"] == "ok"

    async def test_empty_dataframes(self):
        """数据源返回空 DataFrame 时正常处理"""
        with patch(
            "gold_agent.api.extra_data.cache.get_with_meta",
            return_value=(
                pd.DataFrame(),
                {"source_status": "unavailable", "quality_score": 0, "row_count": 0},
            ),
        ):
            result = await get_extra_data()

            for key in ("central_bank", "cot", "etf_flow", "geopol", "fedwatch", "aisc"):
                assert result[key]["records"] == 0
                assert result[key]["data"] == []
                assert result[key]["meta"]["quality_score"] == 0

    async def test_china_macro_structure(self):
        """中国宏观数据返回结构正确"""
        with patch(
            "gold_agent.api.extra_data.cache.get_with_meta",
            return_value=(
                _mock_df(["date", "value"]),
                {"source_status": "cache", "quality_score": 88, "row_count": 3},
            ),
        ):
            result = await get_extra_data()

            cm = result["china_macro"]
            for ind in ("cpi", "ppi", "pmi", "m2", "gdp", "lpr", "usd_cny"):
                assert ind in cm
                assert cm[ind]["_status"] == "ok"
                assert cm[ind]["meta"]["quality_score"] == 88

    async def test_china_macro_uses_frequency_specific_stale_windows(self):
        calls: list[dict] = []

        def mock_cache_get_with_meta(key, fetch_fn, **kwargs):
            calls.append({"key": key, **kwargs})
            return _mock_df(["date", "value"]), {
                "source_status": "cache",
                "quality_score": 88,
                "row_count": 3,
            }

        with patch(
            "gold_agent.api.extra_data.cache.get_with_meta",
            side_effect=mock_cache_get_with_meta,
        ):
            await get_extra_data()

        by_key = {call["key"]: call for call in calls}
        assert by_key["china_cpi"]["expected_frequency"] == "monthly"
        assert by_key["china_cpi"]["max_stale_days"] == 32
        assert by_key["china_gdp"]["expected_frequency"] == "quarterly"
        assert by_key["china_gdp"]["max_stale_days"] == 94
        assert by_key["china_usd_cny"]["expected_frequency"] == "daily"
        assert by_key["china_usd_cny"]["max_stale_days"] == 2


class TestCalendarAPI:
    """测试 /api/analysis/calendar 端点"""

    async def test_calendar_with_date_range(self):
        """calendar 端点同时传递 start_date 和 end_date（覆盖 line 119）"""
        with patch("gold_agent.api.extra_data.fetch_calendar") as mock_fc:
            mock_fc.return_value = _mock_df(["date", "event", "importance"])
            result = await get_calendar(start_date="2026-01-01", end_date="2026-12-31")
            assert result["records"] > 0
            assert result["meta"]["row_count"] == result["records"]
            mock_fc.assert_called_once_with("2026-01-01", "2026-12-31")

    async def test_calendar_error_returns_empty(self):
        """calendar 端点异常时返回错误结构（覆盖 lines 136-138）"""
        with patch("gold_agent.api.extra_data.fetch_calendar") as mock_fc:
            mock_fc.side_effect = Exception("Calendar API error")
            result = await get_calendar(start_date="2026-01-01", end_date="2026-12-31")
            assert result["records"] == 0
            assert result["next_event"] is None
            assert result["data"] == []
            assert "error" in result
            assert result["meta"]["source_status"] == "unavailable"
