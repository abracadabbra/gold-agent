"""CFTC COT 持仓报告单元测试"""

from unittest.mock import patch

import pandas as pd

from gold_agent.data.cot import fetch_cot


def _mock_cot_year():
    """模拟 cot_reports cot.cot_year() 返回值"""
    return pd.DataFrame({
        "Date": ["2024-01-02", "2024-01-09", "2024-01-16"],
        "Market and Exchange Names": ["GOLD - COMEX"] * 3,
        "CFTC Commodity Code": ["088691"] * 3,
        "Open Interest": [500000, 510000, 520000],
        "Prod Long": [100000, 102000, 101000],
        "Prod Short": [80000, 79000, 82000],
        "Swap Long": [120000, 121000, 119000],
        "Swap Short": [90000, 91000, 92000],
        "M M Long": [150000, 155000, 160000],
        "M M Short": [70000, 68000, 72000],
        "Other Long": [30000, 31000, 29000],
        "Other Short": [20000, 21000, 22000],
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

    def test_fetch_error(self):
        """API 异常时返回空"""
        with patch("cot_reports.cot_year") as mock_cot:
            mock_cot.side_effect = Exception("API error")

            result = fetch_cot(year=2024)

            assert result.empty
