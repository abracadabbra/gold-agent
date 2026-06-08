"""WebSocket 接口 — 实时数据推送"""

import asyncio
import json
from datetime import datetime, UTC

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import logging
logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 活跃连接: {client_id: WebSocket}
        self.active_connections: dict[str, WebSocket] = {}
        # 订阅频道: {channel: set(client_id)}
        self.subscriptions: dict[str, set[str]] = {
            "price": set(),      # 金价更新
            "signal": set(),     # 信号更新
            "news": set(),       # 新闻更新
            "debate": set(),     # 辩论结果
            "system": set(),     # 系统状态
        }
        # 客户端订阅: {client_id: set(channel)}
        self.client_subscriptions: dict[str, set[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.client_subscriptions[client_id] = set()
        logger.info(f"WebSocket 连接: {client_id}, 当前连接数: {len(self.active_connections)}")

        # 发送欢迎消息
        await self.send_personal_message(client_id, {
            "type": "connection",
            "client_id": client_id,
            "message": "连接成功",
            "available_channels": list(self.subscriptions.keys()),
            "timestamp": datetime.now(UTC).isoformat()
        })

    def disconnect(self, client_id: str):
        """断开连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        # 清理订阅
        if client_id in self.client_subscriptions:
            for channel in self.client_subscriptions[client_id]:
                if channel in self.subscriptions:
                    self.subscriptions[channel].discard(client_id)
            del self.client_subscriptions[client_id]

        logger.info(f"WebSocket 断开: {client_id}, 当前连接数: {len(self.active_connections)}")

    async def send_personal_message(self, client_id: str, message: dict):
        """发送个人消息"""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
            except Exception as e:
                logger.error(f"发送消息失败 {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, channel: str, message: dict):
        """广播消息到频道的所有订阅者"""
        if channel not in self.subscriptions:
            logger.warning(f"未知频道: {channel}")
            return

        subscribers = self.subscriptions[channel]
        if not subscribers:
            return

        message["channel"] = channel
        message["timestamp"] = datetime.now(UTC).isoformat()

        disconnected = []
        for client_id in subscribers:
            if client_id in self.active_connections:
                websocket = self.active_connections[client_id]
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(message)
                    else:
                        disconnected.append(client_id)
                except Exception as e:
                    logger.error(f"广播失败 {client_id}: {e}")
                    disconnected.append(client_id)

        # 清理断开的连接
        for client_id in disconnected:
            self.disconnect(client_id)

    def subscribe(self, client_id: str, channel: str) -> bool:
        """订阅频道"""
        if channel not in self.subscriptions:
            return False

        self.subscriptions[channel].add(client_id)
        if client_id not in self.client_subscriptions:
            self.client_subscriptions[client_id] = set()
        self.client_subscriptions[client_id].add(channel)

        logger.info(f"订阅: {client_id} -> {channel}")
        return True

    def unsubscribe(self, client_id: str, channel: str) -> bool:
        """取消订阅"""
        if channel not in self.subscriptions:
            return False

        self.subscriptions[channel].discard(client_id)
        if client_id in self.client_subscriptions:
            self.client_subscriptions[client_id].discard(channel)

        logger.info(f"取消订阅: {client_id} -> {channel}")
        return True

    def get_stats(self) -> dict:
        """获取连接统计"""
        return {
            "total_connections": len(self.active_connections),
            "subscriptions": {
                channel: len(subscribers)
                for channel, subscribers in self.subscriptions.items()
            },
            "clients": list(self.active_connections.keys())
        }


# 全局连接管理器
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket 端点处理函数"""
    await manager.connect(websocket, client_id)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                await handle_client_message(client_id, message)
            except json.JSONDecodeError:
                await manager.send_personal_message(client_id, {
                    "type": "error",
                    "message": "无效的 JSON 格式"
                })
            except Exception as e:
                logger.error(f"处理消息失败: {e}")
                await manager.send_personal_message(client_id, {
                    "type": "error",
                    "message": f"处理消息失败: {str(e)}"
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket 错误 {client_id}: {e}")
        manager.disconnect(client_id)


async def handle_client_message(client_id: str, message: dict):
    """处理客户端消息"""
    msg_type = message.get("type")

    if msg_type == "subscribe":
        channel = message.get("channel")
        if channel:
            success = manager.subscribe(client_id, channel)
            await manager.send_personal_message(client_id, {
                "type": "subscription_result",
                "channel": channel,
                "success": success,
                "message": f"已订阅 {channel}" if success else f"订阅失败: {channel}"
            })

    elif msg_type == "unsubscribe":
        channel = message.get("channel")
        if channel:
            success = manager.unsubscribe(client_id, channel)
            await manager.send_personal_message(client_id, {
                "type": "unsubscription_result",
                "channel": channel,
                "success": success,
                "message": f"已取消订阅 {channel}" if success else f"取消订阅失败: {channel}"
            })

    elif msg_type == "ping":
        await manager.send_personal_message(client_id, {
            "type": "pong",
            "timestamp": datetime.now(UTC).isoformat()
        })

    elif msg_type == "stats":
        stats = manager.get_stats()
        await manager.send_personal_message(client_id, {
            "type": "stats",
            "data": stats
        })

    else:
        await manager.send_personal_message(client_id, {
            "type": "error",
            "message": f"未知消息类型: {msg_type}"
        })


# 数据推送函数（供其他模块调用）
async def push_price_update(price_data: dict):
    """推送金价更新"""
    await manager.broadcast("price", {
        "type": "price_update",
        "data": price_data
    })


async def push_signal_update(signal_data: dict):
    """推送信号更新"""
    await manager.broadcast("signal", {
        "type": "signal_update",
        "data": signal_data
    })


async def push_news_update(news_data: dict):
    """推送新闻更新"""
    await manager.broadcast("news", {
        "type": "news_update",
        "data": news_data
    })


async def push_debate_result(debate_data: dict):
    """推送辩论结果"""
    await manager.broadcast("debate", {
        "type": "debate_result",
        "data": debate_data
    })


async def push_system_status(status_data: dict):
    """推送系统状态"""
    await manager.broadcast("system", {
        "type": "system_status",
        "data": status_data
    })


# 定时任务
from gold_agent.data.cache import cache
from gold_agent.data.gold_price import fetch_gold_price, gold_cache_key, period_to_months
from gold_agent.data.news import fetch_news_with_sentiment
from gold_agent.quant.signals import generate_signal, get_signal_summary
from gold_agent.db.repository import save_gold_prices, save_news_articles, save_trade_signal
from gold_agent.db.session import SessionLocal


def _db_save_news(records: list[dict]) -> None:
    """将采集到的新闻写入 DB。"""
    try:
        with SessionLocal() as db:
            save_news_articles(db, records)
    except Exception as e:
        logger.warning(f"DB 保存新闻失败: {e}")
        raise


async def periodic_price_push(interval_seconds: int = 60):
    """定时推送金价"""
    while True:
        try:
            period = "1mo"
            df, meta = cache.get_with_meta(
                key=gold_cache_key("intl", period),
                fetch_fn=fetch_gold_price,
                source="intl",
                period=period,
                max_stale_days=0.1,
                months=period_to_months(period),
                expected_frequency="daily",
            )
            if not df.empty:
                # 写入数据库
                records = df.to_dict(orient="records")
                with SessionLocal() as db:
                    save_gold_prices(db, records)

                # 推送
                latest = df.iloc[-1]
                await push_price_update({
                    "date": str(latest["date"]),
                    "open": float(latest["open"]),
                    "high": float(latest["high"]),
                    "low": float(latest["low"]),
                    "close": float(latest["close"]),
                    "volume": float(latest.get("volume", 0)),
                    "meta": meta,
                })
                logger.debug(f"定时推送: 金价 ${latest['close']:.2f}")
        except Exception as e:
            logger.error(f"定时推送金价失败: {e}")
        await asyncio.sleep(interval_seconds)


async def periodic_signal_push(interval_seconds: int = 60):
    """定时推送交易信号"""
    while True:
        try:
            period = "1y"
            df, meta = cache.get_with_meta(
                key=gold_cache_key("intl", period),
                fetch_fn=fetch_gold_price,
                source="intl",
                period=period,
                max_stale_days=0.1,
                months=period_to_months(period),
                expected_frequency="daily",
            )
            if not df.empty:
                signal = generate_signal(df)
                summary = get_signal_summary(signal)

                # 写入数据库
                signal_dict = {
                    "date": df.iloc[-1]["date"],
                    "source": "intl",
                    **signal.to_dict()
                }
                with SessionLocal() as db:
                    save_trade_signal(db, signal_dict)

                # 推送
                await push_signal_update({
                    "signal": signal.to_dict(),
                    "summary": summary,
                    "meta": meta,
                })
                logger.debug(f"定时推送: 信号 {signal.signal.value}")
        except Exception as e:
            logger.error(f"定时推送信号失败: {e}")
        await asyncio.sleep(interval_seconds)


async def periodic_news_push(interval_seconds: int = 300):
    """定时推送新闻"""
    while True:
        try:
            df, meta = cache.get_with_meta(
                key="news_sentiment",
                fetch_fn=fetch_news_with_sentiment,
                ttl=300,
                max_stale_days=1,
                expected_frequency="intraday",
                db_save_fn=_db_save_news,
            )
            if not df.empty:
                avg_score = float(df["sentiment_score"].mean())
                label = (
                    "bullish" if avg_score > 0.2
                    else "bearish" if avg_score < -0.2
                    else "neutral"
                )
                await push_news_update({
                    "total": len(df),
                    "avg_sentiment": avg_score,
                    "label": label,
                    "articles": df.head(5).to_dict(orient="records"),
                    "meta": meta,
                })
                logger.debug(f"定时推送: 新闻 {len(df)} 条")
        except Exception as e:
            logger.error(f"定时推送新闻失败: {e}")
        await asyncio.sleep(interval_seconds)
