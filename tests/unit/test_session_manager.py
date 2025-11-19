"""
Unit tests for SessionManager class
"""
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as redis

from scaipot.storage.session_manager import SessionManager


class TestSessionManagerInit:
    """Test SessionManager initialization"""

    def test_init_default_values(self):
        """Test initialization with default values"""
        manager = SessionManager("redis://localhost:6379")

        assert manager.redis_url == "redis://localhost:6379"
        assert manager.redis_password is None
        assert manager.default_ttl == 7200  # 2 hours
        assert manager.redis_client is None

    def test_init_custom_values(self):
        """Test initialization with custom values"""
        manager = SessionManager(
            redis_url="redis://localhost:6379/1",
            redis_password="test_pass",
            default_ttl=3600
        )

        assert manager.redis_url == "redis://localhost:6379/1"
        assert manager.redis_password == "test_pass"
        assert manager.default_ttl == 3600


class TestSessionManagerConnection:
    """Test Redis connection methods"""

    @pytest.mark.asyncio
    async def test_connect_success(self, session_manager):
        """Test successful Redis connection"""
        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            await session_manager.connect()

            assert session_manager.redis_client is not None
            mock_logger.info.assert_called_with("Connected to Redis successfully")

    @pytest.mark.asyncio
    async def test_connect_failure(self, session_manager):
        """Test Redis connection failure"""
        # Use invalid Redis URL
        session_manager.redis_url = "redis://invalid:6379"

        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            with pytest.raises(Exception):
                await session_manager.connect()

            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_disconnect(self, session_manager):
        """Test Redis disconnection"""
        await session_manager.connect()
        assert session_manager.redis_client is not None

        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            await session_manager.disconnect()

            assert session_manager.redis_client is None
            mock_logger.info.assert_called_with("Disconnected from Redis")


class TestSessionManagerCreateSession:
    """Test session creation functionality"""

    @pytest.mark.asyncio
    async def test_create_session_success(self, session_manager):
        """Test successful session creation"""
        session_id = "test_session_123"
        platform = "telegram"
        category = "bitcoin_investment"
        scammer_id = "user_456"

        with patch("src.scaipot.storage.session_manager.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 0)
            with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
                result = await session_manager.create_session(
                    session_id, platform, category, scammer_id
                )

                assert result is True
                mock_logger.info.assert_called_with(
                    f"Created session {session_id} for {platform}/{category}"
                )

    @pytest.mark.asyncio
    async def test_create_session_with_metadata(self, session_manager):
        """Test session creation with metadata"""
        session_id = "test_session_123"
        metadata = {"ip_address": "192.168.1.1", "user_agent": "test"}

        result = await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456", metadata
        )

        assert result is True

        # Verify session data
        session_data = await session_manager.get_session(session_id)
        assert session_data["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_create_session_failure(self, session_manager):
        """Test session creation failure"""
        # Disconnect Redis to simulate failure
        await session_manager.disconnect()
        session_manager.redis_client = None

        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.create_session(
                "test_session", "telegram", "category", "user"
            )

            assert result is False
            mock_logger.error.assert_called()


class TestSessionManagerGetSession:
    """Test session retrieval functionality"""

    @pytest.mark.asyncio
    async def test_get_session_existing(self, session_manager):
        """Test retrieving existing session"""
        session_id = "test_session_123"

        # Create session first
        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )

        # Retrieve session
        session_data = await session_manager.get_session(session_id)

        assert session_data is not None
        assert session_data["session_id"] == session_id
        assert session_data["platform"] == "telegram"
        assert session_data["category"] == "bitcoin_investment"
        assert session_data["scammer_identifier"] == "user_456"
        assert session_data["status"] == "active"
        assert session_data["message_count"] == 0
        assert "created_at" in session_data
        assert "last_activity" in session_data

    @pytest.mark.asyncio
    async def test_get_session_nonexistent(self, session_manager):
        """Test retrieving non-existent session"""
        session_data = await session_manager.get_session("nonexistent_session")

        assert session_data is None

    @pytest.mark.asyncio
    async def test_get_session_failure(self, session_manager):
        """Test session retrieval failure"""
        # Disconnect Redis
        await session_manager.disconnect()
        session_manager.redis_client = None

        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.get_session("test_session")

            assert result is None
            mock_logger.error.assert_called()


class TestSessionManagerUpdateSession:
    """Test session update functionality"""

    @pytest.mark.asyncio
    async def test_update_session_success(self, session_manager):
        """Test successful session update"""
        session_id = "test_session_123"

        # Create session
        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )

        # Update session
        updates = {"message_count": 5, "status": "completed"}
        result = await session_manager.update_session(session_id, updates)

        assert result is True

        # Verify updates
        session_data = await session_manager.get_session(session_id)
        assert session_data["message_count"] == 5
        assert session_data["status"] == "completed"
        assert "last_activity" in session_data

    @pytest.mark.asyncio
    async def test_update_session_nonexistent(self, session_manager):
        """Test updating non-existent session"""
        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.update_session("nonexistent", {"status": "active"})

            assert result is False
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_update_session_failure(self, session_manager):
        """Test session update failure"""
        session_id = "test_session_123"

        # Create session
        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )

        # Disconnect Redis
        await session_manager.disconnect()
        session_manager.redis_client = None

        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.update_session(session_id, {"status": "completed"})

            assert result is False
            mock_logger.error.assert_called()


class TestSessionManagerMessageHistory:
    """Test message history functionality"""

    @pytest.mark.asyncio
    async def test_add_message_to_history_success(self, session_manager):
        """Test adding message to history"""
        session_id = "test_session_123"
        role = "user"
        content = "Hello, I'm interested in crypto"

        # Create session
        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )

        # Add message
        with patch("src.scaipot.storage.session_manager.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 10, 30, 0)
            with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
                result = await session_manager.add_message_to_history(session_id, role, content)

                assert result is True
                mock_logger.debug.assert_called_with(f"Added {role} message to session {session_id}")

        # Verify message count updated
        session_data = await session_manager.get_session(session_id)
        assert session_data["message_count"] == 1

    @pytest.mark.asyncio
    async def test_add_message_with_metadata(self, session_manager):
        """Test adding message with metadata"""
        session_id = "test_session_123"
        metadata = {"confidence": 0.95, "intent": "investment_inquiry"}

        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )

        result = await session_manager.add_message_to_history(
            session_id, "assistant", "I'd be happy to help!", metadata
        )

        assert result is True

        # Verify message stored with metadata
        history = await session_manager.get_conversation_history(session_id)
        assert len(history) == 1
        assert history[0]["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_get_conversation_history_full(self, session_manager):
        """Test retrieving full conversation history"""
        session_id = "test_session_123"

        # Create session and add messages
        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )

        messages = [
            ("user", "Hello"),
            ("assistant", "Hi there!"),
            ("user", "Tell me about Bitcoin"),
            ("assistant", "Bitcoin is a cryptocurrency..."),
        ]

        for role, content in messages:
            await session_manager.add_message_to_history(session_id, role, content)

        # Retrieve history
        history = await session_manager.get_conversation_history(session_id)

        assert len(history) == 4
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_get_conversation_history_limited(self, session_manager):
        """Test retrieving limited conversation history"""
        session_id = "test_session_123"

        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )

        # Add 5 messages
        for i in range(5):
            await session_manager.add_message_to_history(
                session_id, "user", f"Message {i}"
            )

        # Retrieve last 3 messages
        history = await session_manager.get_conversation_history(session_id, limit=3)

        assert len(history) == 3
        assert history[0]["content"] == "Message 2"  # Redis lrange with limit
        assert history[2]["content"] == "Message 4"

    @pytest.mark.asyncio
    async def test_get_message_count(self, session_manager):
        """Test getting message count"""
        session_id = "test_session_123"

        # Create session
        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )

        # Initially 0 messages
        count = await session_manager.get_message_count(session_id)
        assert count == 0

        # Add messages
        await session_manager.add_message_to_history(session_id, "user", "Hello")
        await session_manager.add_message_to_history(session_id, "assistant", "Hi!")

        count = await session_manager.get_message_count(session_id)
        assert count == 2


class TestSessionManagerDeleteSession:
    """Test session deletion functionality"""

    @pytest.mark.asyncio
    async def test_delete_session_success(self, session_manager):
        """Test successful session deletion"""
        session_id = "test_session_123"

        # Create session and add messages
        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )
        await session_manager.add_message_to_history(session_id, "user", "Hello")

        # Delete session
        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.delete_session(session_id)

            assert result is True
            mock_logger.info.assert_called_with(f"Deleted session {session_id}")

        # Verify session is gone
        session_data = await session_manager.get_session(session_id)
        assert session_data is None

        # Verify history is gone
        history = await session_manager.get_conversation_history(session_id)
        assert history == []

    @pytest.mark.asyncio
    async def test_delete_session_nonexistent(self, session_manager):
        """Test deleting non-existent session"""
        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.delete_session("nonexistent")

            assert result is True  # Redis delete on non-existent keys succeeds
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_delete_session_failure(self, session_manager):
        """Test session deletion failure"""
        # Disconnect Redis
        await session_manager.disconnect()
        session_manager.redis_client = None

        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.delete_session("test_session")

            assert result is False
            mock_logger.error.assert_called()


class TestSessionManagerExtendTTL:
    """Test TTL extension functionality"""

    @pytest.mark.asyncio
    async def test_extend_session_ttl_success(self, session_manager):
        """Test successful TTL extension"""
        session_id = "test_session_123"

        # Create session
        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )

        # Mock TTL check
        session_manager.redis_client.ttl = AsyncMock(return_value=1800)  # 30 minutes left

        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.extend_session_ttl(session_id, 3600)

            assert result is True
            mock_logger.debug.assert_called()

        # Verify TTL was extended for both keys
        session_manager.redis_client.expire.assert_called()
        assert session_manager.redis_client.expire.call_count == 2

    @pytest.mark.asyncio
    async def test_extend_session_ttl_expired_session(self, session_manager):
        """Test TTL extension on expired session"""
        session_id = "test_session_123"

        await session_manager.create_session(
            session_id, "telegram", "bitcoin_investment", "user_456"
        )

        # Mock expired TTL
        session_manager.redis_client.ttl = AsyncMock(return_value=0)

        result = await session_manager.extend_session_ttl(session_id, 3600)

        assert result is False

    @pytest.mark.asyncio
    async def test_extend_session_ttl_failure(self, session_manager):
        """Test TTL extension failure"""
        # Disconnect Redis
        await session_manager.disconnect()
        session_manager.redis_client = None

        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.extend_session_ttl("test_session", 3600)

            assert result is False
            mock_logger.error.assert_called()


class TestSessionManagerListSessions:
    """Test session listing functionality"""

    @pytest.mark.asyncio
    async def test_list_active_sessions_all(self, session_manager):
        """Test listing all active sessions"""
        # Create multiple sessions
        sessions = ["session_1", "session_2", "session_3"]
        for session_id in sessions:
            await session_manager.create_session(
                session_id, "telegram", "bitcoin_investment", f"user_{session_id}"
            )

        # List all sessions
        active_sessions = await session_manager.list_active_sessions()

        assert len(active_sessions) >= 3  # May have more from other tests
        assert "session_1" in active_sessions
        assert "session_2" in active_sessions
        assert "session_3" in active_sessions

    @pytest.mark.asyncio
    async def test_list_active_sessions_pattern(self, session_manager):
        """Test listing sessions with pattern"""
        # Create sessions with different patterns
        await session_manager.create_session(
            "telegram_001", "telegram", "bitcoin_investment", "user_1"
        )
        await session_manager.create_session(
            "signal_001", "signal", "romance_scam", "user_2"
        )

        telegram_sessions = await session_manager.list_active_sessions("telegram*")

        assert "telegram_001" in telegram_sessions
        assert "signal_001" not in telegram_sessions

    @pytest.mark.asyncio
    async def test_list_active_sessions_failure(self, session_manager):
        """Test session listing failure"""
        # Disconnect Redis
        await session_manager.disconnect()
        session_manager.redis_client = None

        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.list_active_sessions()

            assert result == []
            mock_logger.error.assert_called()


class TestSessionManagerHealthCheck:
    """Test health check functionality"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, session_manager):
        """Test successful health check"""
        result = await session_manager.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, session_manager):
        """Test health check failure"""
        # Disconnect Redis
        await session_manager.disconnect()
        session_manager.redis_client = None

        with patch("src.scaipot.storage.session_manager.logger") as mock_logger:
            result = await session_manager.health_check()

            assert result is False
            mock_logger.error.assert_called()


class TestSessionManagerKeyGeneration:
    """Test Redis key generation"""

    def test_get_session_key(self, session_manager):
        """Test session key generation"""
        session_id = "test_session_123"
        expected_key = f"session:{session_id}"

        result = session_manager._get_session_key(session_id)
        assert result == expected_key

    def test_get_history_key(self, session_manager):
        """Test history key generation"""
        session_id = "test_session_123"
        expected_key = f"history:{session_id}"

        result = session_manager._get_history_key(session_id)
        assert result == expected_key