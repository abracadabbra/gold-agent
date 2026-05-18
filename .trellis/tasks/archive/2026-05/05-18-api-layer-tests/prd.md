# API 层测试

## Goal

为 `src/gold_agent/api/` 模块补充单元测试：analysis, debate, backtest, websocket。

## Approach

- 使用 FastAPI `TestClient`
- Mock 所有下层依赖（cache, quant, debate engine）
- 测试 HTTP 状态码、响应结构、异常处理

## Acceptance Criteria

- [ ] analysis: 4 个 GET 端点成功路径和异常路径
- [ ] debate: `/run` POST 和 `/quick` GET 端点
- [ ] backtest: `/strategies` 和 `/run` 端点和 501 回退
- [ ] websocket: 连接/订阅/取消订阅/ping
- [ ] ruff check 通过
