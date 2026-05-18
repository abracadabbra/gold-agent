# 🥇 GoldAgent — 黄金价格分析 Agent

> 让数据说话，让 AI 辩论，让决策有据可依

量化 + LLM 混合驱动的黄金价格分析系统，具备数据采集、技术分析、时序预测、多 Agent 辩论和策略回测能力。

## ✨ 核心特性

- **📊 数据采集**: akshare (国内金价) + yfinance (国际金价) + FRED (宏观数据) + RSS (新闻情绪)
- **📈 技术指标**: 200+ 指标 (MA/RSI/MACD/布林带/ATR/ADX/Supertrend)
- **🔮 时序预测**: Prophet + 外部回归因子 (美元指数/美债/VIX)
- **🤖 多 Agent 辩论**: 看多方 vs 看空方 vs 数据审计员 → 仲裁官裁决
- **📉 策略回测**: backtrader 引擎, 内置 3 种策略, 完整绩效指标
- **🌐 REST API**: FastAPI, 自动文档, WebSocket 流式推送

## 🏗️ 架构

```
前端仪表盘 (Next.js + lightweight-charts)
        ↕ REST / WebSocket
FastAPI 后端
  ├── 数据采集层 (akshare + yfinance + FRED)
  ├── 量化分析层 (pandas-ta + Prophet + backtrader)
  └── LLM 辩论层 (4 Agent 多角色辩论)
        ↕
PostgreSQL + Redis + Parquet 缓存
```

## 🚀 快速开始

```bash
# 1. 克隆项目
git clone <repo-url>
cd gold-agent

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 4. 启动服务
uvicorn gold_agent.main:app --reload --host 0.0.0.0 --port 8000

# 5. 访问 API 文档
open http://localhost:8000/docs
```

## 📡 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/analysis/gold` | GET | 获取金价数据 |
| `/api/analysis/indicators` | GET | 技术指标 |
| `/api/analysis/signal` | GET | 交易信号 |
| `/api/analysis/predict` | GET | 时序预测 |
| `/api/analysis/macro` | GET | 宏观数据 |
| `/api/analysis/news` | GET | 新闻情绪 |
| `/api/debate/run` | POST | 运行多 Agent 辩论 |
| `/api/debate/quick` | GET | 快速分析 |
| `/api/backtest/run` | GET | 运行回测 |
| `/api/backtest/strategies` | GET | 列出策略 |

## 🤖 多 Agent 辩论

| Agent | 角色 | 模型 | 职责 |
|-------|------|------|------|
| 🟢 看多方 | Bull Advocate | GPT-4.1 | 构建看多论点 |
| 🔴 看空方 | Bear Challenger | Claude Sonnet | 质疑反驳 |
| 🔍 审计员 | Data Auditor | GPT-4.1-mini | 验证数据 |
| ⚖️ 仲裁官 | Chief Arbitrator | GPT-4.1 | 综合裁决 |

## 📈 内置策略

- **Golden Cross**: MA 金叉死叉 + RSI 过滤 + ATR 止损
- **RSI Mean Reversion**: RSI 超卖买入 + 超买卖出
- **MACD**: MACD 金叉 + 成交量确认

## 📁 项目结构

```
gold-agent/
├── src/gold_agent/
│   ├── config.py          # 配置管理
│   ├── main.py            # FastAPI 入口
│   ├── data/              # 数据采集层
│   ├── quant/             # 量化分析层
│   │   ├── indicators.py  # 技术指标
│   │   ├── predictor.py   # Prophet 预测
│   │   ├── signals.py     # 信号生成
│   │   └── backtest/      # 回测引擎
│   ├── debate/            # LLM 辩论层
│   └── api/               # API 路由
├── tests/
├── docs/
└── frontend/              # Next.js 前端 (TODO)
```

## 📄 License

MIT
