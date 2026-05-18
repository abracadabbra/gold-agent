# 提升测试覆盖率

## Goal

为 GoldAgent 项目所有核心模块补充单元测试，使覆盖率达到可维护的水平。

## Current State

- `tests/unit/` 仅 2 个文件（test_indicators.py, test_signals.py）
- 15+ 源文件零测试覆盖

## Requirements

分批次覆盖所有核心模块：

1. Data 层：gold_price, macro, news, cache
2. Quant 层：predictor (Prophet), backtest engine
3. Debate 层：agents, engine, llm, prompts
4. API 层：analysis, debate, backtest, websocket 路由
5. Config + DB models

## Acceptance Criteria

- [ ] Data 层模块单元测试通过
- [ ] Quant 层新增测试通过
- [ ] Debate 层测试通过（LLM 调用 mock）
- [ ] API 路由测试通过（FastAPI TestClient）
- [ ] Config + DB 模型测试通过
- [ ] `ruff check` + `mypy` 无新增错误

## Out of Scope

- 集成测试（依赖外部服务 / Docker）
- 前端测试
- E2E 测试

## Child Tasks

- 01-data-layer-tests — data/ 模块（gold_price, macro, news, cache）
- 02-quant-layer-tests — quant/ 模块（predictor, backtest engine）
- 03-debate-layer-tests — debate/ 模块（agents, engine, llm, prompts）
- 04-api-layer-tests — api/ 路由（FastAPI TestClient）
- 05-config-db-tests — config.py + db/models.py
