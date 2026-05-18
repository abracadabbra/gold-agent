"""Agent 定义 — 4 个角色的数据结构"""

from dataclasses import dataclass, field
from typing import Optional

from gold_agent.config import settings
from gold_agent.debate.prompts import (
    BULL_AGENT_SYSTEM,
    BEAR_AGENT_SYSTEM,
    AUDITOR_SYSTEM,
    ARBITRATOR_SYSTEM,
)


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str               # 英文标识
    role: str               # 中文角色名
    system_prompt: str      # System Prompt
    model: str              # 使用的模型
    temperature: float = 0.7
    emoji: str = ""


def get_agents() -> dict[str, AgentConfig]:
    """获取 4 个 Agent 配置"""

    return {
        "advocate": AgentConfig(
            name="advocate",
            role="🟢 看多方",
            system_prompt=BULL_AGENT_SYSTEM,
            model=settings.llm_model_bull,
            temperature=0.7,
            emoji="🟢",
        ),
        "challenger": AgentConfig(
            name="challenger",
            role="🔴 看空方",
            system_prompt=BEAR_AGENT_SYSTEM,
            model=settings.llm_model_bear,
            temperature=0.7,
            emoji="🔴",
        ),
        "auditor": AgentConfig(
            name="auditor",
            role="🔍 数据审计员",
            system_prompt=AUDITOR_SYSTEM,
            model=settings.llm_model_auditor,
            temperature=0.2,  # 审计员要严谨
            emoji="🔍",
        ),
        "arbitrator": AgentConfig(
            name="arbitrator",
            role="⚖️ 仲裁官",
            system_prompt=ARBITRATOR_SYSTEM,
            model=settings.llm_model_arbitrator,
            temperature=0.4,
            emoji="⚖️",
        ),
    }
