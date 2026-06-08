"""AISC 黄金生产成本数据采集单元测试"""

from unittest.mock import patch

import pandas as pd

from gold_agent.data.aisc import fetch_aisc


def _mock_aisc_xlsx():
    """模拟 WGC AISC XLSX 数据"""
    return pd.DataFrame({
        "Year": [2022, 2022, 2023, 2023],
        "Quarter": ["Q1", "Q2", "Q1", "Q2"],
        "Global AISC": [1270, 1285, 1320, 1340],
        "Region": ["Global", "Global", "Global", "Global"],
    })


class TestFetchAisc:
    """测试 AISC 数据获取"""

    def test_wgc_success(self):
        """WGC 下载成功时返回结构化数据"""
        mock_df = _mock_aisc_xlsx()
        with patch("pandas.read_excel") as mock_read:
            mock_read.return_value = mock_df
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = mock_urlopen.return_value.__enter__.return_value
                mock_resp.read.return_value = b"fake xlsx"

                result = fetch_aisc()

                assert not result.empty
                assert "year" in result.columns
                assert "quarter" in result.columns
                assert "global_avg_aisc" in result.columns
                assert "date" in result.columns
                assert len(result) == 4

    def test_wgc_failure_reference_fallback(self):
        """WGC 下载失败时返回参考数据"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("WGC unavailable")

            result = fetch_aisc()

            assert not result.empty
            assert "year" in result.columns
            assert "global_avg_aisc" in result.columns
            # Reference data has ~10 rows
            assert len(result) >= 8

    def test_no_usable_data_in_xlsx(self):
        """XLSX 中无可用数据列时返回空"""
        mock_df = pd.DataFrame({"Unrelated": [1, 2]})
        with patch("pandas.read_excel") as mock_read:
            mock_read.return_value = mock_df
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = mock_urlopen.return_value.__enter__.return_value
                mock_resp.read.return_value = b"fake"

                # Should fail all URLs and then use reference data
                result = fetch_aisc()

                # Falls back to reference data
                assert not result.empty
                assert "reference" in str(result["note"].iloc[0]).lower()

    def test_find_column_exclude(self):
        """_find_column 跳过 exclude 列表中的列（覆盖 line 46）"""
        from gold_agent.data.aisc import _find_column
        df = pd.DataFrame({"year": [2020], "quarter": ["Q1"], "aisc": [1200]})
        col = _find_column(df, ["aisc"], exclude={"quarter"})
        assert col == "aisc"

    def test_find_column_exclude_no_match(self):
        """_find_column exclude 中无匹配时正常返回"""
        from gold_agent.data.aisc import _find_column
        df = pd.DataFrame({"year": [2020], "aisc": [1200]})
        col = _find_column(df, ["aisc"], exclude={"quarter"})
        assert col == "aisc"

    def test_find_aisc_column_no_match(self):
        """_find_aisc_column 找不到 AISC 列时返回 None（覆盖 line 65）"""
        from gold_agent.data.aisc import _find_aisc_column
        df = pd.DataFrame({"year": [2020], "quarter": ["Q1"], "text_col": ["foo"]})
        col = _find_aisc_column(df, "year", "quarter")
        assert col is None

    def test_build_date_no_quarter(self):
        """_build_date 无 quarter 列时使用年中的 6-30（覆盖 line 81）"""
        from gold_agent.data.aisc import _build_date
        df = pd.DataFrame({"year": [2022, 2023], "global_avg_aisc": [1200, 1300]})
        result = _build_date(df)
        assert "date" in result.columns
        assert result["date"].iloc[0].month == 6
        assert result["date"].iloc[0].day == 30

    def test_parse_xlsx_empty_df(self):
        """_parse_xlsx 遇到空 DataFrame 返回空（覆盖 line 89）"""
        from gold_agent.data.aisc import _parse_xlsx
        with patch("pandas.read_excel", return_value=pd.DataFrame()):
            result = _parse_xlsx(b"fake xlsx content")
            assert result.empty
            assert len(result) == 0

    def test_parse_xlsx_no_aisc_column(self):
        """_parse_xlsx 找不到成本列时返回空并记录警告（覆盖 lines 98-99）"""
        from gold_agent.data.aisc import _parse_xlsx
        mock_df = pd.DataFrame({
            "Year": [2022, 2023],
            "Quarter": ["Q1", "Q2"],
            "Note": ["text1", "text2"],
        })
        with patch("pandas.read_excel", return_value=mock_df):
            result = _parse_xlsx(b"fake")
            assert result.empty
