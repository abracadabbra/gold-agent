"""GPR 指数数据采集单元测试"""

from unittest.mock import patch

import pandas as pd

from gold_agent.data.geopol import fetch_geopol


def _make_sample_geopol_df():
    """模拟 GPR XLS 数据"""
    return pd.DataFrame({
        "year": [2020, 2021, 2022],
        "month": [1, 6, 12],
        "GPR": [100.5, 110.2, 95.8],
        "GPR threat": [90.1, 105.3, 88.4],
        "GPR act": [85.2, 95.7, 80.1],
    })


class TestFetchGeopol:
    """测试 GPR 指数获取"""

    def test_success(self):
        """正常下载和解析 GPR 数据"""
        mock_df = _make_sample_geopol_df()
        with patch("gold_agent.data.geopol.pd.read_excel") as mock_read:
            mock_read.return_value = mock_df

            result = fetch_geopol()

            assert not result.empty
            assert "date" in result.columns
            assert "gpr_index" in result.columns
            assert "gpr_threats" in result.columns
            assert "gpr_acts" in result.columns
            assert len(result) == 3
            assert result["date"].dt.tz is None

    def test_with_variant(self):
        """variant 参数被传入但 XLS 数据格式相同"""
        mock_df = _make_sample_geopol_df()
        with patch("gold_agent.data.geopol.pd.read_excel") as mock_read:
            mock_read.return_value = mock_df

            result = fetch_geopol(variant="china")

            assert not result.empty

    def test_no_date_column(self):
        """缺少日期列时返回空"""
        mock_df = pd.DataFrame({"GPR": [100.0], "GPR threat": [90.0]})
        with patch("gold_agent.data.geopol.pd.read_excel") as mock_read:
            mock_read.return_value = mock_df

            result = fetch_geopol()

            assert result.empty

    def test_download_failure(self):
        """下载异常时返回空 DataFrame"""
        with patch("gold_agent.data.geopol.pd.read_excel") as mock_read:
            mock_read.side_effect = Exception("HTTP error")

            result = fetch_geopol()

            assert result.empty

    def test_single_date_col_elif_branch(self):
        """只有一个日期列时使用 elif 分支（覆盖 lines 43-44）"""
        mock_df = pd.DataFrame({
            "year": [2020, 2021],
            "GPR": [100.0, 110.0],
            "GPR_threat": [90.0, 95.0],
            "GPR_act": [85.0, 88.0],
        })
        with patch("gold_agent.data.geopol.pd.read_excel") as mock_read:
            mock_read.return_value = mock_df
            result = fetch_geopol()
            assert not result.empty
            assert "date" in result.columns
            assert "gpr_index" in result.columns
