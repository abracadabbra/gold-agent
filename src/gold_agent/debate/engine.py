"""辩论流程编排 — 多 Agent 协作的核心引擎"""

import json
from dataclasses import dataclass

import logging
logger = logging.getLogger(__name__)

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
            for arg in self.bull_argument.get("arguments", []):
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

请基于以上数据进行分析，不要编造数据。"""

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
            max_tokens=2000,
        )

        # 尝试解析 JSON
        parsed = {}
        try:
            # 清理 markdown 代码块
            clean = content
            if "```" in clean:
                import re
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
        """
        运行完整辩论流程

        流程:
        1. 数据采集 + 量化分析 (外部完成)
        2. 看多方构建论点
        3. 看空方构建论点
        4. 数据审计员验证
        5. 仲裁官综合裁决

        Args:
            data_context: 格式化的市场数据上下文

        Returns:
            DebateResult
        """
        result = DebateResult(rounds=[])
        context = self._build_context(data_context)

        # ---- Step 1: 看多方 ----
        logger.info("=" * 40 + " Round 1: 看多方 " + "=" * 40)
        bull_messages = [
            {"role": "system", "content": self.agents["advocate"].system_prompt},
            {"role": "user", "content": context},
        ]
        bull_round = await self._run_agent(self.agents["advocate"], bull_messages)
        result.rounds.append(bull_round)
        result.bull_argument = bull_round.parsed

        # ---- Step 2: 看空方 ----
        logger.info("=" * 40 + " Round 2: 看空方 " + "=" * 40)
        bear_messages = [
            {"role": "system", "content": self.agents["challenger"].system_prompt},
            {"role": "user", "content": context},
        ]
        bear_round = await self._run_agent(self.agents["challenger"], bear_messages)
        result.rounds.append(bear_round)
        result.bear_argument = bear_round.parsed

        # ---- Step 3: 数据审计 ----
        logger.info("=" * 40 + " Round 3: 数据审计 " + "=" * 40)
        audit_context = f"""{context}

## 看多方论点
{json.dumps(result.bull_argument, ensure_ascii=False, indent=2)}

## 看空方论点
{json.dumps(result.bear_argument, ensure_ascii=False, indent=2)}

请验证以上双方引用的数据是否准确。"""
        audit_messages = [
            {"role": "system", "content": self.agents["auditor"].system_prompt},
            {"role": "user", "content": audit_context},
        ]
        audit_round = await self._run_agent(self.agents["auditor"], audit_messages)
        result.rounds.append(audit_round)
        result.audit_result = audit_round.parsed

        # ---- Step 4: 仲裁裁决 ----
        logger.info("=" * 40 + " Round 4: 仲裁裁决 " + "=" * 40)
        arb_context = f"""{context}

## 看多方论点
{json.dumps(result.bull_argument, ensure_ascii=False, indent=2)}

## 看空方论点
{json.dumps(result.bear_argument, ensure_ascii=False, indent=2)}

## 数据审计结果
{json.dumps(result.audit_result, ensure_ascii=False, indent=2)}

请基于以上所有信息做出最终裁决。"""
        arb_messages = [
            {"role": "system", "content": self.agents["arbitrator"].system_prompt},
            {"role": "user", "content": arb_context},
        ]
        arb_round = await self._run_agent(self.agents["arbitrator"], arb_messages)
        result.rounds.append(arb_round)
        result.final_verdict = arb_round.parsed

        logger.info("辩论完成!")
        return result
