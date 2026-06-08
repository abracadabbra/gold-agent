"""集成测试 — App 启动和 API 基本功能"""

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

from gold_agent.debate.engine import DebateResult, DebateRound
from gold_agent.main import app

client = TestClient(app)


def _meta(
    row_count: int,
    *,
    source_status: str = "cache",
    expected_frequency: str = "daily",
) -> dict:
    return {
        "as_of": "2024-01-05T00:00:00",
        "latest_date": "2024-01-05T00:00:00",
        "fetched_at": "2024-01-05T08:00:00+00:00",
        "cached_at": "2024-01-05T07:55:00+00:00",
        "row_count": row_count,
        "stale": False,
        "source_status": source_status,
        "missing_rate": 0.0,
        "quality_score": 95,
        "expected_frequency": expected_frequency,
    }


def test_root():
    """GET / 返回 API 概览"""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "GoldAgent"
    assert "analysis" in data["endpoints"]
    assert "debate" in data["endpoints"]
    assert "backtest" in data["endpoints"]


def test_health():
    """GET /health 返回系统状态"""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "websocket" in data
    assert "config" in data


def test_stats():
    """GET /stats 返回统计信息"""
    resp = client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "websocket" in data
    assert "system" in data
    assert "cache" in data
    assert "fetch_runs" in data
    assert "uptime" in data["system"]
    assert "recent" in data["fetch_runs"]
    assert "summary" in data["fetch_runs"]


def test_docs_available():
    """OpenAPI 文档可访问"""
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower()


@patch("gold_agent.api.analysis.cache.get_with_meta")
def test_analysis_gold(mock_cache_get_with_meta):
    """GET /api/analysis/gold 返回金价数据"""
    mock_cache_get_with_meta.return_value = (
        pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "open": [2000.0] * 5, "high": [2010.0] * 5, "low": [1990.0] * 5,
            "close": [2005.0] * 5, "volume": [10000] * 5,
        }),
        _meta(5),
    )
    resp = client.get("/api/analysis/gold?source=intl&period=1y")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "intl"
    assert data["latest_price"] == 2005.0
    assert data["meta"]["row_count"] == 5


@patch("gold_agent.api.analysis.cache.get_with_meta")
def test_analysis_signal(mock_cache_get_with_meta):
    """GET /api/analysis/signal 返回交易信号"""
    price_df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=100, freq="D"),
        "open": [2000.0] * 100, "high": [2010.0] * 100, "low": [1990.0] * 100,
        "close": [2005.0] * 100, "volume": [10000] * 100,
    })
    macro_df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "tips_yield": [1.5] * 10,
    })
    mock_cache_get_with_meta.side_effect = [
        (price_df, _meta(100)),
        (macro_df, _meta(10, source_status="live")),
    ]
    resp = client.get("/api/analysis/signal")
    assert resp.status_code == 200
    data = resp.json()
    assert "signal" in data
    assert data["meta"]["row_count"] == 100
    assert data["macro_factors_meta"]["source_status"] == "live"
    assert data["macro_factors_meta"]["row_count"] == 10
    assert data["evaluation"]["sample_size"] > 0
    assert data["evaluation_meta"]["sample_size"] == data["evaluation"]["sample_size"]
    assert "sample_satisfied" in data["evaluation_meta"]
    assert "hit_rate" in data["evaluation"]


@patch("gold_agent.api.backtest.fetch_gold_price")
@patch("gold_agent.api.backtest._get_backtester")
def test_backtest_strategies(mock_get_bt, mock_fetch):
    """GET /api/backtest/strategies 返回策略列表"""
    from gold_agent.quant.backtest.engine import STRATEGIES, GoldBacktester, get_backtest_summary
    mock_get_bt.return_value = (GoldBacktester, STRATEGIES, get_backtest_summary)
    mock_fetch.return_value = pd.DataFrame({
        "date": pd.date_range("2022-01-01", periods=500, freq="D"),
        "open": [2000.0] * 500, "high": [2010.0] * 500, "low": [1990.0] * 500,
        "close": [2005.0] * 500, "volume": [10000] * 500,
    })
    resp = client.get("/api/backtest/strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert "strategies" in data


@patch("gold_agent.api.analysis.cache.get_with_meta")
def test_analysis_macro(mock_cache_get_with_meta):
    """GET /api/analysis/macro 返回宏观数据"""
    realtime = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3, freq="D"),
        "usd_index": [104.0, 103.5, 103.8],
    })
    official = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3, freq="ME"),
        "cpi": [3.1, 3.0, 2.9],
    })

    def cache_side_effect(key, **kwargs):
        if key.startswith("macro_yfinance"):
            return realtime, _meta(3)
        if key.startswith("macro_fred_"):
            return official, _meta(3, source_status="live", expected_frequency="mixed")
        return pd.DataFrame(), _meta(0, source_status="unavailable")

    mock_cache_get_with_meta.side_effect = cache_side_effect

    resp = client.get("/api/analysis/macro")
    assert resp.status_code == 200
    data = resp.json()
    assert "realtime" in data
    assert "official" in data
    assert data["realtime"]["records"] == 3
    assert data["official"]["records"] == 3
    assert data["official"]["meta"]["source_status"] == "live"
    assert data["meta"]["available_count"] == 2
    assert data["meta"]["unavailable_count"] == 0
    assert data["meta"]["coverage_satisfied"] is True
    assert data["meta"]["min_required_available"] == 2
    assert data["meta"]["source_status"] == "cache"
    assert data["meta"]["quality_score"] == 95


@patch("gold_agent.api.analysis.cache.get_with_meta")
def test_analysis_macro_partial_coverage(mock_cache_get_with_meta):
    """GET /api/analysis/macro exposes aggregate quality when a macro source is missing."""
    realtime = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3, freq="D"),
        "usd_index": [104.0, 103.5, 103.8],
    })

    def cache_side_effect(key, **kwargs):
        if key.startswith("macro_yfinance"):
            return realtime, _meta(3, source_status="live")
        if key.startswith("macro_fred_"):
            return pd.DataFrame(), _meta(0, source_status="unavailable", expected_frequency="mixed")
        return pd.DataFrame(), _meta(0, source_status="unavailable")

    mock_cache_get_with_meta.side_effect = cache_side_effect

    resp = client.get("/api/analysis/macro")
    assert resp.status_code == 200
    data = resp.json()
    assert data["realtime"]["records"] == 3
    assert data["official"]["records"] == 0
    assert data["meta"]["available_count"] == 1
    assert data["meta"]["unavailable_count"] == 1
    assert data["meta"]["coverage_satisfied"] is False
    assert data["meta"]["source_status"] == "live"
    assert data["meta"]["quality_score"] == 17


@patch("gold_agent.api.analysis.cache.get_with_meta")
def test_analysis_news(mock_cache_get_with_meta):
    """GET /api/analysis/news 返回新闻情绪"""
    mock_cache_get_with_meta.return_value = (
        pd.DataFrame({
            "title": ["Gold rally surge", "Rate hike"],
            "link": ["http://a.com", "http://b.com"],
            "published": ["", ""],
            "source": ["test", "test"],
            "sentiment_score": [0.6, -0.1],
            "sentiment_label": ["bullish", "neutral"],
        }),
        _meta(2, expected_frequency="intraday"),
    )
    resp = client.get("/api/analysis/news")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    # avg = (0.6 + -0.1) / 2 = 0.25 > 0.2 -> bullish
    assert data["label"] == "bullish"
    assert data["meta"]["expected_frequency"] == "intraday"
    assert data["meta"]["sample_size"] == 2
    assert data["meta"]["valid_sentiment_count"] == 2
    assert data["meta"]["min_required_articles"] == 5
    assert data["meta"]["sample_satisfied"] is False
    assert data["meta"]["conclusion_suitable"] is False
    assert data["meta"]["quality_score"] == 65


@patch("gold_agent.api.analysis.cache.get_with_meta")
def test_analysis_news_sufficient_sample(mock_cache_get_with_meta):
    """GET /api/analysis/news marks sentiment conclusions suitable when sample is enough."""
    mock_cache_get_with_meta.return_value = (
        pd.DataFrame({
            "title": [f"Gold story {i}" for i in range(5)],
            "link": [f"http://example.com/{i}" for i in range(5)],
            "published": [""] * 5,
            "source": ["test"] * 5,
            "sentiment_score": [0.3, 0.2, 0.4, 0.1, 0.5],
            "sentiment_label": ["bullish"] * 5,
        }),
        _meta(5, expected_frequency="intraday"),
    )
    resp = client.get("/api/analysis/news")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["meta"]["sample_satisfied"] is True
    assert data["meta"]["conclusion_suitable"] is True
    assert data["meta"]["quality_score"] == 95


@patch("gold_agent.api.extra_data.cache.get")
def test_extra_calendar(mock_cache):
    """GET /api/analysis/calendar 返回财经日历"""
    resp = client.get("/api/analysis/calendar?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "next_event" in data


# ── 辅助: 通用的金价 DataFrame ──

def _price_df(periods: int = 100) -> pd.DataFrame:
    """创建模拟金价 DataFrame"""
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=periods, freq="D"),
        "open": [2000.0] * periods,
        "high": [2010.0] * periods,
        "low": [1990.0] * periods,
        "close": [2005.0] * periods,
        "volume": [10000] * periods,
    })


# ═══════════════════════════════════════════════════════════
# 技术指标
# ═══════════════════════════════════════════════════════════

@patch("gold_agent.api.analysis.cache.get_with_meta")
def test_analysis_indicators(mock_cache_get_with_meta):
    """GET /api/analysis/indicators 返回技术指标"""
    mock_cache_get_with_meta.return_value = (_price_df(200), _meta(200))
    resp = client.get("/api/analysis/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert "price" in data
    assert data["price"] == 2005.0
    assert "indicators" in data
    assert "summary" in data
    assert data["meta"]["row_count"] == 200
    assert data["indicator_meta"]["row_count"] == 1
    assert data["indicator_meta"]["warmup_satisfied"] is True
    assert data["indicator_meta"]["available_indicators"] > 0


# ═══════════════════════════════════════════════════════════
# 预测
# ═══════════════════════════════════════════════════════════

@patch("gold_agent.api.analysis.cache.get_with_meta")
def test_analysis_predict(mock_cache_get_with_meta):
    """GET /api/analysis/predict 返回预测结果"""
    def _side_effect(key, **kwargs):
        if key.startswith("macro_yfinance"):
            return pd.DataFrame({
                "date": pd.date_range("2024-01-01", periods=200, freq="D"),
                "usd_index": [104.0] * 200,
                "vix": [15.0] * 200,
                "us_10y": [4.2] * 200,
            }), _meta(200, source_status="live")
        return _price_df(400), _meta(400)

    mock_cache_get_with_meta.side_effect = _side_effect

    resp = client.get("/api/analysis/predict?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert "prediction" in data
    assert "history" in data
    assert "trend" in data
    assert "summary" in data
    assert "disclaimer" in data
    assert data["meta"]["row_count"] == 400
    assert data["regressor_meta"]["source_status"] == "live"
    assert data["regressor_meta"]["row_count"] == 200
    assert data["regressor_alignment"]["usd_index"]["aligned_as_of"] == "2024-07-18T00:00:00"
    assert data["regressor_alignment"]["usd_index"]["lag_days"] == 200
    assert data["evaluation"]["baseline"] == "naive_last_value"
    assert data["evaluation"]["sample_size"] > 0
    assert data["evaluation"]["mae"] is not None
    assert [item["baseline"] for item in data["evaluation"]["baselines"]] == [
        "naive_last_value",
        "moving_average",
        "linear_trend",
    ]


# ═══════════════════════════════════════════════════════════
# 关键因子
# ═══════════════════════════════════════════════════════════

@patch("gold_agent.api.factors.cache.get_with_meta")
def test_analysis_factors(mock_cache_get_with_meta):
    """GET /api/analysis/factors 返回关键因子数据"""
    mock_cache_get_with_meta.return_value = (_price_df(10), _meta(10))
    resp = client.get("/api/analysis/factors")
    assert resp.status_code == 200
    data = resp.json()
    expected_keys = {"cot", "fedwatch", "central_bank", "tips", "dxy"}
    assert expected_keys.issubset(data.keys())
    assert "meta" in data
    assert data["meta"]["row_count"] == 5
    assert data["meta"]["min_required_available"] == 3


# ═══════════════════════════════════════════════════════════
# 补充数据
# ═══════════════════════════════════════════════════════════

@patch("gold_agent.api.extra_data.cache.get_with_meta")
def test_analysis_extra(mock_cache_get_with_meta):
    """GET /api/analysis/extra 返回全部补充数据"""
    mock_cache_get_with_meta.return_value = (_price_df(10), _meta(10))
    resp = client.get("/api/analysis/extra")
    assert resp.status_code == 200
    data = resp.json()
    expected_keys = {"central_bank", "cot", "etf_flow", "geopol",
                      "fedwatch", "aisc", "china_macro"}
    for key in expected_keys:
        assert key in data, f"缺少 key: {key}"
        if key != "china_macro":
            assert data[key]["meta"]["row_count"] == 10
    assert "cpi" in data["china_macro"]
    assert data["china_macro"]["cpi"]["meta"]["row_count"] == 10


# ═══════════════════════════════════════════════════════════
# 辩论 - 快速分析
# ═══════════════════════════════════════════════════════════

@patch("gold_agent.api.debate.cache.get_with_meta")
def test_debate_quick(mock_cache):
    """GET /api/debate/quick 返回快速分析结果"""
    mock_cache.return_value = (
        _price_df(200),
        {
            "as_of": "2024-05-01T00:00:00",
            "latest_date": "2024-05-01T00:00:00",
            "fetched_at": "2024-05-01T08:00:00+00:00",
            "cached_at": "2024-05-01T07:55:00+00:00",
            "row_count": 200,
            "stale": False,
            "source_status": "cache",
            "missing_rate": 0.0,
            "quality_score": 95,
            "expected_frequency": "daily",
        },
    )
    resp = client.get("/api/debate/quick")
    assert resp.status_code == 200
    data = resp.json()
    assert "signal" in data
    assert "indicators" in data
    assert data["meta"]["source_status"] == "cache"


# ═══════════════════════════════════════════════════════════
# 辩论 - 完整流程
# ═══════════════════════════════════════════════════════════

def _sample_debate_result() -> DebateResult:
    """创建模拟辩论结果"""
    round_ = MagicMock(spec=DebateRound)
    round_.role = "bull"
    round_.agent_name = "bull"
    round_.parsed = {"key_points": ["强势基本面"]}

    return DebateResult(
        rounds=[round_],
        bull_argument={
            "arguments": [{"point": "强势基本面", "strength": "高", "evidence": "数据支持"}],
            "confidence": 80,
        },
        bear_argument={
            "arguments": [{"point": "政策风险", "strength": "中", "evidence": "不确定性"}],
            "confidence": 60,
        },
        audit_result={"missed_data": [], "overall_assessment": "数据充分"},
        final_verdict={
            "verdict": "bullish", "confidence": 75,
            "price_range": {"low": 2000, "high": 2100},
            "time_horizon": "1周", "key_reasons": ["趋势向好"],
            "risk_warnings": ["注意回调"], "final_advice": "逢低买入",
        },
    )


@patch("gold_agent.api.debate.DebateEngine")
@patch("gold_agent.api.debate.build_factor_snapshot", new_callable=AsyncMock)
@patch("gold_agent.api.debate.cache.get_with_meta")
def test_debate_run(mock_cache_get_with_meta, mock_build_factor_snapshot, mock_engine_cls):
    """POST /api/debate/run 返回完整辩论结果"""
    mock_cache_get_with_meta.side_effect = [
        (_price_df(200), _meta(200)),
        (
            pd.DataFrame({
                "date": pd.date_range("2024-05-01", periods=5, freq="D"),
                "usd_index": [104.0] * 5,
            }),
            _meta(5),
        ),
        (
            pd.DataFrame({
                "date": pd.date_range("2024-01-01", periods=5, freq="ME"),
                "cpi": [3.0] * 5,
            }),
            _meta(5, source_status="live", expected_frequency="mixed"),
        ),
        (
            pd.DataFrame({
                "title": ["Gold rally surge"],
                "link": ["http://a.com"],
                "published": [""],
                "source": ["test"],
                "sentiment_score": [0.6],
                "sentiment_label": ["bullish"],
            }),
            _meta(1, expected_frequency="intraday"),
        ),
    ]
    mock_build_factor_snapshot.return_value = {
        "cot": {
            "label": "看多",
            "aligned_as_of": "2024-05-01T00:00:00",
            "lag_days": 1,
        },
        "fedwatch": {
            "label": "偏鸽",
            "aligned_as_of": "2024-05-01T00:00:00",
            "lag_days": 0,
        },
        "central_bank": {
            "label": "利多",
            "aligned_as_of": "2024-04-30T00:00:00",
            "lag_days": 2,
        },
        "tips": {
            "label": "中性",
            "aligned_as_of": "2024-05-01T00:00:00",
            "lag_days": 0,
        },
        "dxy": {
            "label": "中性",
            "aligned_as_of": "2024-05-01T00:00:00",
            "lag_days": 0,
        },
        "meta": {
            **_meta(5),
            "row_count": 5,
            "expected_frequency": "mixed",
            "available_count": 5,
            "unavailable_count": 0,
            "min_required_available": 3,
            "coverage_satisfied": True,
            "max_lag_days": 2,
        },
    }

    mock_engine = AsyncMock()
    mock_engine.run_debate.return_value = _sample_debate_result()
    mock_engine_cls.return_value = mock_engine

    resp = client.post("/api/debate/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "detail" in data
    assert "bull" in data["detail"]
    assert "bear" in data["detail"]
    assert "verdict" in data["detail"]
    assert data["meta"]["gold"]["row_count"] == 200
    assert data["meta"]["macro"]["available_count"] == 2
    assert data["meta"]["macro"]["coverage_satisfied"] is True
    assert data["meta"]["factors"]["available_count"] == 5
    assert data["meta"]["factors"]["max_lag_days"] == 2
    assert data["meta"]["news"]["expected_frequency"] == "intraday"
    context = mock_engine.run_debate.call_args.args[0]
    assert "available_count=2/2" in context
    assert "coverage_satisfied=True" in context
    assert "关键因子快照" in context
    assert "max_lag_days=2" in context


# ═══════════════════════════════════════════════════════════
# 回测
# ═══════════════════════════════════════════════════════════

@patch("gold_agent.api.backtest.cache.get_with_meta")
def test_backtest_run(mock_cache_get_with_meta):
    """GET /api/backtest/run 返回回测结果"""
    mock_cache_get_with_meta.return_value = (_price_df(500), _meta(500))

    class FakeResult:
        def __init__(self):
            self.initial_cash = 100000
            self.final_value = 110000
            self.total_return = 0.10
            self.max_drawdown = 0.05
            self.sharpe_ratio = 1.5
            self.total_trades = 10
            self.win_rate = 0.6
            self.strategy_name = "golden_cross"

    class FakeBacktester:
        def __init__(self, strategy_name="golden_cross", initial_cash=100000):
            self.strategy_name = strategy_name
            self.initial_cash = initial_cash
        def run(self, df):
            return FakeResult()

    def _fake_get_backtester():
        return FakeBacktester, {"golden_cross": "金叉策略"}, lambda r: r.__dict__

    with patch("gold_agent.api.backtest._get_backtester", _fake_get_backtester):
        resp = client.get("/api/backtest/run?strategy=golden_cross&period=2y")
        assert resp.status_code == 200
        data = resp.json()
        assert "initial_cash" in data
        assert data["initial_cash"] == 100000
        assert "final_value" in data
        assert "total_return" in data
        assert data["meta"]["row_count"] == 500
        assert data["backtest_meta"]["sample_size"] == 500
        assert data["backtest_meta"]["trades"] == 10
        assert data["backtest_meta"]["sample_satisfied"] is True
