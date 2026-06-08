"""辩论流程编排 — 多 Agent 协作的核心引擎"""

import json
import re
from dataclasses import dataclass
from collections.abc import AsyncGenerator

import logging
logger = logging.getLogger(__name__)

from gold_agent.config import settings
from gold_agent.debate.agents import get_agents, AgentConfig
from gold_agent.debate.llm import chat_completion


@dataclass
class DebateRound:
    """一轮辩论的结果"""
    agent_name: str
    role: str
    model: str
    content: str          # 原始 LLM 输出
    parsed: dict          # JSON 解析结果
    tokens_used: int = 0


@dataclass
class DebateResult:
    """完整辩论结果"""
    rounds: list[DebateRound]
    bull_argument: dict | None = None
    bear_argument: dict | None = None
    audit_result: dict | None = None
    final_verdict: dict | None = None

    def to_dict(self) -> dict:
        return {
            "bull": self.bull_argument,
            "bear": self.bear_argument,
            "audit": self.audit_result,
            "verdict": self.final_verdict,
        }

    def to_summary(self) -> str:
        """生成人类可读的辩论摘要"""
        lines = ["=" * 60, "📊 黄金多空辩论结果", "=" * 60, ""]

        if self.bull_argument:
            lines.append("🟢 看多方观点:")
            for arg in self.bull_argument.get("arguments", []):
                lines.append(f"  • {arg.get('point', '')} [{arg.get('strength', '')}]")
                lines.append(f"    依据: {arg.get('evidence', '')}")
            lines.append(f"  置信度: {self.bull_argument.get('confidence', 'N/A')}%")
            lines.append("")

        if self.bear_argument:
            lines.append("🔴 看空方观点:")
            for arg in self.bear_argument.get("arguments", []):
                lines.append(f"  • {arg.get('point', '')} [{arg.get('strength', '')}]")
                lines.append(f"    依据: {arg.get('evidence', '')}")
            lines.append(f"  置信度: {self.bear_argument.get('confidence', 'N/A')}%")
            lines.append("")

        if self.audit_result:
            lines.append("🔍 数据审计:")
            missed = self.audit_result.get("missed_data", [])
            if missed:
                lines.append(f"  遗漏数据: {', '.join(missed)}")
            lines.append(f"  评估: {self.audit_result.get('overall_assessment', '')}")
            lines.append("")

        if self.final_verdict:
            v = self.final_verdict
            emoji_map = {"bullish": "📈", "bearish": "📉", "sideways": "➡️"}
            verdict_emoji = emoji_map.get(v.get("verdict", ""), "")
            lines.append(f"⚖️ 仲裁官裁决: {v.get('verdict', '')} {verdict_emoji}")
            lines.append(f"  置信度: {v.get('confidence', 'N/A')}%")
            pr = v.get("price_range", {})
            lines.append(f"  价格区间: ${pr.get('low', 0):.2f} ~ ${pr.get('high', 0):.2f}")
            lines.append(f"  时间范围: {v.get('time_horizon', '')}")
            lines.append("  核心理由:")
            for r in v.get("key_reasons", []):
                lines.append(f"    • {r}")
            lines.append("  ⚠️ 风险提示:")
            for w in v.get("risk_warnings", []):
                lines.append(f"    • {w}")
            lines.append(f"\n  💡 建议: {v.get('final_advice', '')}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


class DebateEngine:
    """辩论引擎 — 编排 4 个 Agent 的辩论流程"""

    def __init__(self):
        self.agents = get_agents()

    def _build_context(self, data_context: str) -> str:
        """构建注入辩论的上下文"""
        return f"""## 当前市场数据

以下是黄金市场的最新量化数据，你的论点**必须基于这些数据**：

{data_context}

请基于以上数据进行分析，不要编造数据。

如果上下文里出现 `source_status`、`stale`、`quality_score`、
`row_count` 等质量字段，你必须先判断这些数据是否足够新鲜、是否足够可靠：
- `stale=yes` 的数据不能当作实时事实
- `source_status=db_fallback` 或 `source_status=cache` 的数据要结合 `as_of` 一起审慎引用
- `quality_score` 低或 `row_count` 很小的数据，只能作为弱证据，不能支撑强结论
- 当数据质量不足时，应明确说明不确定性，不要过度下结论"""

    async def _run_agent(
        self,
        agent: AgentConfig,
        messages: list[dict],
    ) -> DebateRound:
        """运行单个 Agent"""
        logger.info(f"运行 Agent: {agent.role} ({agent.model})")

        content = await chat_completion(
            messages=messages,
            model=agent.model,
            temperature=agent.temperature,
            max_tokens=settings.debate_max_tokens,
        )

        # 尝试解析 JSON
        parsed = {}
        try:
            # 清理 markdown 代码块
            clean = content
            if "```" in clean:
                match = re.search(r"```(?:json)?\s*(.*?)```", clean, re.DOTALL)
                if match:
                    clean = match.group(1)
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            logger.warning(f"Agent {agent.name} 输出不是有效 JSON，使用原始文本")
            parsed = {"raw_text": content}

        return DebateRound(
            agent_name=agent.name,
            role=agent.role,
            model=agent.model,
            content=content,
            parsed=parsed,
        )

    async def run_debate(self, data_context: str) -> DebateResult:
        """运行完整辩论流程（消费 stream_debate 的完整结果）"""
        async for stage, item in self._debate_rounds(data_context):
            if stage == "complete":
                assert isinstance(item, DebateResult)
                return item
        raise RuntimeError("debate did not complete")

    async def stream_debate(
        self, data_context: str
    ) -> AsyncGenerator[tuple[str, DebateRound | DebateResult], None]:
        async for stage, item in self._debate_rounds(data_context):
            yield stage, item

    async def _debate_rounds(
        self, data_context: str
    ) -> AsyncGenerator[tuple[str, DebateRound | DebateResult], None]:
        """
        4 轮辩论核心逻辑 — 被 run_debate / stream_debate 共用。
        stage_name: bull / bear / audit / verdict / complete
        """
        result = DebateResult(rounds=[])
        context = self._build_context(data_context)

        # ---- Step 1: 看多方 ----
        logger.info("=" * 40 + " Round 1: 看多方 " + "=" * 40)
        bull_round = await self._run_agent(
            self.agents["advocate"],
            [{"role": "system", "content": self.agents["advocate"].system_prompt},
             {"role": "user", "content": context}],
        )
        result.rounds.append(bull_round)
        result.bull_argument = bull_round.parsed
        yield ("bull", bull_round)

        # ---- Step 2: 看空方 ----
        logger.info("=" * 40 + " Round 2: 看空方 " + "=" * 40)
        bear_round = await self._run_agent(
            self.agents["challenger"],
            [{"role": "system", "content": self.agents["challenger"].system_prompt},
             {"role": "user", "content": context}],
        )
        result.rounds.append(bear_round)
        result.bear_argument = bear_round.parsed
        yield ("bear", bear_round)

        # ---- Step 3: 数据审计 ----
        logger.info("=" * 40 + " Round 3: 数据审计 " + "=" * 40)
        audit_round = await self._run_agent(
            self.agents["auditor"],
            [{"role": "system", "content": self.agents["auditor"].system_prompt},
             {"role": "user", "content": f"""{context}

## 看多方论点
{json.dumps(result.bull_argument, ensure_ascii=False, indent=2)}

## 看空方论点
{json.dumps(result.bear_argument, ensure_ascii=False, indent=2)}

请验证以上双方引用的数据是否准确。"""}],
        )
        result.rounds.append(audit_round)
        result.audit_result = audit_round.parsed
        yield ("audit", audit_round)

        # ---- Step 4: 仲裁裁决 ----
        logger.info("=" * 40 + " Round 4: 仲裁裁决 " + "=" * 40)
        arb_round = await self._run_agent(
            self.agents["arbitrator"],
            [{"role": "system", "content": self.agents["arbitrator"].system_prompt},
             {"role": "user", "content": f"""{context}

## 看多方论点
{json.dumps(result.bull_argument, ensure_ascii=False, indent=2)}

## 看空方论点
{json.dumps(result.bear_argument, ensure_ascii=False, indent=2)}

## 数据审计结果
{json.dumps(result.audit_result, ensure_ascii=False, indent=2)}

请基于以上所有信息做出最终裁决。"""}],
        )
        result.rounds.append(arb_round)
        result.final_verdict = arb_round.parsed
        yield ("verdict", arb_round)

        logger.info("辩论完成!")
        yield ("complete", result)
