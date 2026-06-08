"""金价数据采集单元测试"""

from unittest.mock import patch

import pandas as pd
import pytest

from gold_agent.data.gold_price import (
    fetch_all_gold,
    fetch_gold_etf,
    fetch_gold_price,
    fetch_gold_spot_akshare,
    fetch_gold_xauusd,
    gold_cache_key,
    period_to_days,
    period_to_months,
)


@pytest.fixture
def sample_yfinance_df():
    """模拟 yfinance history() 返回的 DataFrame (含时区)"""
    import datetime
    today = datetime.date.today()
    dates = pd.date_range(today - datetime.timedelta(days=7), periods=5, freq="D", tz="UTC")
    return pd.DataFrame({
        "Date": dates,
        "Open": [2000.0, 2010.0, 2005.0, 2015.0, 2020.0],
        "High": [2010.0, 2020.0, 2015.0, 2025.0, 2030.0],
        "Low": [1990.0, 2000.0, 1995.0, 2005.0, 2010.0],
        "Close": [2005.0, 2015.0, 2008.0, 2018.0, 2025.0],
        "Volume": [10000, 12000, 11000, 13000, 14000],
    })


@pytest.fixture
def sample_akshare_df():
    """模拟 akshare spot_hist_sge() 返回的 DataFrame"""
    import datetime
    today = datetime.date.today()
    dates = pd.date_range(today - datetime.timedelta(days=5), periods=3, freq="D")
    return pd.DataFrame({
        "date": dates,
        "open": [480.0, 482.0, 481.0],
        "high": [485.0, 486.0, 484.0],
        "low": [475.0, 478.0, 477.0],
        "close": [482.0, 483.0, 480.0],
        "volume": [5000, 5200, 5100],
    })


class TestFetchGoldXauusd:
    """测试 yfinance XAUUSD 获取"""

    def test_success(self, sample_yfinance_df):
        """正常拉取应返回标准化的 OHLCV 列"""
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = mock_ticker_cls.return_value
            mock_ticker.history.return_value = sample_yfinance_df

            result = fetch_gold_xauusd(period="1mo")

            mock_ticker_cls.assert_called_once_with("GC=F")
            mock_ticker.history.assert_called_once_with(period="1mo", auto_adjust=True)

            assert list(result.columns) == ["date", "open", "high", "low", "close", "volume"]
            assert len(result) == 5
            # 时区应该被移除
            assert result["date"].dt.tz is None
            # 应该按日期排序
            assert result["date"].is_monotonic_increasing

    def test_error_empty(self):
        """yfinance 异常时返回空 DataFrame"""
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = mock_ticker_cls.return_value
            mock_ticker.history.side_effect = Exception("API error")

            result = fetch_gold_xauusd()

            assert result.empty
            assert list(result.columns) == []


class TestFetchGoldEtf:
    """测试 yfinance GLD ETF 获取"""

    def test_success(self, sample_yfinance_df):
        """正常拉取 GLD ETF 数据"""
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = mock_ticker_cls.return_value
            mock_ticker.history.return_value = sample_yfinance_df

            result = fetch_gold_etf(period="6mo")

            mock_ticker_cls.assert_called_once_with("GLD")
            assert list(result.columns) == ["date", "open", "high", "low", "close", "volume"]
            assert len(result) == 5

    def test_error_empty(self):
        """yfinance 连接异常时返回空 DataFrame"""
        with patch("yfinance.Ticker") as mock_ticker_cls:
            mock_ticker = mock_ticker_cls.return_value
            mock_ticker.history.side_effect = ConnectionError("No network")

            result = fetch_gold_etf()

            assert result.empty


class TestFetchGoldSpotAkshare:
    """测试 akshare 沪金现货获取"""

    def test_success(self, sample_akshare_df):
        """正常拉取应返回标准化的 OHLCV 列"""
        with patch("akshare.spot_hist_sge") as mock_fn:
            mock_fn.return_value = sample_akshare_df

            result = fetch_gold_spot_akshare(days=30)

            assert list(result.columns) == ["date", "open", "high", "low", "close", "volume"]
            assert len(result) == 3
            assert result["date"].dt.tz is None

    def test_error_empty(self):
        """akshare 异常时返回空 DataFrame"""
        with patch("akshare.spot_hist_sge") as mock_fn:
            mock_fn.side_effect = Exception("akshare error")

            result = fetch_gold_spot_akshare()

            assert result.empty


class TestFetchAllGold:
    """测试 fetch_all_gold 聚合函数"""

    def test_returns_all_sources(self, sample_yfinance_df, sample_akshare_df):
        """应返回三个数据源的 dict"""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = sample_yfinance_df

            with patch("akshare.spot_hist_sge") as mock_ak:
                mock_ak.return_value = sample_akshare_df

                result = fetch_all_gold(period="1y")

                assert set(result.keys()) == {"gold_xauusd", "gold_etf", "gold_spot_cny"}
                assert all(not df.empty for df in result.values())

    def test_partial_failure(self, sample_yfinance_df):
        """部分源失败时其他源仍返回"""
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.history.side_effect = [
                sample_yfinance_df,     # xauusd 成功
                Exception("ETF error"),  # etf 失败
            ]

            with patch("akshare.spot_hist_sge") as mock_ak:
                mock_ak.side_effect = Exception("akshare error")

                result = fetch_all_gold()

                assert not result["gold_xauusd"].empty
                assert result["gold_etf"].empty
                assert result["gold_spot_cny"].empty


class TestFetchGoldPrice:
    """测试 fetch_gold_price 别名"""

    def test_delegates_to_xauusd(self):
        """应委托给 fetch_gold_xauusd"""
        with patch("gold_agent.data.gold_price.fetch_gold_xauusd") as mock_fn:
            mock_df = pd.DataFrame({"close": [2000.0]})
            mock_fn.return_value = mock_df

            result = fetch_gold_price(period="1y")

            mock_fn.assert_called_once_with(period="1y")
            assert not result.empty

    def test_delegates_to_etf(self):
        """source='gld' 时委托给 fetch_gold_etf（覆盖 line 109）"""
        with patch("gold_agent.data.gold_price.fetch_gold_etf") as mock_fn:
            mock_df = pd.DataFrame({"close": [190.0]})
            mock_fn.return_value = mock_df

            result = fetch_gold_price(source="gld", period="6mo")

            mock_fn.assert_called_once_with(period="6mo")
            assert not result.empty

    def test_delegates_to_akshare(self):
        """source='shfe' 时委托给 fetch_gold_spot_akshare（覆盖 line 111）"""
        with patch("gold_agent.data.gold_price.fetch_gold_spot_akshare") as mock_fn:
            mock_df = pd.DataFrame({"close": [480.0]})
            mock_fn.return_value = mock_df

            result = fetch_gold_price(source="shfe")

            mock_fn.assert_called_once_with(365)
            assert not result.empty

    def test_delegates_to_akshare_with_period_days(self):
        """source='shfe' 时按 period 转换为天数"""
        with patch("gold_agent.data.gold_price.fetch_gold_spot_akshare") as mock_fn:
            mock_fn.return_value = pd.DataFrame({"close": [480.0]})

            result = fetch_gold_price(source="shfe", period="3mo")

            mock_fn.assert_called_once_with(90)
            assert not result.empty


class TestGoldPeriodHelpers:
    """金价缓存 key 和周期换算规则"""

    def test_gold_cache_key_includes_source_and_period(self):
        assert gold_cache_key("intl", "1mo") == "gold_intl_1mo"
        assert gold_cache_key("intl", "1y") == "gold_intl_1y"

    def test_period_to_days(self):
        assert period_to_days("1mo") == 30
        assert period_to_days("5y") == 1825
        assert period_to_days("unknown") == 365

    def test_period_to_months(self):
        assert period_to_months("1mo") == 1
        assert period_to_months("5y") == 60
        assert period_to_months("unknown") == 12
