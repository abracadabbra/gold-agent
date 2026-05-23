# 扩充国内新闻数据源

## Goal

增加国内新闻 RSS 数据源，解决当前 "国内新闻明细（本次样本）" 只有 1-2 条的问题，让展示内容更丰富。

## What I already know

- 当前国内新闻唯一来源是 `google_news_cn` RSS feed（搜索"黄金 价格"）
- 数据采集在 `src/gold_agent/data/news.py`，4 个 RSS feed 统一采集
- 国内/国外分离纯属前端 filter：`item.source === 'google_news_cn'`
- 前端展示在 `frontend/src/app/page.tsx`，国内新闻明细显示 8 条
- 字段只有 `title`、`link`、`published`、`source`、`sentiment_score`、`sentiment_label`、`bull_hits`、`bear_hits`
- 数据库有 `news_articles` 表，包含所有字段

## Assumptions (temporary)

- 保持现有代码结构不变：所有新闻统一采集，前端 filter 分离
- 不引入正文抓取（纯 RSS headline 方案）
- 不改动现有缓存机制（5min TTL）

## Decision (ADR-lite)

**Context**: 当前国内新闻仅 `google_news_cn` 一条源，只返回 1-2 条
**Decision**:
1. 新增 和讯网黄金 RSS + 东方财富网 RSS 两个 Native RSS
2. 前端用白名单列表匹配多个国内源（不改后端 schema）
**Consequences**: 改动最小，零新依赖；国内新闻预计提升到 15-30 条

## Requirements (evolving)

- [ ] 国内新闻至少能稳定展示 8+ 条
- [ ] 保持情感分析（sentiment）功能
- [ ] 不降低采集性能
- [ ] 兼容现有前端展示逻辑

## Acceptance Criteria (evolving)

- [ ] 新增 2+ 个国内黄金/财经新闻 RSS feed
- [ ] 运行时国内新闻数量从 1-2 条提升到 8+ 条
- [ ] `ruff check` 和 `mypy` 通过
- [ ] 前端 "国内新闻明细" 能正常展示所有源的内容
- [ ] 情感分析对新源内容依然有效

## Out of Scope

- 文章正文抓取
- 增加新的 API 端点
- 改数据库 schema
- 前端 UI 重构

## Technical Notes

- 数据采集: `src/gold_agent/data/news.py` — `RSS_FEEDS` dict + `fetch_news_with_sentiment()`
- 前端分离: `frontend/src/app/page.tsx:306-316` — `item.source === 'google_news_cn'`
- 测试: `tests/unit/test_news.py` — 覆盖 RSS 解析和情感分析
- 数据库: `src/gold_agent/db/models.py` — `NewsArticle` 表

## Research References

* [`research/domestic-rss-sources.md`](research/domestic-rss-sources.md) — 找到 5 个可用源（2 Native RSS + 3 通过 RSSHub）

## Feasible approaches

**方案 A：仅加 Native RSS（推荐，最小改动）**

- 在 `RSS_FEEDS` 添加 和讯网黄金 + 东方财富网
- 零新依赖，预计国内新闻从 1-2 条 → 15-30 条
- 和讯网是 GBK 编码，需在 feedparser 中处理

**方案 B：Native RSS + RSSHub 公共实例**

- 同上 + 金十数据 + 华尔街见闻 via RSSHub 公共实例
- 预计国内新闻 → 30-50 条
- 依赖公共实例稳定性

**方案 C：Native RSS + 自建 RSSHub**

- 方案 B + Docker 自建 RSSHub
- 生产级可靠性，但需要维护额外服务
