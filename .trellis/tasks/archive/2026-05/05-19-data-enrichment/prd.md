# 新增金价报告数据源

## Goal

为金价分析报告补充 7 类缺失数据，所有数据通过非爬虫方式获取（官方 API / Python 库 / 结构化文件下载）。同时更新前端报告页展示新增数据。

## Requirements

### 数据层

1. **央行黄金储备（Central Bank Reserves）**
   - 通过 IMF IFS REST API 获取各国央行黄金持仓
   - 支持按国家查询（中国、美国、俄罗斯、印度等 TOP10）
   - 月度频率数据

2. **CFTC COT 持仓报告**
   - 通过 `cot_reports` 库获取 COMEX 黄金期货持仓
   - 包含投机净多头、商业持仓、未平仓合约
   - 每周频率数据

3. **黄金 ETF 流量（ETF Flow）**
   - 通过 WGC 官网 XLSX 下载获取全球黄金 ETF 持仓和流量
   - 包含 GLD、IAU 等主要 ETF 的日度/月度流入流出
   - 按区域（北美、欧洲、亚洲）拆分

4. **地缘政治风险指数（GPR Index）**
   - 通过静态 XLS 文件下载（matteoiacoviello.com）
   - 支持全球总指数 + 国家细分指数
   - 月度/日度频率

5. **CME FedWatch 利率预期**
   - 通过 `cme-fedwatch` 库获取 FOMC 会议加息概率
   - 包含各次会议的降息/维持/加息概率分布
   - 每日更新

6. **中国宏观数据**
   - 通过 akshare（已完成安装）获取中国 CPI、PMI、PPI、M2、GDP、LPR、人民币汇率
   - 月度频率

7. **黄金生产成本（AISC）**
   - 通过 WGC 官网 XLSX 下载获取全球黄金 AISC 数据
   - 季度频率

### 架构要求

- 每个数据源独立文件，放在 `src/gold_agent/data/` 下
- 复用现有 `DataCache` 缓存层，根据更新频率设定 TTL
- 每个数据函数签名统一：`fetch_xxx(**kwargs) -> pd.DataFrame`
- 新增 API 端点 `GET /api/analysis/extra` 聚合返回所有补充数据
- 前端新增对应展示卡片

### 非功能性要求

- 新引入的 PyPI 包加入 `pyproject.toml` 依赖
- 写单元测试（mock 外部调用）
- 缓存失效策略与数据更新频率匹配

## Acceptance Criteria

- [ ] 7 个数据源均能通过统一 `DataCache.get()` 获取并返回非空 DataFrame
- [ ] `GET /api/analysis/extra` 返回完整 JSON，包含所有 7 类数据
- [ ] 前端 dashboard 展示所有新增数据卡片，加载状态/错误处理正常
- [ ] `ruff check src/ tests/` 无新增错误
- [ ] `mypy src/` 无新增类型错误
- [ ] 单元测试覆盖所有新数据函数（mock 外部调用）

## Out of Scope

- 财经日历数据（需爬虫，暂缓）
- WebSocket 实时推送新增数据
- 数据可视化图表（仅展示数值表格，不引入 chart 库）
- 数据历史回填
