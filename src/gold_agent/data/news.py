"""新闻情绪数据采集 — RSS + 关键词提取"""

import re

import httpx
import pandas as pd
import logging
logger = logging.getLogger(__name__)


# 国内新闻源名列表（前端用此区分国内/国外）
DOMESTIC_SOURCES = ["hexun_gold", "eastmoney", "google_news_cn"]

# 黄金相关 RSS 源
RSS_FEEDS = {
    "google_news": "https://news.google.com/rss/search?q=gold+price&hl=en-US&gl=US&ceid=US:en",
    "google_news_cn": "https://news.google.com/rss/search?q=黄金+价格&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    "google_reuters": "https://news.google.com/rss/search?q=site:reuters.com+gold&hl=en-US",
    "mining_com": "https://www.mining.com/feed",
    "hexun_gold": "https://news.hexun.com/rss/gold.xml",
    "eastmoney": "http://rss.eastmoney.com/rss_partener.xml",
}

# 情绪关键词
BULLISH_KEYWORDS = [
    "rally", "surge", "record high", "safe haven", "inflation hedge",
    "central bank buying", "rate cut", "dollar weak", "geopolitical",
    "央行购金", "创新高", "避险", "降息", "美元走弱",
    "金价上涨", "大涨", "看涨", "利多", "反弹", "走高",
]

BEARISH_KEYWORDS = [
    "selloff", "plunge", "rate hike", "dollar strong", "risk-on",
    "yield surge", "hawkish", "tightening", "deflation",
    "加息", "暴跌", "美元走强", "风险偏好", "鹰派",
    "金价下跌", "大跌", "看跌", "利空", "回落", "走低",
]


def fetch_rss_news(feed_name: str = "google_news", max_items: int = 20) -> list[dict]:
    """
    从 RSS 源获取新闻标题和链接

    Returns:
        [{"title": str, "link": str, "published": str, "source": str}, ...]
    """
    url = RSS_FEEDS.get(feed_name)
    if not url:
        raise ValueError(f"未知 RSS 源: {feed_name}, 可选: {list(RSS_FEEDS.keys())}")

    logger.info(f"获取 RSS 新闻: {feed_name}")

    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"RSS 请求失败: {e}")
        return []

    # 检测 XML 编码（处理 GBK 等非 UTF-8 源）
    raw = resp.content
    enc_match = re.search(rb'encoding=["\']([^"\']+)["\']', raw[:500])
    encoding = enc_match.group(1).decode("ascii", errors="ignore") if enc_match else "utf-8"
    xml_text = raw.decode(encoding, errors="replace")

    # 简单 XML 解析 (避免引入 lxml 依赖)
    items = []
    entries = re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL)

    for entry in entries[:max_items]:
        title = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        link = re.search(r"<link>(.*?)</link>", entry, re.DOTALL)
        pub_date = re.search(r"<pubDate>(.*?)</pubDate>", entry, re.DOTALL)

        if title:
            # 清理 CDATA
            t = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title.group(1).strip())
            items.append({
                "title": t,
                "link": link.group(1).strip() if link else "",
                "published": pub_date.group(1).strip() if pub_date else "",
                "source": feed_name,
            })

    logger.info(f"获取到 {len(items)} 条新闻")
    return items


def analyze_sentiment(text: str) -> dict:
    """
    基于关键词的简单情绪分析

    Returns:
        {"score": float, "label": str, "bull_hits": list, "bear_hits": list}
    """
    text_lower = text.lower()

    bull_hits = [kw for kw in BULLISH_KEYWORDS if kw.lower() in text_lower]
    bear_hits = [kw for kw in BEARISH_KEYWORDS if kw.lower() in text_lower]

    total = len(bull_hits) + len(bear_hits)
    if total == 0:
        score = 0.0
    else:
        score = (len(bull_hits) - len(bear_hits)) / total  # -1 到 +1

    if score > 0.2:
        label = "bullish"
    elif score < -0.2:
        label = "bearish"
    else:
        label = "neutral"

    return {
        "score": round(score, 3),
        "label": label,
        "bull_hits": bull_hits,
        "bear_hits": bear_hits,
    }


def fetch_news_with_sentiment(max_items: int = 30) -> pd.DataFrame:
    """获取所有 RSS 源新闻并分析情绪"""
    all_news = []

    for feed_name in RSS_FEEDS:
        try:
            items = fetch_rss_news(feed_name, max_items=max_items)
            all_news.extend(items)
        except Exception as e:
            logger.error(f"RSS {feed_name} 失败: {e}")

    if not all_news:
        logger.warning("未获取到任何新闻")
        return pd.DataFrame(columns=["title", "link", "published", "source", "sentiment_score", "sentiment_label"])  # noqa: E501

    df = pd.DataFrame(all_news)

    # 情绪分析
    sentiments = df["title"].apply(analyze_sentiment)
    df["sentiment_score"] = sentiments.apply(lambda x: x["score"])
    df["sentiment_label"] = sentiments.apply(lambda x: x["label"])
    df["bull_hits"] = sentiments.apply(lambda x: ",".join(x["bull_hits"]))
    df["bear_hits"] = sentiments.apply(lambda x: ",".join(x["bear_hits"]))

    # 计算整体情绪
    avg_score = df["sentiment_score"].mean()
    logger.info(f"新闻情绪分析完成: {len(df)} 条, 平均得分 {avg_score:.3f}")

    return df.sort_values("sentiment_score", ascending=False).reset_index(drop=True)
