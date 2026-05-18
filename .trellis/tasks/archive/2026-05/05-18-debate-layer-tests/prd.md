# Debate 层测试

## Goal

为 `src/gold_agent/debate/` 模块补充单元测试。

## Modules to test

- `debate/prompts.py` — 4 个 Agent 的 System Prompt 常量
- `debate/agents.py` — AgentConfig dataclass + get_agents()
- `debate/llm.py` — OpenAI 兼容调用封装
- `debate/engine.py` — 辩论编排引擎

## Approach

- Mock `openai.AsyncOpenAI` 避免真实 API 调用
- Mock `chat_completion`/`chat_completion_json` 测试 engine
- 测试 dataclass 的序列化和 to_summary 格式化

## Acceptance Criteria

- [ ] prompts: 验证 4 个 system prompt 常量存在且有内容
- [ ] agents: AgentConfig 字段/get_agents 返回 4 个配置
- [ ] llm: chat_completion/chat_completion_json 成功/异常/JSON fallback
- [ ] engine: DebateRound/DebateResult/DebateEngine 编排流程
- [ ] ruff check 通过
