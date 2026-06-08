"""CFTC COT 持仓报告单元测试"""

from unittest.mock import patch

import pandas as pd

from gold_agent.data.cot import cot_cache_key, fetch_cot


def _mock_cot_year():
    """模拟 cot_reports cot.cot_year() 返回值（使用 CFTC 真实列名）"""
    return pd.DataFrame({
        "As of Date in Form YYYY-MM-DD": ["2024-01-02", "2024-01-09", "2024-01-16"],
        "Market and Exchange Names": ["GOLD - COMEX"] * 3,
        "CFTC Commodity Code": ["088691"] * 3,
        "Open Interest (All)": [500000, 510000, 520000],
        "Commercial Positions-Long (All)": [100000, 102000, 101000],
        "Commercial Positions-Short (All)": [80000, 79000, 82000],
        "Noncommercial Positions-Long (All)": [150000, 155000, 160000],
        "Noncommercial Positions-Short (All)": [70000, 68000, 72000],
    })


class TestFetchCot:
    """测试 COT 持仓数据获取"""

    def test_success(self):
        """正常获取黄金持仓数据"""
        mock_df = _mock_cot_year()
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.return_value = mock_df

            result = fetch_cot(year=2024)

            assert not result.empty
            assert "date" in result.columns
            assert "open_interest" in result.columns
            assert "managed_money_long" in result.columns
            assert "managed_money_short" in result.columns
            assert len(result) == 3

    def test_empty_data(self):
        """cot_reports 返回空时返回空 DataFrame"""
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.return_value = pd.DataFrame()

            result = fetch_cot(year=2024)

            assert result.empty

    def test_default_year(self):
        """不传 year 时使用当前年份"""
        import datetime
        mock_df = _mock_cot_year()
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.return_value = mock_df

            result = fetch_cot()

            current_year = datetime.date.today().year
            mock_cot.assert_called_once_with(year=current_year, cot_report_type="legacy_fut")
            assert not result.empty

    def test_default_year_with_none(self):
        """显式传入 year=None 时使用当前年份"""
        import datetime
        mock_df = _mock_cot_year()
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.return_value = mock_df

            result = fetch_cot(year=None)

            current_year = datetime.date.today().year
            mock_cot.assert_called_once_with(year=current_year, cot_report_type="legacy_fut")
            assert not result.empty

    def test_no_gold_data(self):
        """数据中无黄金持仓时返回空"""
        mock_df = pd.DataFrame({
            "Date": ["2024-01-02"],
            "Market and Exchange Names": ["SILVER - COMEX"],
            "CFTC Commodity Code": ["084691"],
        })
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.return_value = mock_df

            result = fetch_cot(year=2024)

            assert result.empty

    def test_fallback_code_column(self):
        """使用 CFTC_Commodity_Code 列（下划线格式）过滤黄金"""
        # 数据不包含 "Market and Exchange Names"，但包含 "CFTC_Commodity_Code"
        mock_df = pd.DataFrame({
            "As of Date in Form YYYY-MM-DD": ["2024-01-02", "2024-01-09"],
            "CFTC_Commodity_Code": ["088691", "088691"],
            "Open Interest (All)": [500000, 510000],
            "Commercial Positions-Long (All)": [100000, 102000],
            "Commercial Positions-Short (All)": [80000, 79000],
            "Noncommercial Positions-Long (All)": [150000, 155000],
            "Noncommercial Positions-Short (All)": [70000, 68000],
        })
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.return_value = mock_df

            result = fetch_cot(year=2024)

            assert not result.empty
            assert "date" in result.columns
            assert len(result) == 2

    def test_fuzzy_column_matching(self):
        """列名不完全匹配时模糊匹配"""
        mock_df = pd.DataFrame({
            "As of Date in Form YYYY-MM-DD": ["2024-01-02", "2024-01-09", "2024-01-16"],
            "Market and Exchange Names": ["GOLD - COMEX"] * 3,
            "CFTC Commodity Code": ["088691"] * 3,
            "OPEN INTEREST (ALL)": [500000, 510000, 520000],
            "Commercial Positions-Long (All)": [100000, 102000, 101000],
            "Commercial Positions-Short (All)": [80000, 79000, 82000],
            "noncommercial positions-long (all)": [150000, 155000, 160000],
            "noncommercial positions-short (all)": [70000, 68000, 72000],
        })
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.return_value = mock_df

            result = fetch_cot(year=2024)

            assert not result.empty
            assert "open_interest" in result.columns
            assert "managed_money_long" in result.columns
            assert "managed_money_short" in result.columns
            assert len(result) == 3

    def test_fetch_error(self):
        """API 异常时返回空"""
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.side_effect = Exception("API error")

            result = fetch_cot(year=2024)

            assert result.empty

    def test_fuzzy_code_column(self):
        """_filter_gold 模糊匹配 code 列名（覆盖 lines 43-48）"""
        mock_df = pd.DataFrame({
            "As of Date in Form YYYY-MM-DD": ["2024-01-02"],
            "My_Market_Code": ["088691"],
            "Open Interest (All)": [500000],
            "Noncommercial Positions-Long (All)": [150000],
            "Noncommercial Positions-Short (All)": [70000],
            "Commercial Positions-Long (All)": [100000],
            "Commercial Positions-Short (All)": [80000],
        })
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.return_value = mock_df
            result = fetch_cot(year=2024)
            assert not result.empty
            assert "date" in result.columns

    def test_no_code_column_fallback(self):
        """无 market/code 列时使用全部数据（覆盖 lines 47-48）"""
        mock_df = pd.DataFrame({
            "As of Date in Form YYYY-MM-DD": ["2024-01-02"],
            "Open Interest (All)": [500000],
            "Noncommercial Positions-Long (All)": [150000],
            "Noncommercial Positions-Short (All)": [70000],
            "Commercial Positions-Long (All)": [100000],
            "Commercial Positions-Short (All)": [80000],
        })
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.return_value = mock_df
            result = fetch_cot(year=2024)
            # Should not be empty since _filter_gold returns all data
            assert not result.empty

    def test_import_error(self):
        """cot_reports 未安装时返回空（覆盖 lines 110-111）"""
        import builtins
        import sys

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "cot_reports":
                raise ImportError("No module named cot_reports")
            return original_import(name, *args, **kwargs)

        orig_mod = sys.modules.pop("cot_reports", None)
        try:
            with patch("builtins.__import__", side_effect=mock_import):
                from gold_agent.data.cot import fetch_cot as _fetch
                result = _fetch(year=2024)
                assert result.empty
        finally:
            if orig_mod is not None:
                sys.modules["cot_reports"] = orig_mod


class TestCotCacheKey:
    """测试 cot_cache_key"""

    def test_explicit_year(self):
        assert cot_cache_key(2024) == "cot_2024"

    def test_default_current_year(self):
        import datetime

        current_year = datetime.date.today().year
        assert cot_cache_key() == f"cot_{current_year}"
