"""WebSocket 接口单元测试 — ConnectionManager + WebSocket 端点"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketState

from gold_agent.api.websocket import (
    ConnectionManager,
    push_debate_result,
    push_news_update,
    push_price_update,
    push_signal_update,
    push_system_status,
)
from gold_agent.main import app

client = TestClient(app)


# ============================================================
# ConnectionManager 单元测试
# ============================================================


class TestConnectionManager:
    """ConnectionManager 核心功能"""

    @pytest.fixture
    def manager(self):
        return ConnectionManager()

    @pytest.fixture
    def mock_ws(self):
        ws = MagicMock()
        ws.client_state = WebSocketState.CONNECTED
        ws.send_json = AsyncMock()
        ws.accept = AsyncMock()
        return ws

    # --- connect / disconnect ---

    @pytest.mark.asyncio
    async def test_connect_adds_client(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")
        assert "client1" in manager.active_connections
        assert "client1" in manager.client_subscriptions
        assert mock_ws.send_json.await_count == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")
        manager.disconnect("client1")
        assert "client1" not in manager.active_connections
        assert "client1" not in manager.client_subscriptions

    @pytest.mark.asyncio
    async def test_disconnect_cleans_subscriptions(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")
        manager.subscribe("client1", "price")
        assert "client1" in manager.subscriptions["price"]

        manager.disconnect("client1")
        assert "client1" not in manager.subscriptions["price"]

    # --- subscribe / unsubscribe ---

    def test_subscribe_unknown_channel_returns_false(self, manager):
        assert manager.subscribe("client1", "unknown_channel") is False

    @pytest.mark.asyncio
    async def test_subscribe_known_channel_returns_true(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")
        assert manager.subscribe("client1", "price") is True
        assert "client1" in manager.subscriptions["price"]

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_client(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")
        manager.subscribe("client1", "price")
        assert manager.unsubscribe("client1", "price") is True
        assert "client1" not in manager.subscriptions["price"]

    def test_unsubscribe_unknown_channel_returns_false(self, manager):
        assert manager.unsubscribe("client1", "unknown") is False

    # --- broadcast ---

    @pytest.mark.asyncio
    async def test_broadcast_delivers_to_subscribers(self, manager, mock_ws):
        manager.active_connections["client1"] = mock_ws
        manager.subscriptions["price"].add("client1")

        await manager.broadcast("price", {"type": "test", "data": "hello"})

        mock_ws.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_unknown_channel_does_nothing(self, manager):
        # Should not raise
        await manager.broadcast("unknown", {"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_skips_disconnected_clients(self, manager):
        ws = MagicMock()
        ws.client_state = WebSocketState.DISCONNECTED
        manager.active_connections["client1"] = ws
        manager.subscriptions["price"].add("client1")

        await manager.broadcast("price", {"type": "test"})
        # disconnected client is removed
        assert "client1" not in manager.active_connections

    # --- stats ---

    @pytest.mark.asyncio
    async def test_get_stats_format(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")

        stats = manager.get_stats()
        assert stats["total_connections"] == 1
        assert "subscriptions" in stats
        assert "clients" in stats
        assert "client1" in stats["clients"]


# ============================================================
# WebSocket 端点集成测试
# ============================================================


class TestWebSocketEndpoints:
    """通过 TestClient 测试 WebSocket 端点"""

    def test_connect_receives_welcome(self):
        with client.websocket_connect("/ws/test-client") as ws:
            data = ws.receive_json()
            assert data["type"] == "connection"
            assert data["client_id"] == "test-client"
            assert "available_channels" in data

    def test_subscribe_channel(self):
        with client.websocket_connect("/ws/test-client") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "price"})
            data = ws.receive_json()
            assert data["type"] == "subscription_result"
            assert data["success"] is True
            assert data["channel"] == "price"

    def test_subscribe_unknown_channel(self):
        with client.websocket_connect("/ws/test-client") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "nonexistent"})
            data = ws.receive_json()
            assert data["type"] == "subscription_result"
            assert data["success"] is False

    def test_unsubscribe_channel(self):
        with client.websocket_connect("/ws/test-client") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "subscribe", "channel": "price"})
            ws.receive_json()  # subscription_result

            ws.send_json({"type": "unsubscribe", "channel": "price"})
            data = ws.receive_json()
            assert data["type"] == "unsubscription_result"
            assert data["success"] is True

    def test_ping_returns_pong(self):
        with client.websocket_connect("/ws/test-client") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"
            assert "timestamp" in data

    def test_unknown_message_type_returns_error(self):
        with client.websocket_connect("/ws/test-client") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "invalid_type"})
            data = ws.receive_json()
            assert data["type"] == "error"

    def test_invalid_json_returns_error(self):
        with client.websocket_connect("/ws/test-client") as ws:
            ws.receive_json()  # welcome
            ws.send_text("not valid json")
            data = ws.receive_json()
            assert data["type"] == "error"

    def test_stats_message(self):
        with client.websocket_connect("/ws/test-client") as ws:
            ws.receive_json()  # welcome
            ws.send_json({"type": "stats"})
            data = ws.receive_json()
            assert data["type"] == "stats"
            assert "data" in data
            assert data["data"]["total_connections"] >= 1


# ============================================================
# Push 函数测试
# ============================================================


class TestPushFunctions:
    """数据推送函数 — 验证委托给 manager.broadcast"""

    @pytest.mark.asyncio
    async def test_push_price_update(self):
        with patch("gold_agent.api.websocket.manager.broadcast") as mock_broadcast:
            await push_price_update({"price": 2000.0})
            mock_broadcast.assert_awaited_once_with(
                "price",
                {"type": "price_update", "data": {"price": 2000.0}},
            )

    @pytest.mark.asyncio
    async def test_push_signal_update(self):
        with patch("gold_agent.api.websocket.manager.broadcast") as mock_broadcast:
            await push_signal_update({"signal": "buy"})
            mock_broadcast.assert_awaited_once_with(
                "signal",
                {"type": "signal_update", "data": {"signal": "buy"}},
            )

    @pytest.mark.asyncio
    async def test_push_news_update(self):
        with patch("gold_agent.api.websocket.manager.broadcast") as mock_broadcast:
            await push_news_update({"headline": "Gold rally"})
            mock_broadcast.assert_awaited_once_with(
                "news",
                {"type": "news_update", "data": {"headline": "Gold rally"}},
            )

    @pytest.mark.asyncio
    async def test_push_debate_result(self):
        with patch("gold_agent.api.websocket.manager.broadcast") as mock_broadcast:
            await push_debate_result({"verdict": "bullish"})
            mock_broadcast.assert_awaited_once_with(
                "debate",
                {"type": "debate_result", "data": {"verdict": "bullish"}},
            )

    @pytest.mark.asyncio
    async def test_push_system_status(self):
        with patch("gold_agent.api.websocket.manager.broadcast") as mock_broadcast:
            await push_system_status({"status": "healthy"})
            mock_broadcast.assert_awaited_once_with(
                "system",
                {"type": "system_status", "data": {"status": "healthy"}},
            )
