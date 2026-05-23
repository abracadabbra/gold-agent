# Research: 国内财经新闻 RSS 源调研

## 测试结果

### ✅ 可直接使用的 Native RSS（无需额外依赖）

| 源 | URL | 状态 | 黄金相关性 | 可靠性 |
|---|-----|------|-----------|--------|
| **和讯网黄金** | `https://news.hexun.com/rss/gold.xml` | ✅ 200 OK，Gold-dedicated | ★★★★★ | ★★★★ |
| **东方财富网** | `http://rss.eastmoney.com/rss_partener.xml` | ✅ 200 OK，综合财经 | ★★★★ | ★★★★★ |

### ✅ 可通过 RSSHub 获取

| 源 | RSSHub Route | 黄金相关性 | 可靠性 |
|---|-------------|-----------|--------|
| **金十数据** | `/jin10` | ★★★★★ | ★★★★ |
| **华尔街见闻** | `/wallstreetcn/news/global` | ★★★★ | ★★★★ |
| **财联社** | `/cls/telegraph` | ★★★ | ★★★★ |

### ❌ 不可用

- 新浪财经 RSS — 全部 404，已停止服务
- 金融界 RSS — 全部 404，2013 年后未维护
- 华尔街见闻官方 RSS — 已失效

## 推荐方案

### 方案 A：仅加 Native RSS（最小改动）
- 添加 和讯网黄金 + 东方财富网 到 `RSS_FEEDS`
- 零依赖，预计国内新闻从 1-2 条增加到 15-30 条

### 方案 B：Native RSS + RSSHub
- 同上 + 金十数据 + 华尔街见闻 via RSSHub
- 需要一个稳定的 RSSHub 公共实例
- 预计国内新闻增加到 30-50 条

### 方案 C：Native RSS + 自建 RSSHub
- 方案 B + Docker 自建 RSSHub
- 生产可用，但需要维护额外服务
