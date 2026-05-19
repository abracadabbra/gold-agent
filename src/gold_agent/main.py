"""FastAPI 主入口"""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import logging
logger = logging.getLogger(__name__)

from gold_agent.config import settings
from gold_agent.api.analysis import router as analysis_router
from gold_agent.api.debate import router as debate_router
from gold_agent.api.backtest import router as backtest_router
from gold_agent.api.extra_data import router as extra_data_router
from gold_agent.api.websocket import (
    websocket_endpoint,
    manager as ws_manager,
    periodic_price_push,
    periodic_signal_push,
    periodic_news_push,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("GoldAgent 启动")
    logger.info(f"  LLM: {settings.openai_base_url}")
    logger.info(f"  缓存: {settings.parquet_dir}")

    settings.ensure_dirs()
    app.state.start_time = time.time()

    # 后台定时推送
    push_tasks = [
        asyncio.create_task(periodic_price_push(60), name="price-push"),
        asyncio.create_task(periodic_signal_push(60), name="signal-push"),
        asyncio.create_task(periodic_news_push(300), name="news-push"),
    ]
    logger.info(f"启动 {len(push_tasks)} 个定时推送任务")

    yield

    for t in push_tasks:
        t.cancel()
    await asyncio.gather(*push_tasks, return_exceptions=True)
    logger.info("GoldAgent 关闭")


app = FastAPI(
    title="GoldAgent",
    description="量化 + LLM 混合驱动的黄金价格分析系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(analysis_router)
app.include_router(debate_router)
app.include_router(backtest_router)
app.include_router(extra_data_router)


# WebSocket 端点
@app.websocket("/ws/{client_id}")
async def websocket_route(websocket: WebSocket, client_id: str):
    """WebSocket 连接端点"""
    await websocket_endpoint(websocket, client_id)


@app.get("/")
async def root():
    return {
        "name": "GoldAgent",
        "version": "0.1.0",
        "description": "量化 + LLM 混合驱动的黄金价格分析系统",
        "docs": "/docs",
        "websocket": "/ws/{client_id}",
        "endpoints": {
            "analysis": "/api/analysis",
            "debate": "/api/debate",
            "backtest": "/api/backtest",
        }
    }


@app.get("/health")
async def health():
    """健康检查端点"""
    ws_stats = ws_manager.get_stats()
    return {
        "status": "ok",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "running",
            "websocket": "running",
            "cache": "available",
        },
        "websocket": ws_stats,
        "config": {
            "llm_model_bull": settings.llm_model_bull,
            "llm_model_bear": settings.llm_model_bear,
            "parquet_dir": str(settings.parquet_dir),
        }
    }


def _count_parquet_files(subdir: str) -> int:
    """统计缓存目录中某个数据类型的 Parquet 文件数"""
    data_dir = settings.parquet_dir / subdir
    if data_dir.exists():
        return len(list(data_dir.glob("*.parquet")))
    return 0


def _format_duration(seconds: float) -> str:
    """将秒数格式化为可读的时间"""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m {secs}s"


@app.get("/stats")
async def stats():
    """系统统计端点"""
    ws_stats = ws_manager.get_stats()
    uptime = _format_duration(time.time() - getattr(app.state, "start_time", time.time()))

    cache_stats = {}
    extra_keys = [
        "central_bank_reserves", "cot", "etf_flow", "geopol",
        "fedwatch", "aisc", "china_cpi", "china_ppi", "china_pmi",
        "china_m2", "china_gdp", "china_lpr", "china_usd_cny",
    ]
    for key in ["gold_intl", "gold_shfe", "gold_gld", "macro_yfinance"] + extra_keys:
        cache_stats[key] = _count_parquet_files(key)

    return {
        "websocket": ws_stats,
        "system": {
            "uptime": uptime,
            "version": "0.1.0",
        },
        "cache": cache_stats,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("gold_agent.main:app", host="0.0.0.0", port=8000, reload=True)
