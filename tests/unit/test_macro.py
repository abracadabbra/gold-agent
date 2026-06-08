"""宏观经济数据采集单元测试"""

from unittest.mock import patch

import numpy as np
import pandas as pd

from gold_agent.config import settings
from gold_agent.data.macro import (
    fetch_all_macro,
    fetch_macro_fred,
    fetch_macro_yfinance,
    macro_fred_cache_key,
    macro_yfinance_cache_key,
)


def _make_multiindex_df(ticker_symbols, n_periods=3):
    """构造模拟 yfinance download 返回的 MultiIndex DataFrame"""
    dates = pd.date_range("2024-01-01", periods=n_periods, freq="D", tz="UTC", name="Date")
    arrays = [["Close"] * len(ticker_symbols) + ["Open"] * len(ticker_symbols),
              ticker_symbols * 2]
    columns = pd.MultiIndex.from_arrays(arrays, names=["Price", "Ticker"])
    data = np.random.randn(n_periods, len(ticker_symbols) * 2)
    return pd.DataFrame(data, index=dates, columns=columns)


class TestFetchMacroYfinance:
    """测试 yfinance 宏观数据获取"""

    def test_success_with_multiple_indicators(self):
        """正常拉取多个指标"""
        fake_df = _make_multiindex_df(["DX-Y.NYB", "^TNX"])
        with patch("gold_agent.data.macro.yf.download") as mock_dl:
            mock_dl.return_value = fake_df

            result = fetch_macro_yfinance(indicators=["usd_index", "us_10y"])

            assert not result.empty
            assert "date" in result.columns
            assert "usd_index" in result.columns
            assert "us_10y" in result.columns
            assert len(result) == 3
            # 时区应该被移除
            assert result["date"].dt.tz is None

    def test_default_indicators(self):
        """不传 indicators 时拉取全部指标"""
        fake_df = _make_multiindex_df(["DX-Y.NYB", "^TNX", "^VIX", "^GSPC", "CL=F", "^IRX"])
        with patch("gold_agent.data.macro.yf.download") as mock_dl:
            mock_dl.return_value = fake_df

            result = fetch_macro_yfinance(period="1y")

            assert not result.empty
            assert "date" in result.columns
            # 至少有部分指标列
            macro_cols = {"usd_index", "us_10y", "vix", "sp500", "crude_oil", "us_2y"}
            assert macro_cols.issubset(result.columns)

    def test_yfinance_returns_empty_dataframe(self):
        """yfinance 返回空 DataFrame 时应返回空"""
        with patch("gold_agent.data.macro.yf.download") as mock_dl:
            mock_dl.return_value = pd.DataFrame()

            result = fetch_macro_yfinance()
            assert result.empty

    def test_yfinance_raises_exception(self):
        """yfinance 调用异常时应返回空"""
        with patch("gold_agent.data.macro.yf.download") as mock_dl:
            mock_dl.side_effect = Exception("download failed")

            result = fetch_macro_yfinance()
            assert result.empty

    def test_single_ticker_non_multiindex(self):
        """单 ticker 时 columns 不是 MultiIndex（覆盖 lines 61-62）"""
        dates = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC", name="Date")
        # Single ticker returns regular Index (not MultiIndex)
        single_df = pd.DataFrame(
            {"Close": [2000.0, 2010.0, 2005.0]},
            index=dates,
        )
        single_df.columns.name = "Price"
        with patch("gold_agent.data.macro.yf.download") as mock_dl:
            mock_dl.return_value = single_df
            result = fetch_macro_yfinance(indicators=["gold"])
            assert not result.empty
            assert "date" in result.columns

    def test_datetime_column_rename(self):
        """yfinance 返回 datetime 列名时重命名为 date（覆盖 line 71）"""
        # Use "Datetime" as index name so reset_index creates a "Datetime" column
        dates = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC", name="Datetime")
        arrays = [["Close"] * 2, ["DX-Y.NYB", "^TNX"]]
        columns = pd.MultiIndex.from_arrays(arrays, names=["Price", "Ticker"])
        df = pd.DataFrame(index=dates, columns=columns, dtype=float)
        with patch("gold_agent.data.macro.yf.download") as mock_dl:
            mock_dl.return_value = df
            result = fetch_macro_yfinance(indicators=["usd_index", "us_10y"])
            assert not result.empty
            assert "date" in result.columns


class TestFetchMacroFred:
    """测试 FRED 宏观数据获取"""

    def test_success_with_multiple_series(self):
        """正常拉取多个 FRED 序列"""
        with patch.object(settings, "fred_api_key", "mock_key"):
            with patch("fredapi.Fred") as mock_fred_cls:
                mock_fred = mock_fred_cls.return_value
                # 模拟 get_series 返回 pandas Series
                dates = pd.date_range("2024-01-01", periods=5, freq="ME")
                mock_fred.get_series.return_value = pd.Series(
                    [3.0, 3.1, 3.0, 2.9, 3.0], index=dates
                )

                result = fetch_macro_fred(series_ids=["fed_rate", "cpi"])

                assert not result.empty
                assert "date" in result.columns
                assert "fed_rate" in result.columns
                assert "cpi" in result.columns
                assert len(result) == 5
                assert result["date"].dt.tz is None

    def test_no_api_key(self):
        """API key 为空时直接返回空 DataFrame"""
        with patch.object(settings, "fred_api_key", ""):
            result = fetch_macro_fred()

            assert result.empty

    def test_unknown_series_id(self):
        """未知 series_id 被跳过"""
        with patch.object(settings, "fred_api_key", "mock_key"):
            with patch("fredapi.Fred") as mock_fred_cls:
                mock_fred = mock_fred_cls.return_value
                mock_fred.get_series.return_value = pd.Series([1.0, 2.0])

                result = fetch_macro_fred(series_ids=["unknown_series", "fed_rate"])

                # unknown_series 应该被跳过，只返回 fed_rate
                assert "fed_rate" in result.columns
                assert "unknown_series" not in result.columns

    def test_series_raises_exception(self):
        """单个序列获取失败时不影响其他序列"""
        with patch.object(settings, "fred_api_key", "mock_key"):
            with patch("fredapi.Fred") as mock_fred_cls:
                mock_fred = mock_fred_cls.return_value
                # 第一次调用成功，第二次异常
                mock_fred.get_series.side_effect = [
                    pd.Series([1.0, 2.0]),
                    Exception("FRED error"),
                ]

                result = fetch_macro_fred(series_ids=["fed_rate", "cpi"])

                assert "fed_rate" in result.columns
                # 即使 cpi 失败，fed_rate 也应该返回
                assert not result.empty

    def test_series_returns_empty(self):
        """FRED 序列返回空时记录警告（覆盖 line 131）"""
        with patch.object(settings, "fred_api_key", "mock_key"):
            with patch("fredapi.Fred") as mock_fred_cls:
                mock_fred = mock_fred_cls.return_value
                mock_fred.get_series.return_value = pd.Series([], dtype=float)

                result = fetch_macro_fred(series_ids=["fed_rate"])
                # No data -> empty result
                assert result.empty

    def test_no_results_returns_empty(self):
        """所有 FRED 序列都失败时返回空（覆盖 line 136）"""
        with patch.object(settings, "fred_api_key", "mock_key"):
            with patch("fredapi.Fred") as mock_fred_cls:
                mock_fred = mock_fred_cls.return_value
                mock_fred.get_series.side_effect = Exception("API error")

                result = fetch_macro_fred(series_ids=["fed_rate", "cpi"])
                assert result.empty


class TestFetchAllMacro:
    """测试 fetch_all_macro 聚合函数"""

    def test_returns_dict_with_realtime_and_official(self):
        """应返回包含 realtime 和 official 的 dict"""
        fake_yf = _make_multiindex_df(["DX-Y.NYB"])
        with patch.object(settings, "fred_api_key", "mock_key"):
            with patch("gold_agent.data.macro.yf.download") as mock_dl:
                mock_dl.return_value = fake_yf

                with patch("fredapi.Fred") as mock_fred_cls:
                    mock_fred = mock_fred_cls.return_value
                    mock_fred.get_series.return_value = pd.Series([1.0, 2.0])

                    result = fetch_all_macro(period="1y")

                    assert "realtime" in result
                    assert "official" in result
                    assert not result["realtime"].empty
                    assert not result["official"].empty


class TestMacroCacheKeys:
    """测试宏观缓存 key helper"""

    def test_macro_yfinance_cache_key_default_is_backward_compatible(self):
        assert macro_yfinance_cache_key(period="1y") == "macro_yfinance_1y"

    def test_macro_yfinance_cache_key_sorts_subset_indicators(self):
        assert (
            macro_yfinance_cache_key(period="1y", indicators=["us_10y", "usd_index"])
            == "macro_yfinance_1y_us_10y-usd_index"
        )

    def test_macro_yfinance_cache_key_full_set_collapses_to_default(self):
        assert (
            macro_yfinance_cache_key(
                period="1y",
                indicators=["gold", "crude_oil", "sp500", "vix", "us_2y", "us_10y", "usd_index"],
            )
            == "macro_yfinance_1y"
        )

    def test_macro_yfinance_cache_key_empty_subset_isolated(self):
        assert macro_yfinance_cache_key(period="1y", indicators=[]) == "macro_yfinance_1y_none"

    def test_macro_fred_cache_key_includes_start_date(self):
        assert macro_fred_cache_key(start_date="2024-01-01") == "macro_fred_2024-01-01_all"

    def test_macro_fred_cache_key_sorts_series_ids(self):
        assert (
            macro_fred_cache_key(start_date="2024-01-01", series_ids=["tips_yield", "fed_rate"])
            == "macro_fred_2024-01-01_fed_rate-tips_yield"
        )
