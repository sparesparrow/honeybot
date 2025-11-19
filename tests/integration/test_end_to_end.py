"""
End-to-end integration tests for SCAIPOT honeypot system
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.scaipot.bots.base_adapter import IncomingMessage
from src.scaipot.bots.telegram_adapter import TelegramBotAdapter
from src.scaipot.llm_engine.claude_client import ClaudeClient
from src.scaipot.llm_engine.response_generator import ResponseGenerator
from src.scaipot.mcp_integration.mcp_client import MCPPromptsClient
from src.scaipot.orchestrator import MessageOrchestrator
from src.scaipot.storage.session_manager import SessionManager


@pytest.mark.integration
class TestEndToEndConversationFlow:
    """Test complete conversation flow from message to response"""

    @pytest.fixture
    async def full_orchestrator(self, redis_client, mock_claude_client):
        """Create a fully configured orchestrator with all components"""
        # Setup session manager
        session_manager = SessionManager(
            redis_url="redis://localhost:6379/1",
            default_ttl=3600
        )
        session_manager.redis_client = redis_client

        # Setup MCP client mock
        mcp_client = AsyncMock(spec=MCPPromptsClient)
        category_config = {
            "system_prompt": "You are a crypto investor interested in Bitcoin investments. Ask questions to understand their offer.",
            "persona": {"name": "Alex", "age": 28, "background": "Recent college graduate interested in cryptocurrencies"},
            "behavior_notes": "Be enthusiastic but cautious. Ask for specific details about investment opportunities."
        }
        mcp_client.get_category_prompt.return_value = category_config
        mcp_client.list_categories.return_value = ["bitcoin_investment", "romance_scam"]

        # Setup response generator
        response_generator = ResponseGenerator(mock_claude_client, mcp_client, use_cache=False)

        # Setup orchestrator
        orchestrator = MessageOrchestrator(session_manager, response_generator, "bitcoin_investment")

        # Setup mock telegram adapter
        telegram_config = {"bot_token": "test_token_123"}
        telegram_adapter = TelegramBotAdapter(telegram_config)

        # Mock the telegram application to avoid real API calls
        with patch("src.scaipot.bots.telegram_adapter.ApplicationBuilder") as mock_builder:
            mock_app = AsyncMock()
            mock_app.bot = AsyncMock()
            mock_app.bot.send_message = AsyncMock(return_value=True)
            mock_app.bot.send_chat_action = AsyncMock(return_value=True)
            mock_app.bot.get_me = AsyncMock(return_value=AsyncMock(username="test_bot"))

            mock_builder.return_value.token.return_value.build.return_value = mock_app
            telegram_adapter.application = mock_app
            telegram_adapter.is_running = True

        orchestrator.register_bot_adapter("telegram", telegram_adapter)

        yield orchestrator

        # Cleanup
        await session_manager.disconnect()

    @pytest.mark.asyncio
    async def test_complete_conversation_flow(self, full_orchestrator, mock_claude_client):
        """Test a complete conversation from scammer message to honeypot response"""
        orchestrator = full_orchestrator

        # Mock Claude response
        mock_claude_client.generate_response_async.return_value = (
            "That sounds really interesting! I've been looking to invest in some crypto. "
            "Can you tell me more about this Bitcoin opportunity? What kind of returns are we talking about?"
        )

        # Start orchestrator
        await orchestrator.start()
        assert orchestrator.is_running is True

        # Create incoming message from scammer
        incoming_msg = IncomingMessage(
            message_id="msg_123",
            sender_id="scammer_456",
            content="Hi! I have a great Bitcoin investment opportunity for you. "
                   "We can double your money in just 2 weeks!",
            platform="telegram",
            timestamp="2024-01-15T10:30:00Z",
            chat_id="chat_789",
            metadata={
                "username": "crypto_scam_master",
                "first_name": "Scam",
                "last_name": "Master",
                "language_code": "en",
                "is_bot": False,
            }
        )

        # Process the message
        with patch("src.scaipot.orchestrator.asyncio.sleep"):  # Skip delay for faster tests
            await orchestrator.handle_incoming_message(incoming_msg)

        # Verify session was created
        session_id = "telegram:scammer_456"
        session_data = await orchestrator.session_manager.get_session(session_id)
        assert session_data is not None
        assert session_data["platform"] == "telegram"
        assert session_data["category"] == "bitcoin_investment"
        assert session_data["scammer_identifier"] == "scammer_456"
        assert session_data["status"] == "active"

        # Verify conversation history was stored
        history = await orchestrator.session_manager.get_conversation_history(session_id)
        assert len(history) == 2

        # First message (user)
        assert history[0]["role"] == "user"
        assert "Bitcoin investment opportunity" in history[0]["content"]
        assert history[0]["metadata"]["username"] == "crypto_scam_master"

        # Second message (assistant)
        assert history[1]["role"] == "assistant"
        assert "interesting" in history[1]["content"]
        assert "double your money" in history[1]["content"]

        # Verify response was sent via bot adapter
        telegram_adapter = orchestrator.bot_adapters["telegram"]
        telegram_adapter.send_message.assert_called_once()

        sent_message = telegram_adapter.send_message.call_args[0][0]
        assert sent_message.chat_id == "chat_789"
        assert sent_message.reply_to_message_id == "msg_123"
        assert len(sent_message.content) > 50  # Reasonable response length

        # Verify Claude was called with correct parameters
        mock_claude_client.generate_response_async.assert_called_once()
        call_args = mock_claude_client.generate_response_async.call_args
        assert "bitcoin_investment" in call_args[1]["system_prompt"]
        assert "Alex" in call_args[1]["system_prompt"]  # Persona name
        assert "honeypot designed to waste scammer time" in call_args[1]["system_prompt"]
        assert call_args[1]["messages"][0]["role"] == "user"
        assert "Bitcoin investment" in call_args[1]["messages"][0]["content"]

        # Clean up
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_multiple_messages_same_conversation(self, full_orchestrator, mock_claude_client):
        """Test multiple messages in the same conversation"""
        orchestrator = full_orchestrator

        # Mock different responses for each message
        mock_claude_client.generate_response_async.side_effect = [
            "Wow, that sounds amazing! How does this work exactly?",
            "Really? 500% returns? That seems too good to be true. Can you explain the process step by step?",
        ]

        await orchestrator.start()

        # First message
        msg1 = IncomingMessage(
            message_id="msg_1",
            sender_id="scammer_456",
            content="Invest $1000 now and get $6000 back in 2 weeks!",
            platform="telegram",
            timestamp="2024-01-15T10:30:00Z",
            chat_id="chat_789",
            metadata={"username": "crypto_scam_master"}
        )

        # Second message
        msg2 = IncomingMessage(
            message_id="msg_2",
            sender_id="scammer_456",
            content="It's very simple. Just send Bitcoin to this address: bc1q...",
            platform="telegram",
            timestamp="2024-01-15T10:31:00Z",
            chat_id="chat_789",
            metadata={"username": "crypto_scam_master"}
        )

        with patch("src.scaipot.orchestrator.asyncio.sleep"):
            await orchestrator.handle_incoming_message(msg1)
            await orchestrator.handle_incoming_message(msg2)

        session_id = "telegram:scammer_456"

        # Verify conversation history has all messages
        history = await orchestrator.session_manager.get_conversation_history(session_id)
        assert len(history) == 4  # 2 user + 2 assistant messages

        # Check message order and content
        assert history[0]["role"] == "user"
        assert "$1000" in history[0]["content"]

        assert history[1]["role"] == "assistant"
        assert "amazing" in history[1]["content"]

        assert history[2]["role"] == "user"
        assert "bc1q" in history[2]["content"]

        assert history[3]["role"] == "assistant"
        assert "500% returns" in history[3]["content"]

        # Verify both responses were sent
        telegram_adapter = orchestrator.bot_adapters["telegram"]
        assert telegram_adapter.send_message.call_count == 2

        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_different_categories(self, redis_client, mock_claude_client):
        """Test using different honeypot categories"""
        # Setup with romance scam category
        session_manager = SessionManager(redis_url="redis://localhost:6379/1")
        session_manager.redis_client = redis_client

        mcp_client = AsyncMock(spec=MCPPromptsClient)
        romance_config = {
            "system_prompt": "You are looking for love and companionship online.",
            "persona": {"name": "Sarah", "age": 32, "background": "Divorced professional seeking meaningful relationship"},
            "behavior_notes": "Be open and trusting. Share personal details gradually. Express loneliness."
        }
        mcp_client.get_category_prompt.return_value = romance_config

        response_generator = ResponseGenerator(mock_claude_client, mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator, "romance_scam")

        mock_claude_client.generate_response_async.return_value = (
            "Oh wow, you sound like such a kind person! I've been feeling so lonely lately. "
            "Tell me more about yourself and what you're looking for in a relationship."
        )

        # Setup mock adapter
        adapter = AsyncMock()
        adapter.send_message = AsyncMock(return_value=True)
        adapter.send_typing_action = AsyncMock(return_value=True)
        orchestrator.register_bot_adapter("telegram", adapter)

        await orchestrator.start()

        # Send romance scam message
        msg = IncomingMessage(
            message_id="msg_123",
            sender_id="romance_scammer",
            content="Hello beautiful! I saw your profile and I think we could be perfect for each other. I'm a successful businessman from Nigeria.",
            platform="telegram",
            timestamp="2024-01-15T10:30:00Z",
            chat_id="chat_123",
            metadata={"username": "love_scammer"}
        )

        with patch("src.scaipot.orchestrator.asyncio.sleep"):
            await orchestrator.handle_incoming_message(msg)

        # Verify romance category was used
        session_data = await session_manager.get_session("telegram:romance_scammer")
        assert session_data["category"] == "romance_scam"

        # Verify response contains romance-themed content
        call_args = mock_claude_client.generate_response_async.call_args
        system_prompt = call_args[1]["system_prompt"]
        assert "Sarah" in system_prompt  # Persona name
        assert "looking for love" in system_prompt
        assert "lonely" in system_prompt

        response = call_args[0][0]  # First positional arg (system_prompt)
        assert "Sarah" in response
        assert "lonely" in response

        await orchestrator.stop()
        await session_manager.disconnect()

    @pytest.mark.asyncio
    async def test_health_check_integration(self, full_orchestrator):
        """Test health check across all components"""
        orchestrator = full_orchestrator

        await orchestrator.start()

        health = await orchestrator.health_check()

        # Should have health status for all components
        assert "orchestrator" in health
        assert "redis" in health
        assert "bot_telegram" in health

        # All should be healthy
        assert health["orchestrator"] is True
        assert health["redis"] is True
        assert health["bot_telegram"] is True

        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, full_orchestrator, mock_claude_client):
        """Test statistics tracking during conversations"""
        orchestrator = full_orchestrator

        mock_claude_client.generate_response_async.return_value = "Interesting!"

        await orchestrator.start()

        # Send a few messages
        for i in range(3):
            msg = IncomingMessage(
                message_id=f"msg_{i}",
                sender_id="stats_user",
                content=f"Message {i}",
                platform="telegram",
                timestamp=f"2024-01-15T10:{30+i}:00Z",
                chat_id="chat_stats",
                metadata={"username": "stats_tester"}
            )

            with patch("src.scaipot.orchestrator.asyncio.sleep"):
                await orchestrator.handle_incoming_message(msg)

        # Check statistics
        stats = await orchestrator.get_statistics()

        assert stats["is_running"] is True
        assert "telegram" in stats["platforms"]
        assert stats["active_sessions"] >= 1  # At least our session
        assert stats["default_category"] == "bitcoin_investment"

        await orchestrator.stop()


@pytest.mark.integration
class TestErrorRecovery:
    """Test error recovery and resilience"""

    @pytest.mark.asyncio
    async def test_claude_api_failure_recovery(self, redis_client, mock_claude_client):
        """Test recovery when Claude API fails"""
        session_manager = SessionManager(redis_url="redis://localhost:6379/1")
        session_manager.redis_client = redis_client

        mcp_client = AsyncMock(spec=MCPPromptsClient)
        mcp_client.get_category_prompt.return_value = {"system_prompt": "Test"}

        response_generator = ResponseGenerator(mock_claude_client, mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        # Make Claude API fail
        mock_claude_client.generate_response_async.side_effect = Exception("API down")

        adapter = AsyncMock()
        adapter.send_message = AsyncMock(return_value=True)
        adapter.send_typing_action = AsyncMock(return_value=True)
        orchestrator.register_bot_adapter("telegram", adapter)

        await orchestrator.start()

        msg = IncomingMessage(
            message_id="msg_1",
            sender_id="error_user",
            content="Hello",
            platform="telegram",
            timestamp="2024-01-15T10:30:00Z",
            chat_id="chat_1",
            metadata={}
        )

        # Should not crash, should handle error gracefully
        with patch("src.scaipot.orchestrator.asyncio.sleep"):
            await orchestrator.handle_incoming_message(msg)

        # Session should still be created despite API failure
        session_data = await session_manager.get_session("telegram:error_user")
        assert session_data is not None

        # Adapter should still be called (with fallback response)
        adapter.send_message.assert_called_once()

        await orchestrator.stop()
        await session_manager.disconnect()

    @pytest.mark.asyncio
    async def test_adapter_failure_recovery(self, redis_client, mock_claude_client):
        """Test recovery when bot adapter fails"""
        session_manager = SessionManager(redis_url="redis://localhost:6379/1")
        session_manager.redis_client = redis_client

        mcp_client = AsyncMock(spec=MCPPromptsClient)
        mcp_client.get_category_prompt.return_value = {"system_prompt": "Test"}

        response_generator = ResponseGenerator(mock_claude_client, mcp_client)
        orchestrator = MessageOrchestrator(session_manager, response_generator)

        mock_claude_client.generate_response_async.return_value = "Response"

        # Make adapter fail
        adapter = AsyncMock()
        adapter.send_message.return_value = False  # Send fails
        adapter.send_typing_action = AsyncMock(return_value=True)
        orchestrator.register_bot_adapter("telegram", adapter)

        await orchestrator.start()

        msg = IncomingMessage(
            message_id="msg_1",
            sender_id="adapter_fail_user",
            content="Hello",
            platform="telegram",
            timestamp="2024-01-15T10:30:00Z",
            chat_id="chat_1",
            metadata={}
        )

        with patch("src.scaipot.orchestrator.asyncio.sleep"):
            await orchestrator.handle_incoming_message(msg)

        # Session and history should still be created
        session_data = await session_manager.get_session("telegram:adapter_fail_user")
        assert session_data is not None

        history = await session_manager.get_conversation_history("telegram:adapter_fail_user")
        assert len(history) == 2  # User message + assistant response still stored

        await orchestrator.stop()
        await session_manager.disconnect()