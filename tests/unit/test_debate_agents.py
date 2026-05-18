"""Agent 配置与提示词单元测试 — prompts.py + agents.py"""

from gold_agent.debate.agents import AgentConfig, get_agents
from gold_agent.debate.prompts import (
    ARBITRATOR_SYSTEM,
    AUDITOR_SYSTEM,
    BEAR_AGENT_SYSTEM,
    BULL_AGENT_SYSTEM,
)

# ============================================================
# Prompts
# ============================================================


class TestPrompts:
    """测试 System Prompt 常量"""

    def test_bull_agent_system_exists(self):
        """BULL_AGENT_SYSTEM 存在且有内容"""
        assert BULL_AGENT_SYSTEM is not None
        assert len(BULL_AGENT_SYSTEM) > 0

    def test_bear_agent_system_exists(self):
        """BEAR_AGENT_SYSTEM 存在且有内容"""
        assert BEAR_AGENT_SYSTEM is not None
        assert len(BEAR_AGENT_SYSTEM) > 0

    def test_auditor_system_exists(self):
        """AUDITOR_SYSTEM 存在且有内容"""
        assert AUDITOR_SYSTEM is not None
        assert len(AUDITOR_SYSTEM) > 0

    def test_arbitrator_system_exists(self):
        """ARBITRATOR_SYSTEM 存在且有内容"""
        assert ARBITRATOR_SYSTEM is not None
        assert len(ARBITRATOR_SYSTEM) > 0

    def test_bull_agent_content(self):
        """看多方提示词包含预期关键词"""
        assert "bullish" in BULL_AGENT_SYSTEM
        assert "看多" in BULL_AGENT_SYSTEM

    def test_bear_agent_content(self):
        """看空方提示词包含预期关键词"""
        assert "bearish" in BEAR_AGENT_SYSTEM
        assert "看空" in BEAR_AGENT_SYSTEM

    def test_auditor_content(self):
        """数据审计员提示词包含预期关键词"""
        assert "数据审计" in AUDITOR_SYSTEM

    def test_arbitrator_content(self):
        """仲裁官提示词包含预期关键词"""
        assert "仲裁官" in ARBITRATOR_SYSTEM

    def test_bull_has_json_format(self):
        """看多方输出格式包含 stance 或 verdict 字段"""
        assert '"stance"' in BULL_AGENT_SYSTEM or '"verdict"' in BULL_AGENT_SYSTEM

    def test_bear_has_json_format(self):
        """看空方输出格式包含 stance 或 verdict 字段"""
        assert '"stance"' in BEAR_AGENT_SYSTEM or '"verdict"' in BEAR_AGENT_SYSTEM

    def test_auditor_has_json_format(self):
        """审计员输出格式包含 verdict 或 claim 字段"""
        assert '"verdict"' in AUDITOR_SYSTEM or '"claim"' in AUDITOR_SYSTEM

    def test_arbitrator_has_json_format(self):
        """仲裁官输出格式包含 verdict 字段"""
        assert '"verdict"' in ARBITRATOR_SYSTEM

    def test_all_prompts_have_output_format(self):
        """所有 prompt 都包含 JSON 输出格式说明"""
        for prompt in [BULL_AGENT_SYSTEM, BEAR_AGENT_SYSTEM,
                       AUDITOR_SYSTEM, ARBITRATOR_SYSTEM]:
            assert "输出格式" in prompt or "```json" in prompt


# ============================================================
# AgentConfig
# ============================================================


class TestAgentConfig:
    """测试 AgentConfig dataclass"""

    def test_create_agent_config(self):
        """创建 AgentConfig 并验证所有字段"""
        config = AgentConfig(
            name="test_agent",
            role="测试角色",
            system_prompt="测试 prompt",
            model="gpt-4.1",
            temperature=0.5,
            emoji="🔵",
        )
        assert config.name == "test_agent"
        assert config.role == "测试角色"
        assert config.system_prompt == "测试 prompt"
        assert config.model == "gpt-4.1"
        assert config.temperature == 0.5
        assert config.emoji == "🔵"

    def test_default_temperature(self):
        """默认 temperature 应为 0.7"""
        config = AgentConfig(
            name="test",
            role="test",
            system_prompt="test",
            model="gpt-4.1",
        )
        assert config.temperature == 0.7

    def test_default_emoji(self):
        """默认 emoji 应为空字符串"""
        config = AgentConfig(
            name="test",
            role="test",
            system_prompt="test",
            model="gpt-4.1",
        )
        assert config.emoji == ""


# ============================================================
# get_agents()
# ============================================================


class TestGetAgents:
    """测试 get_agents()"""

    def test_returns_dict_with_4_agents(self):
        """get_agents 返回包含 4 个 Agent 的字典"""
        agents = get_agents()
        assert isinstance(agents, dict)
        assert len(agents) == 4
        assert "advocate" in agents
        assert "challenger" in agents
        assert "auditor" in agents
        assert "arbitrator" in agents

    def test_advocate_config(self):
        """看多方配置正确"""
        agents = get_agents()
        adv = agents["advocate"]
        assert adv.name == "advocate"
        assert "看多" in adv.role
        assert adv.emoji == "🟢"
        assert len(adv.system_prompt) > 0

    def test_challenger_config(self):
        """看空方配置正确"""
        agents = get_agents()
        chl = agents["challenger"]
        assert chl.name == "challenger"
        assert "看空" in chl.role
        assert chl.emoji == "🔴"
        assert len(chl.system_prompt) > 0

    def test_auditor_config(self):
        """数据审计员配置正确"""
        agents = get_agents()
        aud = agents["auditor"]
        assert aud.name == "auditor"
        assert "审计" in aud.role
        assert aud.emoji == "🔍"
        assert len(aud.system_prompt) > 0

    def test_arbitrator_config(self):
        """仲裁官配置正确"""
        agents = get_agents()
        arb = agents["arbitrator"]
        assert arb.name == "arbitrator"
        assert "仲裁" in arb.role
        assert arb.emoji == "⚖️"
        assert len(arb.system_prompt) > 0

    def test_temperatures(self):
        """每个 Agent 的 temperature 值正确"""
        agents = get_agents()
        assert agents["advocate"].temperature == 0.7
        assert agents["challenger"].temperature == 0.7
        assert agents["auditor"].temperature == 0.2
        assert agents["arbitrator"].temperature == 0.4

    def test_models_from_settings(self):
        """Agent 模型从 settings 读取"""
        from gold_agent.config import settings

        agents = get_agents()
        assert agents["advocate"].model == settings.llm_model_bull
        assert agents["challenger"].model == settings.llm_model_bear
        assert agents["auditor"].model == settings.llm_model_auditor
        assert agents["arbitrator"].model == settings.llm_model_arbitrator
