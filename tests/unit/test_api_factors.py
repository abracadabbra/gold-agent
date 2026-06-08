"""关键因子聚合接口测试"""

from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from gold_agent.data.cot import cot_cache_key
from gold_agent.data.macro import macro_fred_cache_key
from gold_agent.main import app

client = TestClient(app)


def _meta(row_count: int, source_status: str = "cache") -> dict:
    return {
        "as_of": "2024-01-03T00:00:00",
        "latest_date": "2024-01-03T00:00:00",
        "fetched_at": "2024-01-03T08:00:00+00:00",
        "row_count": row_count,
        "stale": False,
        "source_status": source_status,
        "missing_rate": 0.0,
        "quality_score": 100,
        "expected_frequency": "daily",
    }


def _fake_cot():
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3, freq="W"),
        "exchange": ["COMEX"] * 3,
        "open_interest": [500000] * 3,
        "managed_money_long": [250000.0, 260000.0, 270000.0],
        "managed_money_short": [100000.0, 95000.0, 90000.0],
        "producer_long": [150000] * 3,
        "producer_short": [200000] * 3,
    })


def _fake_fedwatch():
    return pd.DataFrame({
        "meeting_date": ["2024-12-18"],
        "rate": ["4.25-4.50"],
        "hike_probability": [0.05],
        "cut_probability": [0.70],
        "no_change_probability": [0.25],
        "date": [pd.Timestamp("2024-12-01")],
    })


def _fake_cb():
    return pd.DataFrame({
        "country": ["美国", "德国", "法国", "美国", "德国", "法国"],
        "gold_reserves_tonnes": [100.0, 90.0, 80.0, 110.0, 95.0, 85.0],
        "date": [pd.Timestamp("2024-01-01")] * 3 + [pd.Timestamp("2024-01-06")] * 3,
    })


def _fake_fred():
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3, freq="D"),
        "tips_yield": [1.8, 1.5, 0.3],
        "fed_rate": [5.5] * 3,
    })


def _fake_yfinance():
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3, freq="D"),
        "usd_index": [104.5, 105.0, 103.8],
        "vix": [15.0] * 3,
        "us_10y": [4.5] * 3,
    })


class TestFactors:
    """关键因子端点"""

    def test_factors_all_data(self):
        """所有数据源正常时返回完整因子"""

        def mock_cache_get_with_meta(key, **kwargs):
            if key == cot_cache_key(2026):
                return _fake_cot(), _meta(3)
            if key == "fedwatch":
                return _fake_fedwatch(), _meta(1)
            if key == "central_bank_reserves":
                return _fake_cb(), _meta(6)
            if key == macro_fred_cache_key(start_date="2024-01-01"):
                return _fake_fred(), _meta(3)
            if key == "macro_yfinance_1y":
                return _fake_yfinance(), _meta(3)
            return pd.DataFrame(), _meta(0, source_status="unavailable")

        with patch(
            "gold_agent.api.factors.cache.get_with_meta",
            side_effect=mock_cache_get_with_meta,
        ) as mock_cache:
            resp = client.get("/api/analysis/factors")
            assert resp.status_code == 200
            data = resp.json()

            # COT
            assert data["cot"] is not None
            assert data["cot"]["long_short_ratio"] == 3.0
            assert data["cot"]["label"] == "看多"
            assert data["cot"]["meta"]["row_count"] == 3
            assert data["cot"]["aligned_as_of"] == "2024-01-21T00:00:00"
            assert data["cot"]["lag_days"] >= 0

            # FedWatch
            assert data["fedwatch"] is not None
            assert data["fedwatch"]["cut_probability"] == 70.0
            assert data["fedwatch"]["label"] == "偏鸽"
            assert data["fedwatch"]["meta"]["source_status"] == "cache"
            assert data["fedwatch"]["aligned_as_of"] == "2024-12-01T00:00:00"
            assert data["fedwatch"]["lag_days"] >= 0

            # Central bank
            assert data["central_bank"] is not None
            assert data["central_bank"]["total_reserves_tonnes"] == 290.0
            assert data["central_bank"]["label"] == "利多"
            assert data["central_bank"]["meta"]["row_count"] == 6
            assert data["central_bank"]["aligned_as_of"] == "2024-01-06T00:00:00"
            assert data["central_bank"]["top_countries"] == [
                {"country": "美国", "gold_reserves_tonnes": 110.0},
                {"country": "德国", "gold_reserves_tonnes": 95.0},
                {"country": "法国", "gold_reserves_tonnes": 85.0},
            ]

            # TIPS
            assert data["tips"] is not None
            assert data["tips"]["tips_yield"] == 0.3
            assert data["tips"]["label"] == "利多"
            assert data["tips"]["meta"]["quality_score"] == 100
            assert data["tips"]["aligned_as_of"] == "2024-01-03T00:00:00"

            # DXY
            assert data["dxy"] is not None
            assert data["dxy"]["dxy"] == 103.8
            assert data["dxy"]["label"] == "中性"
            assert data["dxy"]["meta"]["row_count"] == 3
            assert data["dxy"]["aligned_as_of"] == "2024-01-03T00:00:00"

            # All 5 keys present
            for key in ["cot", "fedwatch", "central_bank", "tips", "dxy"]:
                assert key in data
            assert data["meta"]["available_count"] == 5
            assert data["meta"]["unavailable_count"] == 0
            assert data["meta"]["coverage_satisfied"] is True
            assert data["meta"]["min_required_available"] == 3
            assert data["meta"]["source_status"] == "cache"
            assert data["meta"]["quality_score"] == 100
            assert data["meta"]["max_lag_days"] >= 0
            cot_call = next(
                call.kwargs
                for call in mock_cache.call_args_list
                if call.kwargs["key"] == cot_cache_key(2026)
            )
            assert cot_call["year"] == 2026

    def test_factors_partial_failure(self):
        """部分数据源无数据时仍返回 meta，便于判断不可用原因。"""
        patcher = patch("gold_agent.api.factors.cache.get_with_meta",
                        return_value=(pd.DataFrame(), _meta(0, source_status="unavailable")))
        patcher.start()
        try:
            resp = client.get("/api/analysis/factors")
            assert resp.status_code == 200
            data = resp.json()
            for key in ["cot", "fedwatch", "central_bank", "tips", "dxy"]:
                assert data[key]["available"] is False
                assert data[key]["reason"] == "empty"
                assert data[key]["meta"]["source_status"] == "unavailable"
                assert data[key]["meta"]["row_count"] == 0
            assert data["meta"]["available_count"] == 0
            assert data["meta"]["unavailable_count"] == 5
            assert data["meta"]["coverage_satisfied"] is False
            assert data["meta"]["source_status"] == "unavailable"
            assert data["meta"]["quality_score"] == 0
        finally:
            patcher.stop()

    def test_factors_respect_as_of_query(self):
        def mock_cache_get_with_meta(key, **kwargs):
            if key == cot_cache_key(2024):
                return _fake_cot(), _meta(3)
            if key == "fedwatch":
                return _fake_fedwatch(), _meta(1)
            if key == "central_bank_reserves":
                return _fake_cb(), _meta(6)
            if key == macro_fred_cache_key(start_date="2024-01-01"):
                return _fake_fred(), _meta(3)
            if key == "macro_yfinance_1y":
                return _fake_yfinance(), _meta(3)
            return pd.DataFrame(), _meta(0, source_status="unavailable")

        with patch(
            "gold_agent.api.factors.cache.get_with_meta",
            side_effect=mock_cache_get_with_meta,
        ):
            resp = client.get("/api/analysis/factors?as_of=2024-01-15")

        assert resp.status_code == 200
        data = resp.json()
        assert data["cot"]["aligned_as_of"] == "2024-01-14T00:00:00"
        assert data["tips"]["aligned_as_of"] == "2024-01-03T00:00:00"
        assert data["fedwatch"]["available"] is False
        assert data["fedwatch"]["reason"] == "not_aligned"
        assert data["fedwatch"]["meta"]["row_count"] == 1
        assert data["meta"]["available_count"] == 4
        assert data["meta"]["coverage_satisfied"] is True

    def test_factors_cot_uses_anchor_year_cache_key(self):
        def mock_cache_get_with_meta(key, **kwargs):
            if key == cot_cache_key(2024):
                assert kwargs["year"] == 2024
                return _fake_cot(), _meta(3)
            if key == "fedwatch":
                return pd.DataFrame(), _meta(0, source_status="unavailable")
            if key == "central_bank_reserves":
                return pd.DataFrame(), _meta(0, source_status="unavailable")
            if key == macro_fred_cache_key(start_date="2024-01-01"):
                return pd.DataFrame(), _meta(0, source_status="unavailable")
            if key == "macro_yfinance_1y":
                return pd.DataFrame(), _meta(0, source_status="unavailable")
            raise AssertionError(f"unexpected key: {key}")

        with patch(
            "gold_agent.api.factors.cache.get_with_meta",
            side_effect=mock_cache_get_with_meta,
        ) as mock_cache:
            resp = client.get("/api/analysis/factors?as_of=2024-01-15")

        assert resp.status_code == 200
        cot_calls = [
            call.kwargs
            for call in mock_cache.call_args_list
            if call.kwargs["key"].startswith("cot_")
        ]
        assert cot_calls[0]["key"] == cot_cache_key(2024)
        assert cot_calls[0]["year"] == 2024
