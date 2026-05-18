"""FastAPI 主入口"""

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
from gold_agent.api.websocket import websocket_endpoint, manager as ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("GoldAgent 启动")
    logger.info(f"  LLM: {settings.openai_base_url}")
    logger.info(f"  缓存: {settings.parquet_dir}")

    settings.ensure_dirs()

    yield

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


@app.get("/stats")
async def stats():
    """系统统计端点"""
    ws_stats = ws_manager.get_stats()
    
    # 这里可以添加更多统计信息
    # 比如数据库记录数、缓存命中率等
    
    return {
        "websocket": ws_stats,
        "system": {
            "uptime": "计算运行时间",
            "memory_usage": "内存使用情况",
            "disk_usage": "磁盘使用情况",
        },
        "data": {
            "gold_prices_count": "金价记录数",
            "predictions_count": "预测记录数",
            "debates_count": "辩论记录数",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("gold_agent.main:app", host="0.0.0.0", port=8000, reload=True)
