"""辩论引擎单元测试 — engine.py"""

from unittest.mock import AsyncMock, patch

import pytest

from gold_agent.debate.engine import DebateEngine, DebateResult, DebateRound

# ============================================================
# DebateRound
# ============================================================


class TestDebateRound:
    """测试 DebateRound dataclass"""

    def test_create_round(self):
        """创建 DebateRound 并验证所有字段"""
        round_data = DebateRound(
            agent_name="advocate",
            role="看多方",
            model="gpt-4.1",
            content='{"stance": "bullish"}',
            parsed={"stance": "bullish"},
            tokens_used=50,
        )
        assert round_data.agent_name == "advocate"
        assert round_data.role == "看多方"
        assert round_data.model == "gpt-4.1"
        assert round_data.content == '{"stance": "bullish"}'
        assert round_data.parsed == {"stance": "bullish"}
        assert round_data.tokens_used == 50

    def test_default_tokens_used(self):
        """tokens_used 默认值为 0"""
        round_data = DebateRound(
            agent_name="test",
            role="test",
            model="gpt-4.1",
            content="{}",
            parsed={},
        )
        assert round_data.tokens_used == 0


# ============================================================
# DebateResult
# ============================================================


class TestDebateResult:
    """测试 DebateResult dataclass"""

    def test_to_dict_all_fields(self):
        """to_dict 返回正确的键"""
        result = DebateResult(
            rounds=[],
            bull_argument={"stance": "bullish"},
            bear_argument={"stance": "bearish"},
            audit_result={"overall_assessment": "ok"},
            final_verdict={"verdict": "bullish"},
        )
        d = result.to_dict()
        assert d["bull"] == {"stance": "bullish"}
        assert d["bear"] == {"stance": "bearish"}
        assert d["audit"] == {"overall_assessment": "ok"}
        assert d["verdict"] == {"verdict": "bullish"}

    def test_to_dict_defaults(self):
        """to_dict 在字段为 None 时返回 None"""
        result = DebateResult(rounds=[])
        d = result.to_dict()
        assert d["bull"] is None
        assert d["bear"] is None
        assert d["audit"] is None
        assert d["verdict"] is None

    def test_to_summary_full(self):
        """to_summary 包含所有 Agent 的辩论内容"""
        result = DebateResult(
            rounds=[],
            bull_argument={
                "stance": "bullish",
                "confidence": 70,
                "arguments": [
                    {
                        "point": "避险需求",
                        "evidence": "中东局势紧张",
                        "strength": "strong",
                    }
                ],
            },
            bear_argument={
                "stance": "bearish",
                "confidence": 60,
                "arguments": [
                    {
                        "point": "美元走强",
                        "evidence": "DXY 105",
                        "strength": "medium",
                    }
                ],
            },
            audit_result={
                "missed_data": ["CPI 数据"],
                "overall_assessment": "数据质量良好",
            },
            final_verdict={
                "verdict": "bullish",
                "confidence": 65,
                "price_range": {"low": 3200, "high": 3300, "currency": "USD/oz"},
                "time_horizon": "1w",
                "key_reasons": ["避险情绪升温"],
                "risk_warnings": ["美联储鹰派表态"],
                "final_advice": "适度做多",
            },
        )
        summary = result.to_summary()
        assert "看多方" in summary
        assert "看空方" in summary
        assert "数据审计" in summary
        assert "仲裁官" in summary
        assert "bullish" in summary
        assert "3200" in summary
        assert "3300" in summary

    def test_to_summary_no_verdict(self):
        """to_summary 在没有最终裁决时不应报错"""
        result = DebateResult(
            rounds=[],
            bull_argument={"stance": "bullish", "confidence": 70, "arguments": []},
            bear_argument={"stance": "bearish", "confidence": 60, "arguments": []},
        )
        summary = result.to_summary()
        assert "看多方" in summary
        assert "看空方" in summary

    def test_to_summary_empty(self):
        """完全空的 DebateResult 应生成有效字符串"""
        result = DebateResult(rounds=[])
        summary = result.to_summary()
        assert len(summary) > 0


# ============================================================
# DebateEngine
# ============================================================


class TestDebateEngine:
    """测试 DebateEngine"""

    def test_init_creates_agents(self):
        """初始化时通过 get_agents 创建 4 个 Agent"""
        engine = DebateEngine()
        assert hasattr(engine, "agents")
        assert len(engine.agents) == 4
        assert "advocate" in engine.agents
        assert "challenger" in engine.agents
        assert "auditor" in engine.agents
        assert "arbitrator" in engine.agents

    def test_build_context(self):
        """_build_context 包装数据上下文"""
        engine = DebateEngine()
        context = engine._build_context("test data")
        assert "test data" in context
        assert "市场数据" in context
        assert "quality_score" in context
        assert "stale=yes" in context

    @pytest.mark.asyncio
    async def test_run_debate_full_flow(self):
        """完整辩论流程 — 4 个 Agent 按顺序执行"""
        fake_bull = (
            '{"stance":"bullish","confidence":70,"arguments":['
            '{"point":"test","evidence":"data","strength":"strong"}]}'
        )
        fake_bear = '{"stance":"bearish","confidence":60,"arguments":[]}'
        fake_audit = (
            '{"bull_claims":[],"bear_claims":[],'
            '"overall_assessment":"ok"}'
        )
        fake_arb = (
            '{"verdict":"bullish","confidence":65,'
            '"price_range":{"low":3200,"high":3300,"currency":"USD/oz"},'
            '"key_reasons":["test"],"risk_warnings":["risk"],'
            '"final_advice":"buy"}'
        )

        with patch(
            "gold_agent.debate.engine.chat_completion", new=AsyncMock()
        ) as mock_llm:
            mock_llm.side_effect = [fake_bull, fake_bear, fake_audit, fake_arb]

            engine = DebateEngine()
            result = await engine.run_debate(data_context="some data")

            assert result.bull_argument["stance"] == "bullish"
            assert result.bear_argument["stance"] == "bearish"
            assert result.audit_result["overall_assessment"] == "ok"
            assert result.final_verdict["verdict"] == "bullish"
            assert len(result.rounds) == 4

    @pytest.mark.asyncio
    async def test_run_debate_rounds_order(self):
        """验证 4 轮辩论的执行顺序: advocate → challenger → auditor → arbitrator"""
        fake_bull = '{"stance":"bullish"}'
        fake_bear = '{"stance":"bearish"}'
        fake_audit = '{"overall_assessment":"ok"}'
        fake_arb = '{"verdict":"bullish"}'

        with patch(
            "gold_agent.debate.engine.chat_completion", new=AsyncMock()
        ) as mock_llm:
            mock_llm.side_effect = [fake_bull, fake_bear, fake_audit, fake_arb]

            engine = DebateEngine()
            result = await engine.run_debate(data_context="some data")

            assert result.rounds[0].agent_name == "advocate"
            assert result.rounds[1].agent_name == "challenger"
            assert result.rounds[2].agent_name == "auditor"
            assert result.rounds[3].agent_name == "arbitrator"

    @pytest.mark.asyncio
    async def test_run_agent_json_fallback(self):
        """LLM 返回非 JSON 时 parsed 包含 raw_text"""
        engine = DebateEngine()

        with patch(
            "gold_agent.debate.engine.chat_completion", new=AsyncMock()
        ) as mock_llm:
            mock_llm.return_value = "This is not JSON"

            agent = engine.agents["advocate"]
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": "hello"},
            ]
            round_data = await engine._run_agent(agent, messages)
            assert "raw_text" in round_data.parsed
            assert round_data.parsed["raw_text"] == "This is not JSON"

    @pytest.mark.asyncio
    async def test_run_agent_markdown_json(self):
        """LLM 返回 markdown 代码块包裹的 JSON 时应能正确解析"""
        engine = DebateEngine()
        markdown_json = '```json\n{"stance": "bullish", "confidence": 80}\n```'

        with patch(
            "gold_agent.debate.engine.chat_completion", new=AsyncMock()
        ) as mock_llm:
            mock_llm.return_value = markdown_json

            agent = engine.agents["advocate"]
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": "analyze"},
            ]
            round_data = await engine._run_agent(agent, messages)
            assert round_data.parsed["stance"] == "bullish"
            assert round_data.parsed["confidence"] == 80

    @pytest.mark.asyncio
    async def test_run_agent_markdown_json_no_lang(self):
        """LLM 返回无语言标记的 ``` 代码块时也能正确解析"""
        engine = DebateEngine()
        markdown_json = '```\n{"stance": "bearish", "confidence": 55}\n```'

        with patch(
            "gold_agent.debate.engine.chat_completion", new=AsyncMock()
        ) as mock_llm:
            mock_llm.return_value = markdown_json

            agent = engine.agents["challenger"]
            messages = [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": "analyze"},
            ]
            round_data = await engine._run_agent(agent, messages)
            assert round_data.parsed["stance"] == "bearish"
            assert round_data.parsed["confidence"] == 55


class TestDebateEngineIncomplete:
    """测试辩论未完成情况"""

    @pytest.mark.asyncio
    async def test_run_debate_incomplete(self):
        """辩论未完成时引发 RuntimeError（覆盖 line 153）"""
        engine = DebateEngine()

        # Create a generator that yields "bull" then stops without "complete"
        async def incomplete_generator(_):
            yield ("bull", DebateRound(
                agent_name="advocate", role="看多方",
                model="gpt-4.1", content="{}", parsed={},
            ))

        with patch.object(engine, "_debate_rounds", incomplete_generator):
            with pytest.raises(RuntimeError, match="debate did not complete"):
                await engine.run_debate(data_context="test")

    @pytest.mark.asyncio
    async def test_stream_debate(self):
        """stream_debate 正确 yield 每一轮（覆盖 lines 158-159）"""
        engine = DebateEngine()
        fake_round = DebateRound(
            agent_name="advocate", role="看多方",
            model="gpt-4.1", content="{}", parsed={},
        )
        fake_result = DebateResult(rounds=[fake_round])

        async def mock_rounds(_):
            yield ("bull", fake_round)
            yield ("complete", fake_result)

        with patch.object(engine, "_debate_rounds", mock_rounds):
            stages = []
            items = []
            async for stage, item in engine.stream_debate(data_context="test"):
                stages.append(stage)
                items.append(item)

            assert stages == ["bull", "complete"]
            assert items[0] is fake_round
            assert items[1] is fake_result
