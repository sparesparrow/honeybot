"""
Unit tests for MessageOrchestrator class
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scaipot.bots.base_adapter import BaseBotAdapter, IncomingMessage, OutgoingMessage
from scaipot.llm_engine.response_generator import ResponseGenerator
from scaipot.orchestrator import MessageOrchestrator
from scaipot.storage.session_manager import SessionManager


class TestMessageOrchestratorInit:
    """Test MessageOrchestrator initialization"""

    def test_init_default_values(self, session_manager, mock_claude_client):
        """Test initialization with default values"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        orchestrator = MessageOrchestrator(session_manager, response_generator)

        assert orchestrator.session_manager == session_manager
        assert orchestrator.response_generator == response_generator
        assert orchestrator.default_category == "bitcoin_investment"
        assert orchestrator.bot_adapters == {}
        assert orchestrator.is_running is False

    def test_init_custom_category(self, session_manager, mock_claude_client):
        """Test initialization with custom default category"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        orchestrator = MessageOrchestrator(
            session_manager, response_generator, default_category="romance_scam"
        )

        assert orchestrator.default_category == "romance_scam"


class TestMessageOrchestratorAdapterRegistration:
    """Test bot adapter registration"""

    def test_register_bot_adapter(self, session_manager, mock_claude_client):
        """Test successful bot adapter registration"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        mock_adapter = MagicMock(spec=BaseBotAdapter)

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            orchestrator.register_bot_adapter("telegram", mock_adapter)

            assert "telegram" in orchestrator.bot_adapters
            assert orchestrator.bot_adapters["telegram"] == mock_adapter
            mock_adapter.register_message_handler.assert_called_once_with(
                orchestrator.handle_incoming_message
            )
            mock_logger.info.assert_called_with("Registered bot adapter for platform: telegram")


class TestMessageOrchestratorLifecycle:
    """Test orchestrator start/stop lifecycle"""

    @pytest.mark.asyncio
    async def test_start_success(self, session_manager, mock_claude_client):
        """Test successful orchestrator startup"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        # Register mock adapters
        mock_adapter1 = AsyncMock(spec=BaseBotAdapter)
        mock_adapter2 = AsyncMock(spec=BaseBotAdapter)
        orchestrator.register_bot_adapter("telegram", mock_adapter1)
        orchestrator.register_bot_adapter("signal", mock_adapter2)

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            await orchestrator.start()

            assert orchestrator.is_running is True
            session_manager.connect.assert_called_once()
            mock_adapter1.start.assert_called_once()
            mock_adapter2.start.assert_called_once()
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_start_failure(self, session_manager, mock_claude_client):
        """Test orchestrator startup failure"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        # Make session manager connection fail
        session_manager.connect.side_effect = Exception("Redis connection failed")

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            with pytest.raises(Exception, match="Redis connection failed"):
                await orchestrator.start()

            assert orchestrator.is_running is False
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_stop_success(self, session_manager, mock_claude_client):
        """Test successful orchestrator shutdown"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)
        orchestrator.is_running = True

        # Register mock adapters
        mock_adapter1 = AsyncMock(spec=BaseBotAdapter)
        mock_adapter2 = AsyncMock(spec=BaseBotAdapter)
        orchestrator.register_bot_adapter("telegram", mock_adapter1)
        orchestrator.register_bot_adapter("signal", mock_adapter2)

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            await orchestrator.stop()

            assert orchestrator.is_running is False
            session_manager.disconnect.assert_called_once()
            mock_adapter1.stop.assert_called_once()
            mock_adapter2.stop.assert_called_once()
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_stop_with_errors(self, session_manager, mock_claude_client):
        """Test orchestrator shutdown with adapter errors"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)
        orchestrator.is_running = True

        # Register adapter that fails to stop
        mock_adapter = AsyncMock(spec=BaseBotAdapter)
        mock_adapter.stop.side_effect = Exception("Stop failed")
        orchestrator.register_bot_adapter("telegram", mock_adapter)

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            await orchestrator.stop()

            # Should still complete shutdown despite errors
            assert orchestrator.is_running is False
            mock_logger.error.assert_called()


class TestMessageOrchestratorMessageHandling:
    """Test incoming message handling"""

    @pytest.mark.asyncio
    async def test_handle_incoming_message_success(self, session_manager, mock_claude_client, incoming_message):
        """Test successful message handling"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        # Setup mocks
        mock_adapter = AsyncMock(spec=BaseBotAdapter)
        orchestrator.register_bot_adapter("telegram", mock_adapter)

        session_data = {
            "session_id": "telegram:user_123",
            "category": "bitcoin_investment",
            "status": "active"
        }
        session_manager.get_session.return_value = session_data
        response_generator.generate_honeypot_response.return_value = "That sounds interesting!"

        with patch("src.scaipot.orchestrator.asyncio.sleep") as mock_sleep:
            with patch("src.scaipot.orchestrator.logger") as mock_logger:
                await orchestrator.handle_incoming_message(incoming_message)

                # Verify session was retrieved
                session_manager.get_session.assert_called_once_with("telegram:user_123")

                # Verify typing action was sent
                mock_adapter.send_typing_action.assert_called_once_with("chat_123")

                # Verify delay was added
                mock_sleep.assert_called_once_with(1.5)

                # Verify response generation was called
                response_generator.generate_honeypot_response.assert_called_once()
                call_args = response_generator.generate_honeypot_response.call_args
                assert call_args[1]["category"] == "bitcoin_investment"
                assert call_args[1]["incoming_message"] == "Hello, I'm interested in crypto investments"
                assert call_args[1]["platform"] == "telegram"

                # Verify messages were added to history
                assert session_manager.add_message_to_history.call_count == 2

                # Verify response was sent
                mock_adapter.send_message.assert_called_once()
                sent_message = mock_adapter.send_message.call_args[0][0]
                assert sent_message.chat_id == "chat_123"
                assert sent_message.content == "That sounds interesting!"
                assert sent_message.reply_to_message_id == "12345"

                mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_handle_incoming_message_new_session(self, session_manager, mock_claude_client, incoming_message):
        """Test message handling that creates a new session"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        # Setup mocks
        mock_adapter = AsyncMock(spec=BaseBotAdapter)
        orchestrator.register_bot_adapter("telegram", mock_adapter)

        # No existing session
        session_manager.get_session.return_value = None
        session_manager.create_session.return_value = True

        session_data = {
            "session_id": "telegram:user_123",
            "category": "bitcoin_investment",
            "status": "active"
        }
        session_manager.get_session.side_effect = [None, session_data]  # First call returns None, second returns session

        response_generator.generate_honeypot_response.return_value = "Welcome!"

        with patch("src.scaipot.orchestrator.asyncio.sleep"):
            await orchestrator.handle_incoming_message(incoming_message)

            # Verify session creation was attempted
            session_manager.create_session.assert_called_once()
            create_call = session_manager.create_session.call_args
            assert create_call[1]["session_id"] == "telegram:user_123"
            assert create_call[1]["platform"] == "telegram"
            assert create_call[1]["category"] == "bitcoin_investment"
            assert create_call[1]["scammer_identifier"] == "user_123"

    @pytest.mark.asyncio
    async def test_handle_incoming_message_no_adapter(self, session_manager, mock_claude_client, incoming_message):
        """Test message handling when no adapter is registered for platform"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        # No adapters registered
        incoming_message.platform = "unknown_platform"

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            await orchestrator.handle_incoming_message(incoming_message)

            mock_logger.error.assert_called_with("No adapter for platform: unknown_platform")

    @pytest.mark.asyncio
    async def test_handle_incoming_message_session_failure(self, session_manager, mock_claude_client, incoming_message):
        """Test message handling when session creation/retrieval fails"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        mock_adapter = AsyncMock(spec=BaseBotAdapter)
        orchestrator.register_bot_adapter("telegram", mock_adapter)

        # Session retrieval fails
        session_manager.get_session.return_value = None
        session_manager.create_session.return_value = False

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            await orchestrator.handle_incoming_message(incoming_message)

            mock_logger.error.assert_called()
            # Should not proceed to response generation
            response_generator.generate_honeypot_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_incoming_message_send_failure(self, session_manager, mock_claude_client, incoming_message):
        """Test message handling when sending response fails"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        mock_adapter = AsyncMock(spec=BaseBotAdapter)
        mock_adapter.send_message.return_value = False  # Send fails
        orchestrator.register_bot_adapter("telegram", mock_adapter)

        session_manager.get_session.return_value = {"category": "bitcoin_investment"}
        response_generator.generate_honeypot_response.return_value = "Response"

        with patch("src.scaipot.orchestrator.asyncio.sleep"):
            with patch("src.scaipot.orchestrator.logger") as mock_logger:
                await orchestrator.handle_incoming_message(incoming_message)

                mock_adapter.send_message.assert_called_once()
                mock_logger.error.assert_called_with("Failed to send response message")

    @pytest.mark.asyncio
    async def test_handle_incoming_message_exception(self, session_manager, mock_claude_client, incoming_message):
        """Test message handling with unexpected exception"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        mock_adapter = AsyncMock(spec=BaseBotAdapter)
        orchestrator.register_bot_adapter("telegram", mock_adapter)

        # Make response generation fail
        response_generator.generate_honeypot_response.side_effect = Exception("Generation failed")

        with patch("src.scaipot.orchestrator.asyncio.sleep"):
            with patch("src.scaipot.orchestrator.logger") as mock_logger:
                await orchestrator.handle_incoming_message(incoming_message)

                mock_logger.error.assert_called()


class TestMessageOrchestratorSessionManagement:
    """Test session management helpers"""

    @pytest.mark.asyncio
    async def test_get_or_create_session_existing(self, session_manager, mock_claude_client, incoming_message):
        """Test getting existing session"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        session_data = {"session_id": "telegram:user_123", "category": "bitcoin_investment"}
        session_manager.get_session.return_value = session_data

        result = await orchestrator._get_or_create_session("telegram:user_123", incoming_message)

        assert result == session_data
        session_manager.update_session.assert_called_once_with(
            "telegram:user_123", {"status": "active"}
        )
        session_manager.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_session_new(self, session_manager, mock_claude_client, incoming_message):
        """Test creating new session"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        # No existing session
        session_manager.get_session.return_value = None
        session_manager.create_session.return_value = True

        session_data = {"session_id": "telegram:user_123", "category": "bitcoin_investment"}
        session_manager.get_session.side_effect = [None, session_data]  # First None, then session

        result = await orchestrator._get_or_create_session("telegram:user_123", incoming_message)

        assert result == session_data
        session_manager.create_session.assert_called_once()
        create_call = session_manager.create_session.call_args
        assert create_call[1]["platform"] == "telegram"
        assert create_call[1]["category"] == "bitcoin_investment"

    @pytest.mark.asyncio
    async def test_get_or_create_session_creation_failure(self, session_manager, mock_claude_client, incoming_message):
        """Test session creation failure"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        session_manager.get_session.return_value = None
        session_manager.create_session.return_value = False

        result = await orchestrator._get_or_create_session("telegram:user_123", incoming_message)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_formatted_history_success(self, session_manager, mock_claude_client):
        """Test getting formatted conversation history"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        history_data = [
            {"role": "user", "content": "Hello", "timestamp": "2024-01-01T10:00:00Z"},
            {"role": "assistant", "content": "Hi there!", "timestamp": "2024-01-01T10:00:05Z"}
        ]
        session_manager.get_conversation_history.return_value = history_data

        result = await orchestrator._get_formatted_history("session_123")

        expected = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        assert result == expected
        session_manager.get_conversation_history.assert_called_once_with("session_123", limit=20)

    @pytest.mark.asyncio
    async def test_get_formatted_history_failure(self, session_manager, mock_claude_client):
        """Test formatted history retrieval failure"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        session_manager.get_conversation_history.side_effect = Exception("History error")

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            result = await orchestrator._get_formatted_history("session_123")

            assert result == []
            mock_logger.error.assert_called()

    def test_generate_session_id(self, session_manager, mock_claude_client):
        """Test session ID generation"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        session_id = orchestrator._generate_session_id("telegram", "user_456")

        assert session_id == "telegram:user_456"


class TestMessageOrchestratorStatistics:
    """Test statistics and monitoring"""

    @pytest.mark.asyncio
    async def test_get_active_sessions_count_success(self, session_manager, mock_claude_client):
        """Test getting active sessions count"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        sessions = ["session_1", "session_2", "session_3"]
        session_manager.list_active_sessions.return_value = sessions

        count = await orchestrator.get_active_sessions_count()

        assert count == 3
        session_manager.list_active_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_sessions_count_failure(self, session_manager, mock_claude_client):
        """Test active sessions count failure"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        session_manager.list_active_sessions.side_effect = Exception("List error")

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            count = await orchestrator.get_active_sessions_count()

            assert count == 0
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_get_statistics_success(self, session_manager, mock_claude_client):
        """Test getting orchestrator statistics"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)
        orchestrator.is_running = True

        # Register adapters
        mock_adapter = MagicMock(spec=BaseBotAdapter)
        orchestrator.register_bot_adapter("telegram", mock_adapter)
        orchestrator.register_bot_adapter("signal", mock_adapter)

        session_manager.list_active_sessions.return_value = ["session_1", "session_2"]

        stats = await orchestrator.get_statistics()

        expected = {
            "is_running": True,
            "platforms": ["telegram", "signal"],
            "active_sessions": 2,
            "default_category": "bitcoin_investment",
        }
        assert stats == expected

    @pytest.mark.asyncio
    async def test_get_statistics_failure(self, session_manager, mock_claude_client):
        """Test statistics retrieval failure"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        session_manager.list_active_sessions.side_effect = Exception("Stats error")

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            stats = await orchestrator.get_statistics()

            assert stats == {}
            mock_logger.error.assert_called()


class TestMessageOrchestratorHealthCheck:
    """Test health check functionality"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, session_manager, mock_claude_client):
        """Test successful health check"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)
        orchestrator.is_running = True

        # Register adapters
        mock_adapter1 = AsyncMock(spec=BaseBotAdapter)
        mock_adapter1.health_check.return_value = True
        mock_adapter2 = AsyncMock(spec=BaseBotAdapter)
        mock_adapter2.health_check.return_value = False

        orchestrator.register_bot_adapter("telegram", mock_adapter1)
        orchestrator.register_bot_adapter("signal", mock_adapter2)

        session_manager.health_check.return_value = True

        health = await orchestrator.health_check()

        expected = {
            "orchestrator": True,
            "redis": True,
            "bot_telegram": True,
            "bot_signal": False,
        }
        assert health == expected

    @pytest.mark.asyncio
    async def test_health_check_failure(self, session_manager, mock_claude_client):
        """Test health check failure"""
        mock_mcp_client = AsyncMock()
        response_generator = ResponseGenerator(mock_claude_client, mock_mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        # Make Redis health check fail
        session_manager.health_check.side_effect = Exception("Health check error")

        with patch("src.scaipot.orchestrator.logger") as mock_logger:
            health = await orchestrator.health_check()

            assert health == {"error": True}
            mock_logger.error.assert_called()