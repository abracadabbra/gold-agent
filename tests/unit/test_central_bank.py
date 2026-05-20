"""央行黄金储备数据采集单元测试"""

import pandas as pd

from gold_agent.data.central_bank import (
    fetch_central_bank_reserves,
)


class TestFetchCentralBank:
    def test_success(self):
        result = fetch_central_bank_reserves()
        assert not result.empty
        assert "country" in result.columns
        assert "date" in result.columns
        assert "gold_reserves_tonnes" in result.columns
        assert "rank" in result.columns
        assert "country_name" in result.columns
        assert result["country"].iloc[0] == "US"
        assert result["gold_reserves_tonnes"].iloc[0] == 8133.5

    def test_filter_countries(self):
        result = fetch_central_bank_reserves(countries=["CN", "US"])
        assert result["country"].nunique() == 2
        assert set(result["country"].values) == {"CN", "US"}

    def test_ranking(self):
        result = fetch_central_bank_reserves()
        assert result["rank"].iloc[0] == 1
        assert result["rank"].iloc[-1] == result["rank"].max()
        assert result["rank"].is_monotonic_increasing

    def test_column_types(self):
        result = fetch_central_bank_reserves()
        assert result["gold_reserves_tonnes"].dtype == "float64"
        assert result["rank"].dtype == "int64"

    def test_country_name_mapping(self):
        result = fetch_central_bank_reserves(countries=["CN"])
        assert result["country_name"].iloc[0] == "中国"

    def test_date_present(self):
        result = fetch_central_bank_reserves()
        assert result["date"].iloc[0] == pd.Timestamp("2025-05-01")
