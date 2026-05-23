# Research: hexun 替代源调研

## hexun 问题
- 非标准 RSS XML（`<Data><News>` 结构，无 `<item>`）
- 标题 base64 加密
- 数据全部是 2015 年
- 有反爬 JS 验证

## 替代方案

### ✅ 推荐：中国新闻网财经
- URL: `https://www.chinanews.com.cn/rss/finance.xml`
- 标准 RSS 2.0，UTF-8
- 综合财经新闻，包含黄金市场报道
- 无反爬，无依赖

### ✅ 已确认：东方财富网
- URL: `http://rss.eastmoney.com/rss_partener.xml`
- 96 条，标准 RSS 2.0，UTF-8
- CDATA 标题，现有解析器正确处理
