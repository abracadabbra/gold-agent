"""中国宏观经济数据采集单元测试"""

from unittest.mock import patch

import pandas as pd
import pytest

from gold_agent.data.china_macro import (
    fetch_all_china_macro,
    fetch_china_cpi,
    fetch_china_fx,
    fetch_china_gdp,
    fetch_china_lpr,
    fetch_china_m2,
    fetch_china_pmi,
    fetch_china_ppi,
)


def _mock_akshare_df():
    """模拟 akshare 返回的 DataFrame（含中文列名）"""
    return pd.DataFrame({
        "日期": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
        "值": [100.5, 101.2, 101.8],
    })


def _mock_lpr_df():
    """模拟 bond_zh_lpr 返回值"""
    return pd.DataFrame({
        "日期": pd.to_datetime(["2024-01-01", "2024-02-01"]),
        "1年期LPR": [3.45, 3.35],
        "5年期LPR": [4.20, 4.10],
    })


def _mock_fx_df():
    """模拟 fx_spot_quote 返回值"""
    return pd.DataFrame({
        "日期": pd.to_datetime(["2024-01-01"]),
        "收盘价": [7.12],
    })


class TestFetchChinaMacro:
    """测试中国宏观数据获取"""

    @pytest.mark.parametrize("fetch_fn,ak_func", [
        (fetch_china_cpi, "macro_china_cpi"),
        (fetch_china_ppi, "macro_china_ppi"),
        (fetch_china_pmi, "macro_china_pmi"),
        (fetch_china_m2, "macro_china_money_supply"),
        (fetch_china_gdp, "macro_china_gdp"),
    ])
    def test_basic_macro(self, fetch_fn, ak_func):
        """基础宏观指标正常获取，返回 date + value"""
        mock_df = _mock_akshare_df()
        with patch(f"akshare.{ak_func}") as mock_ak:
            mock_ak.return_value = mock_df

            result = fetch_fn()

            assert not result.empty
            assert "date" in result.columns
            assert "value" in result.columns
            assert len(result) == 3
            assert result["date"].dt.tz is None

    def test_fetch_lpr(self):
        """LPR 数据获取"""
        with patch("akshare.macro_china_lpr") as mock_ak:
            mock_ak.return_value = _mock_lpr_df()

            result = fetch_china_lpr()

            assert not result.empty
            assert "date" in result.columns
            assert "value" in result.columns

    def test_fetch_fx(self):
        """汇率数据获取"""
        with patch("akshare.fx_spot_quote") as mock_ak:
            mock_ak.return_value = _mock_fx_df()

            result = fetch_china_fx()

            assert not result.empty
            assert "date" in result.columns
            assert "value" in result.columns

    def test_fetch_error(self):
        """akshare 异常时返回空 DataFrame"""
        with patch("akshare.macro_china_cpi") as mock_ak:
            mock_ak.side_effect = Exception("API error")

            result = fetch_china_cpi()

            assert result.empty

    def test_empty_return(self):
        """akshare 返回空 DataFrame 时返回空"""
        with patch("akshare.macro_china_cpi") as mock_ak:
            mock_ak.return_value = pd.DataFrame()

            result = fetch_china_cpi()

            assert result.empty

    def test_fetch_all(self):
        """fetch_all_china_macro 返回所有指标"""
        mock_df = _mock_akshare_df()
        patches = [
            patch("akshare.macro_china_cpi", return_value=mock_df),
            patch("akshare.macro_china_ppi", return_value=mock_df),
            patch("akshare.macro_china_pmi", return_value=mock_df),
            patch("akshare.macro_china_money_supply", return_value=mock_df),
            patch("akshare.macro_china_gdp", return_value=mock_df),
            patch("akshare.macro_china_lpr", return_value=_mock_lpr_df()),
            patch("akshare.fx_spot_quote", return_value=_mock_fx_df()),
        ]
        for p in patches:
            p.start()

        try:
            result = fetch_all_china_macro()

            expected_keys = {"cpi", "ppi", "pmi", "m2", "gdp", "lpr", "usd_cny"}
            assert set(result.keys()) == expected_keys
            assert all(not df.empty for df in result.values())
        finally:
            for p in patches:
                p.stop()
