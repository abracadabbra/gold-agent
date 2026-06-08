"""黄金 ETF 流量数据采集单元测试"""

from unittest.mock import MagicMock, patch

import pandas as pd

from gold_agent.data.etf_flow import (
    _fetch_wgc_etf,
    _fetch_yfinance_etf_fallback,
    _find_date_column,
    _standardize_columns,
    fetch_etf_flow,
)


def _make_urlopen_mock(content: bytes = b"fake xlsx content"):
    """创建模拟 urlopen 响应（支持 context manager）"""
    mock_resp = MagicMock()
    mock_resp.read.return_value = content
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_resp
    mock_cm.__exit__.return_value = None
    return mock_cm


def _mock_wgc_xlsx():
    """模拟 WGC XLSX 原始数据（含日期列，近期日期以保证不过滤）"""
    today = pd.Timestamp.now()
    dates = [today - pd.DateOffset(months=i) for i in range(3)]
    return pd.DataFrame({
        "Date": dates,
        "Fund Name": ["SPDR Gold Shares", "iShares Gold Trust", "SPDR Gold Shares"],
        "Region": ["North America", "North America", "North America"],
        "Holdings Tonnes": [900.5, 250.3, 890.2],
        "Flow Tonnes": [5.0, -2.1, -10.3],
        "Flow USD": [300e6, -130e6, -650e6],
        "AUM USD": [56e9, 15e9, 55e9],
    })


class TestFetchEtfFlow:
    """测试 ETF 流量获取"""

    def test_wgc_success(self):
        """WGC 下载成功时返回结构化数据"""
        mock_df = _mock_wgc_xlsx()
        with patch("pandas.read_excel") as mock_read:
            mock_read.return_value = mock_df
            mock_url = _make_urlopen_mock()
            with patch("urllib.request.urlopen", return_value=mock_url):
                result = fetch_etf_flow(months=12)

                assert not result.empty
                assert "date" in result.columns
                assert "fund_name" in result.columns
                assert "region" in result.columns
                assert len(result) == 3
                assert result["date"].dt.tz is None

    def test_wgc_failure_yfinance_fallback(self):
        """WGC 下载失败时使用 yfinance 兜底"""
        # Make WGC fetch fail (both URL attempts)
        mock_url = _make_urlopen_mock()
        with patch("urllib.request.urlopen", return_value=mock_url):
            # Make pandas.read_excel fail so WGC path returns empty
            with patch("pandas.read_excel") as mock_read:
                mock_read.side_effect = Exception("XLSX parse error")

                # Mock yfinance fallback
                with patch("yfinance.Ticker") as mock_ticker_cls:
                    mock_ticker = mock_ticker_cls.return_value
                    mock_df = pd.DataFrame({
                        "Date": pd.date_range("2024-06-01", periods=2, freq="D", tz="UTC"),
                        "Open": [200.0, 201.0],
                        "High": [202.0, 203.0],
                        "Low": [199.0, 200.0],
                        "Close": [201.0, 202.0],
                        "Volume": [1000000, 1200000],
                    })
                    mock_ticker.history.return_value = mock_df

                    result = fetch_etf_flow(months=6)

                    assert not result.empty
                    assert "date" in result.columns
                    assert "fund_name" in result.columns
                    # Has at least GLD data
                    assert "SPDR Gold Shares" in result["fund_name"].values

    def test_both_fail(self):
        """WGC 和 yfinance 都失败时返回空"""
        mock_url = _make_urlopen_mock()
        with patch("urllib.request.urlopen", return_value=mock_url):
            with patch("pandas.read_excel") as mock_read:
                mock_read.side_effect = Exception("XLSX parse error")

                with patch("yfinance.Ticker") as mock_ticker_cls:
                    mock_ticker = mock_ticker_cls.return_value
                    mock_ticker.history.side_effect = Exception("yfinance error")

                    result = fetch_etf_flow()
                    assert result.empty

    def test_find_date_column_not_found(self):
        """无日期列时 _find_date_column 返回 None"""
        df = pd.DataFrame({"a": [1], "b": [2]})
        assert _find_date_column(df) is None

    def test_standardize_columns_find_date_rename(self):
        """日期列通过 _find_date_column 匹配并重命名"""
        df = pd.DataFrame({
            "Period": pd.date_range("2024-01-01", periods=2),
            "Fund Name": ["SPDR Gold Shares", "iShares Gold Trust"],
            "Region": ["North America", "North America"],
            "Holdings Tonnes": [100.0, 200.0],
        })
        result = _standardize_columns(df)
        assert "date" in result.columns
        assert len(result) == 2

    def test_standardize_columns_missing_fund_name(self):
        """fund_name/region 列缺失时填入默认值 Global"""
        df = pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=2),
            "Holdings Tonnes": [100.0, 200.0],
        })
        result = _standardize_columns(df)
        assert "date" in result.columns
        assert "fund_name" in result.columns
        assert (result["fund_name"] == "Global").all()
        assert "region" in result.columns
        assert (result["region"] == "Global").all()

    def test_wgc_primary_url_fails_fallback_succeeds(self):
        """WGC 主 URL 失败时使用备用 URL 成功"""
        mock_df = _mock_wgc_xlsx()
        mock_url = _make_urlopen_mock()
        with patch("pandas.read_excel") as mock_read:
            mock_read.return_value = mock_df
            exc = Exception("Primary URL failed")
            with patch("urllib.request.urlopen", side_effect=[exc, mock_url]):
                result = fetch_etf_flow(months=12)
                assert not result.empty
                assert len(result) == 3

    def test_wgc_empty_excel(self):
        """WGC XLSX 为空时 _fetch_wgc_etf 返回空"""
        mock_url = _make_urlopen_mock()
        with patch("pandas.read_excel") as mock_read:
            mock_read.return_value = pd.DataFrame()
            with patch("urllib.request.urlopen", return_value=mock_url):
                result = _fetch_wgc_etf(months=12)
                assert result.empty

    def test_wgc_no_date_column(self):
        """WGC 数据中无日期列时 _fetch_wgc_etf 返回空"""
        mock_url = _make_urlopen_mock()
        df_no_date = pd.DataFrame({
            "Fund Name": ["SPDR Gold Shares"],
            "Region": ["North America"],
            "Holdings Tonnes": [900.0],
        })
        with patch("pandas.read_excel") as mock_read:
            mock_read.return_value = df_no_date
            with patch("urllib.request.urlopen", return_value=mock_url):
                result = _fetch_wgc_etf(months=12)
                assert result.empty

    def test_yfinance_ticker_empty_skipped(self):
        """yfinance 部分 ETF 历史数据为空时跳过该 ticker"""
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = mock_ticker_cls.return_value
            mock_ticker.history.return_value = pd.DataFrame()
            result = _fetch_yfinance_etf_fallback(months=6)
            assert result.empty
