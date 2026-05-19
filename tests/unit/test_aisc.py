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
