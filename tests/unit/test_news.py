"""新闻情绪数据采集单元测试"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from gold_agent.data.news import analyze_sentiment, fetch_news_with_sentiment, fetch_rss_news


class TestAnalyzeSentiment:
    """测试情绪分析函数"""

    def test_bullish_text(self):
        """看涨文本应返回 bullish"""
        result = analyze_sentiment("gold rally safe haven buying")
        assert result["score"] > 0.2
        assert result["label"] == "bullish"
        assert len(result["bull_hits"]) > 0
        assert result["bear_hits"] == []

    def test_bearish_text(self):
        """看跌文本应返回 bearish"""
        result = analyze_sentiment("rate hike causes selloff in gold")
        assert result["score"] < -0.2
        assert result["label"] == "bearish"
        assert len(result["bear_hits"]) > 0
        assert result["bull_hits"] == []

    def test_mixed_text(self):
        """混合情绪文本应返回 neutral"""
        result = analyze_sentiment("gold rally but rate hike concerns")
        assert result["label"] == "neutral"

    def test_neutral_text(self):
        """无关键词文本应返回 neutral"""
        result = analyze_sentiment("gold price today at market open")
        assert result["score"] == 0.0
        assert result["label"] == "neutral"
        assert result["bull_hits"] == []
        assert result["bear_hits"] == []

    def test_empty_text(self):
        """空文本应返回 neutral"""
        result = analyze_sentiment("")
        assert result["score"] == 0.0
        assert result["label"] == "neutral"

    def test_case_insensitive(self):
        """情绪关键词匹配不区分大小写"""
        result = analyze_sentiment("GOLD RALLY SAFE HAVEN")
        assert result["label"] == "bullish"
        assert result["score"] > 0.2

    def test_score_is_rounded(self):
        """分数应保留三位小数"""
        result = analyze_sentiment("rally surge")
        assert isinstance(result["score"], float)
        # rally + surge = 2 bull, 0 bear → score = 2/2 = 1.0
        assert result["score"] == 1.0


RSS_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Test Feed</title>
{items}
</channel>
</rss>"""

ITEM_TEMPLATE = """<item>
<title>{title}</title>
<link>{link}</link>
<pubDate>{pub_date}</pubDate>
<description>test</description>
</item>"""


def make_rss_xml(items):
    """生成模拟 RSS XML"""
    entries = "\n".join(
        ITEM_TEMPLATE.format(**item) for item in items
    )
    return RSS_XML_TEMPLATE.format(items=entries)


class TestFetchRssNews:
    """测试 RSS 新闻获取"""

    def test_success(self):
        """正常拉取应解析出 title/link/pubDate"""
        xml = make_rss_xml([
            {"title": "Gold Hits Record High", "link": "http://example.com/1",
             "pub_date": "Mon, 01 Jan 2024 00:00:00 GMT"},
            {"title": "Central Bank Buying Gold", "link": "http://example.com/2",
             "pub_date": "Tue, 02 Jan 2024 00:00:00 GMT"},
        ])

        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = xml
            mock_get.return_value = mock_response

            result = fetch_rss_news(feed_name="google_news", max_items=10)

            assert len(result) == 2
            assert result[0]["title"] == "Gold Hits Record High"
            assert result[0]["link"] == "http://example.com/1"
            assert result[0]["published"] == "Mon, 01 Jan 2024 00:00:00 GMT"
            assert result[0]["source"] == "google_news"

    def test_cdata_cleaned(self):
        """CDATA 包裹的标题应被清理"""
        xml = make_rss_xml([
            {"title": "<![CDATA[Gold Rally Continues]]>", "link": "http://example.com",
             "pub_date": "Mon, 01 Jan 2024 00:00:00 GMT"},
        ])

        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = xml
            mock_get.return_value = mock_response

            result = fetch_rss_news(feed_name="google_news")

            assert result[0]["title"] == "Gold Rally Continues"
            assert "<![CDATA[" not in result[0]["title"]

    def test_unknown_feed_raises_value_error(self):
        """未知 RSS 源应触发 ValueError"""
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock()

            with pytest.raises(ValueError, match="未知 RSS 源"):
                fetch_rss_news(feed_name="unknown_feed")

    def test_http_error_returns_empty_list(self):
        """HTTP 请求失败应返回空列表"""
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("HTTP error")

            result = fetch_rss_news(feed_name="google_news")

            assert result == []

    def test_no_item_entries(self):
        """无 item 条目的 RSS 返回空列表"""
        xml = RSS_XML_TEMPLATE.format(items="")

        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = xml
            mock_get.return_value = mock_response

            result = fetch_rss_news(feed_name="google_news")

            assert result == []

    def test_max_items_respected(self):
        """max_items 参数控制返回数量"""
        items = [
            {"title": f"News {i}", "link": f"http://example.com/{i}",
             "pub_date": f"Mon, {i:02d} Jan 2024 00:00:00 GMT"}
            for i in range(1, 6)
        ]
        xml = make_rss_xml(items)

        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = xml
            mock_get.return_value = mock_response

            result = fetch_rss_news(feed_name="google_news", max_items=3)

            assert len(result) == 3


class TestFetchNewsWithSentiment:
    """测试带情绪的新闻获取"""

    def test_returns_dataframe_with_sentiment_columns(self):
        """返回的 DataFrame 应包含情绪分析列"""
        with patch("gold_agent.data.news.fetch_rss_news") as mock_fetch:
            mock_fetch.return_value = [
                {"title": "Gold rally safe haven demand rises",
                 "link": "http://example.com/1", "published": "Mon, 01 Jan 2024",
                 "source": "google_news"},
                {"title": "Rate hike fears weigh on market",
                 "link": "http://example.com/2", "published": "Tue, 02 Jan 2024",
                 "source": "reuters_gold"},
            ]

            result = fetch_news_with_sentiment()

            assert isinstance(result, pd.DataFrame)
            expected_cols = {"title", "link", "published", "source",
                             "sentiment_score", "sentiment_label",
                             "bull_hits", "bear_hits"}
            assert expected_cols.issubset(set(result.columns))
            assert len(result) == 2

    def test_all_feeds_fail_returns_minimal_df(self):
        """所有 RSS 源失败时返回最小 DataFrame"""
        with patch("gold_agent.data.news.fetch_rss_news") as mock_fetch:
            mock_fetch.side_effect = Exception("RSS error")

            result = fetch_news_with_sentiment()

            assert isinstance(result, pd.DataFrame)
            assert result.empty
            expected_cols = ["title", "link", "published", "source",
                             "sentiment_score", "sentiment_label"]
            assert list(result.columns) == expected_cols

    def test_sorted_by_sentiment_score_descending(self):
        """结果应按情绪分数降序排列"""
        with patch("gold_agent.data.news.fetch_rss_news") as mock_fetch:
            mock_fetch.return_value = [
                {"title": "Rate hike selloff continues",
                 "link": "http://example.com/1", "published": "",
                 "source": "test"},
                {"title": "Gold rally safe haven",
                 "link": "http://example.com/2", "published": "",
                 "source": "test"},
            ]

            result = fetch_news_with_sentiment()

            # 第一条应该是 bullish (rally safe haven), 第二条 bearish (rate hike selloff)
            assert result["sentiment_score"].iloc[0] > result["sentiment_score"].iloc[1]
