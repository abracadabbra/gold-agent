"""补充数据 API 端点单元测试"""

from unittest.mock import patch

import pandas as pd

from gold_agent.api.extra_data import get_extra_data


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
        with patch("gold_agent.api.extra_data.cache.get",
                   return_value=_mock_df(["date", "value"])):
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

    async def test_partial_failure(self):
        """部分数据源失败不影响其他"""
        call_count = [0]

        def mock_cache_get(key, fetch_fn, **kwargs):
            call_count[0] += 1
            if key == "geopol":
                raise Exception("Geopol API error")
            return _mock_df(["date", "value"])

        with patch("gold_agent.api.extra_data.cache.get", side_effect=mock_cache_get):
            result = await get_extra_data()

            assert result["geopol"]["_status"] == "error"
            # Other sources should still work
            assert result["central_bank"]["_status"] == "ok"
            assert result["cot"]["_status"] == "ok"

    async def test_empty_dataframes(self):
        """数据源返回空 DataFrame 时正常处理"""
        with patch("gold_agent.api.extra_data.cache.get", return_value=pd.DataFrame()):
            result = await get_extra_data()

            for key in ("central_bank", "cot", "etf_flow", "geopol", "fedwatch", "aisc"):
                assert result[key]["records"] == 0
                assert result[key]["data"] == []

    async def test_china_macro_structure(self):
        """中国宏观数据返回结构正确"""
        with patch("gold_agent.api.extra_data.cache.get",
                   return_value=_mock_df(["date", "value"])):
            result = await get_extra_data()

            cm = result["china_macro"]
            for ind in ("cpi", "ppi", "pmi", "m2", "gdp", "lpr", "usd_cny"):
                assert ind in cm
                assert cm[ind]["_status"] == "ok"
