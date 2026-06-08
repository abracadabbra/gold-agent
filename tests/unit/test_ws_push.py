"""WebSocket 定时推送任务单元测试 — periodic_*_push"""

import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


def _meta(row_count: int, *, expected_frequency: str = "daily") -> dict:
    return {
        "as_of": "2024-01-05T00:00:00",
        "latest_date": "2024-01-05T00:00:00",
        "fetched_at": "2024-01-05T08:00:00+00:00",
        "cached_at": "2024-01-05T07:55:00+00:00",
        "row_count": row_count,
        "stale": False,
        "source_status": "cache",
        "missing_rate": 0.0,
        "quality_score": 95,
        "expected_frequency": expected_frequency,
    }


def _fake_gold_df():
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=5, freq="D"),
        "open": [2000.0] * 5,
        "high": [2010.0] * 5,
        "low": [1990.0] * 5,
        "close": [2005.0] * 5,
        "volume": [10000] * 5,
    })


def _fake_signal():
    from gold_agent.quant.signals import Signal, TradeSignal
    return TradeSignal(
        signal=Signal.BUY,
        score=50.0,
        confidence=0.7,
        reasons=["MA 多头排列", "RSI 中性"],
        stop_loss=1950.0,
        take_profit=2100.0,
    )


@pytest.fixture
def cancel_after_one():
    """让 asyncio.sleep 第一次调用时取消任务"""
    async def mock_sleep(delay):
        raise asyncio.CancelledError()

    with patch("asyncio.sleep", mock_sleep):
        yield


class TestPeriodicPricePush:
    """测试 periodic_price_push"""

    @pytest.mark.asyncio
    async def test_push_price_on_data(self, cancel_after_one):
        with patch("gold_agent.api.websocket.cache.get_with_meta") as mock_cache:
            mock_cache.return_value = (_fake_gold_df(), _meta(5))

            with patch("gold_agent.api.websocket.push_price_update") as mock_push:
                mock_push.return_value = None

                with patch("gold_agent.api.websocket.save_gold_prices") as mock_save:
                    mock_save.return_value = 5

                    with patch("gold_agent.api.websocket.SessionLocal") as mock_session:
                        mock_session.return_value.__enter__.return_value = MagicMock()

                        with pytest.raises(asyncio.CancelledError):
                            from gold_agent.api.websocket import periodic_price_push
                            await periodic_price_push(interval_seconds=1)

                        mock_cache.assert_called_once()
                        _, kwargs = mock_cache.call_args
                        assert kwargs["key"] == "gold_intl_1mo"
                        assert kwargs["period"] == "1mo"
                        assert kwargs["months"] == 1
                        assert kwargs["expected_frequency"] == "daily"
                        mock_push.assert_called_once()
                        pushed = mock_push.call_args.args[0]
                        assert pushed["meta"]["source_status"] == "cache"
                        assert pushed["meta"]["row_count"] == 5
                        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_empty_data(self, cancel_after_one):
        with patch("gold_agent.api.websocket.cache.get_with_meta") as mock_cache:
            mock_cache.return_value = (pd.DataFrame(), _meta(0))

            with patch("gold_agent.api.websocket.push_price_update") as mock_push:
                with patch("gold_agent.api.websocket.save_gold_prices") as mock_save:

                    with pytest.raises(asyncio.CancelledError):
                        from gold_agent.api.websocket import periodic_price_push
                        await periodic_price_push(interval_seconds=1)

                    mock_push.assert_not_called()
                    mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_cache_exception(self, cancel_after_one):
        with patch("gold_agent.api.websocket.cache.get_with_meta") as mock_cache:
            mock_cache.side_effect = Exception("cache error")

            with patch("gold_agent.api.websocket.push_price_update") as mock_push:
                with patch("gold_agent.api.websocket.logger") as mock_log:

                    with pytest.raises(asyncio.CancelledError):
                        from gold_agent.api.websocket import periodic_price_push
                        await periodic_price_push(interval_seconds=1)

                    mock_log.error.assert_called()
                    mock_push.assert_not_called()


class TestPeriodicSignalPush:
    """测试 periodic_signal_push"""

    @pytest.mark.asyncio
    async def test_push_signal_on_data(self, cancel_after_one):
        with patch("gold_agent.api.websocket.cache.get_with_meta") as mock_cache:
            mock_cache.return_value = (_fake_gold_df(), _meta(5))

            with patch("gold_agent.api.websocket.generate_signal") as mock_gen:
                mock_gen.return_value = _fake_signal()

                with patch("gold_agent.api.websocket.get_signal_summary") as mock_summary:
                    mock_summary.return_value = "signal summary text"

                    with patch("gold_agent.api.websocket.push_signal_update") as mock_push:
                        with patch("gold_agent.api.websocket.save_trade_signal") as mock_save:
                            mock_save.return_value = True

                            with patch("gold_agent.api.websocket.SessionLocal") as mock_session:
                                mock_session.return_value.__enter__.return_value = MagicMock()

                                with pytest.raises(asyncio.CancelledError):
                                    from gold_agent.api.websocket import periodic_signal_push
                                    await periodic_signal_push(interval_seconds=1)

                                _, kwargs = mock_cache.call_args
                                assert kwargs["key"] == "gold_intl_1y"
                                assert kwargs["period"] == "1y"
                                assert kwargs["months"] == 12
                                assert kwargs["expected_frequency"] == "daily"
                                mock_push.assert_called_once()
                                pushed = mock_push.call_args.args[0]
                                assert pushed["meta"]["quality_score"] == 95
                                mock_save.assert_called_once()
                                mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_empty_data(self, cancel_after_one):
        with patch("gold_agent.api.websocket.cache.get_with_meta") as mock_cache:
            mock_cache.return_value = (pd.DataFrame(), _meta(0))

            with patch("gold_agent.api.websocket.push_signal_update") as mock_push:
                with patch("gold_agent.api.websocket.save_trade_signal") as mock_save:

                    with pytest.raises(asyncio.CancelledError):
                        from gold_agent.api.websocket import periodic_signal_push
                        await periodic_signal_push(interval_seconds=1)

                    mock_push.assert_not_called()
                    mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_generate_signal_exception(self, cancel_after_one):
        """generate_signal 异常时被 except 捕获并记录日志"""
        with patch("gold_agent.api.websocket.cache.get_with_meta") as mock_cache:
            mock_cache.return_value = (_fake_gold_df(), _meta(5))

            with patch("gold_agent.api.websocket.generate_signal") as mock_gen:
                mock_gen.side_effect = Exception("signal generation failed")

                with patch("gold_agent.api.websocket.logger") as mock_log:
                    with pytest.raises(asyncio.CancelledError):
                        from gold_agent.api.websocket import periodic_signal_push
                        await periodic_signal_push(interval_seconds=1)

                    mock_log.error.assert_called()


class TestPeriodicNewsPush:
    """测试 periodic_news_push"""

    @pytest.mark.asyncio
    async def test_push_news_on_data(self, cancel_after_one):
        news_df = pd.DataFrame({
            "title": ["金价上涨", "美元走弱"],
            "sentiment_score": [0.5, -0.3],
            "sentiment_label": ["bullish", "bearish"],
            "source": ["reuters", "reuters"],
        })

        with patch("gold_agent.api.websocket.cache.get_with_meta") as mock_cache:
            mock_cache.return_value = (news_df, _meta(2, expected_frequency="intraday"))

            with patch("gold_agent.api.websocket.push_news_update") as mock_push:
                with pytest.raises(asyncio.CancelledError):
                    from gold_agent.api.websocket import periodic_news_push
                    await periodic_news_push(interval_seconds=1)

                mock_cache.assert_called_once()
                _, kwargs = mock_cache.call_args
                assert kwargs["key"] == "news_sentiment"
                assert kwargs["ttl"] == 300
                assert kwargs["max_stale_days"] == 1
                assert kwargs["expected_frequency"] == "intraday"
                assert callable(kwargs["db_save_fn"])
                mock_push.assert_called_once()
                call_data = mock_push.call_args[0][0]
                assert call_data["total"] == 2
                assert call_data["avg_sentiment"] == 0.1
                assert call_data["label"] == "neutral"
                assert call_data["meta"]["expected_frequency"] == "intraday"

    @pytest.mark.asyncio
    async def test_handles_empty_data(self, cancel_after_one):
        with patch("gold_agent.api.websocket.cache.get_with_meta") as mock_cache:
            mock_cache.return_value = (pd.DataFrame(), _meta(0, expected_frequency="intraday"))

            with patch("gold_agent.api.websocket.push_news_update") as mock_push:
                with pytest.raises(asyncio.CancelledError):
                    from gold_agent.api.websocket import periodic_news_push
                    await periodic_news_push(interval_seconds=1)

                mock_push.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_fetch_exception(self, cancel_after_one):
        """cache.get_with_meta 异常时被 except 捕获并记录日志"""
        with patch("gold_agent.api.websocket.cache.get_with_meta") as mock_cache:
            mock_cache.side_effect = Exception("fetch failed")

            with patch("gold_agent.api.websocket.logger") as mock_log:
                with pytest.raises(asyncio.CancelledError):
                    from gold_agent.api.websocket import periodic_news_push
                    await periodic_news_push(interval_seconds=1)

                mock_log.error.assert_called()
