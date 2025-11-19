"""
Unit tests for TelegramBotAdapter class
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update
from telegram.constants import ChatAction

from src.scaipot.bots.base_adapter import IncomingMessage, OutgoingMessage
from src.scaipot.bots.telegram_adapter import TelegramBotAdapter


class TestTelegramBotAdapterInit:
    """Test TelegramBotAdapter initialization"""

    def test_init_basic(self, test_config):
        """Test basic initialization"""
        config = {"bot_token": "test_token_123"}

        adapter = TelegramBotAdapter(config)

        assert adapter.platform_name == "telegram"
        assert adapter.config == config
        assert adapter.bot_token == "test_token_123"
        assert adapter.application is None
        assert adapter.message_handler_callback is None
        assert adapter.is_running is False

    def test_init_missing_token(self):
        """Test initialization with missing bot token"""
        config = {}

        with pytest.raises(ValueError, match="telegram adapter missing required config"):
            TelegramBotAdapter(config)


class TestTelegramBotAdapterLifecycle:
    """Test bot lifecycle methods"""

    @pytest.mark.asyncio
    async def test_start_success(self, test_config, mock_telegram_application):
        """Test successful bot startup"""
        config = {"bot_token": "test_token_123"}
        adapter = TelegramBotAdapter(config)

        with patch("src.scaipot.bots.telegram_adapter.ApplicationBuilder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_telegram_application

            with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
                await adapter.start()

                assert adapter.is_running is True
                assert adapter.application == mock_telegram_application
                mock_logger.info.assert_called_with("Telegram bot started and polling for messages")

    @pytest.mark.asyncio
    async def test_start_validation_failure(self, test_config):
        """Test startup failure during validation"""
        config = {"bot_token": "invalid_token"}
        adapter = TelegramBotAdapter(config)

        # Mock validation failure
        with patch.object(adapter, 'validate_config', side_effect=ValueError("Invalid config")):
            with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
                with pytest.raises(RuntimeError, match="Telegram bot startup failed"):
                    await adapter.start()

                mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_stop_success(self, mock_telegram_application):
        """Test successful bot shutdown"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.application = mock_telegram_application
        adapter.is_running = True

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            await adapter.stop()

            assert adapter.is_running is False
            mock_logger.info.assert_called_with("Telegram bot stopped successfully")

    @pytest.mark.asyncio
    async def test_stop_no_application(self):
        """Test shutdown when no application exists"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        # Should not raise error
        await adapter.stop()
        assert adapter.is_running is False


class TestTelegramBotAdapterMessaging:
    """Test message sending functionality"""

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_telegram_application, outgoing_message):
        """Test successful message sending"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.application = mock_telegram_application

        result = await adapter.send_message(outgoing_message)

        assert result is True
        mock_telegram_application.bot.send_message.assert_called_once_with(
            chat_id="chat_123",
            text="Hi! I'd love to learn about crypto investing. What are you interested in?",
            reply_to_message_id="12345",
            **{"parse_mode": "markdown"}
        )

    @pytest.mark.asyncio
    async def test_send_message_no_application(self, outgoing_message):
        """Test message sending without initialized application"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            result = await adapter.send_message(outgoing_message)

            assert result is False
            mock_logger.error.assert_called_with("Telegram application not initialized")

    @pytest.mark.asyncio
    async def test_send_message_failure(self, mock_telegram_application, outgoing_message):
        """Test message sending failure"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.application = mock_telegram_application

        # Mock API failure
        mock_telegram_application.bot.send_message.side_effect = Exception("API Error")

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            result = await adapter.send_message(outgoing_message)

            assert result is False
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_send_typing_action_success(self, mock_telegram_application):
        """Test successful typing action sending"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.application = mock_telegram_application

        result = await adapter.send_typing_action("chat_123")

        assert result is True
        mock_telegram_application.bot.send_chat_action.assert_called_once_with(
            chat_id="chat_123",
            action=ChatAction.TYPING
        )

    @pytest.mark.asyncio
    async def test_send_typing_action_failure(self, mock_telegram_application):
        """Test typing action failure"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.application = mock_telegram_application

        mock_telegram_application.bot.send_chat_action.side_effect = Exception("API Error")

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            result = await adapter.send_typing_action("chat_123")

            assert result is False
            mock_logger.error.assert_called()


class TestTelegramBotAdapterMessageHandling:
    """Test message handling functionality"""

    def test_register_message_handler(self):
        """Test message handler registration"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        async def dummy_handler(message):
            pass

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            adapter.register_message_handler(dummy_handler)

            assert adapter.message_handler_callback == dummy_handler
            mock_logger.info.assert_called_with("Registered message handler callback")

    @pytest.mark.asyncio
    async def test_handle_telegram_message_success(self, mock_telegram_update):
        """Test successful Telegram message handling"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        async def dummy_handler(message):
            assert isinstance(message, IncomingMessage)
            assert message.platform == "telegram"
            assert message.sender_id == "67890"
            assert message.content == "Hello! Want to invest in crypto?"

        adapter.message_handler_callback = dummy_handler

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            await adapter._handle_telegram_message(mock_telegram_update, None)

            mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_telegram_message_no_callback(self, mock_telegram_update):
        """Test message handling without registered callback"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            await adapter._handle_telegram_message(mock_telegram_update, None)

            mock_logger.warning.assert_called_with("No message handler registered, ignoring message")

    @pytest.mark.asyncio
    async def test_handle_telegram_message_no_text(self):
        """Test handling message without text content"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        # Mock update with no text
        update = MagicMock()
        update.message.text = None

        # Should return early without error
        await adapter._handle_telegram_message(update, None)

    @pytest.mark.asyncio
    async def test_handle_telegram_message_processing_error(self, mock_telegram_update):
        """Test message handling with processing error"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        async def failing_handler(message):
            raise Exception("Handler error")

        adapter.message_handler_callback = failing_handler

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            await adapter._handle_telegram_message(mock_telegram_update, None)

            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_handle_start_command_success(self, mock_telegram_application):
        """Test successful /start command handling"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.application = mock_telegram_application

        update = MagicMock()
        update.message.chat_id = 11111

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            await adapter._handle_start_command(update, None)

            mock_telegram_application.bot.send_message.assert_called_once()
            call_args = mock_telegram_application.bot.send_message.call_args
            assert call_args[1]["chat_id"] == 11111
            assert "interested in learning about cryptocurrency investing" in call_args[1]["text"]
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_handle_start_command_no_message(self, mock_telegram_application):
        """Test /start command with no message"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.application = mock_telegram_application

        update = MagicMock()
        update.message = None

        # Should return early without error
        await adapter._handle_start_command(update, None)


class TestTelegramBotAdapterMessageNormalization:
    """Test message normalization"""

    def test_normalize_incoming_message_complete(self, mock_telegram_update):
        """Test normalizing complete Telegram message"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        message = adapter.normalize_incoming_message(mock_telegram_update)

        assert isinstance(message, IncomingMessage)
        assert message.message_id == "12345"
        assert message.sender_id == "67890"
        assert message.content == "Hello! Want to invest in crypto?"
        assert message.platform == "telegram"
        assert message.chat_id == "11111"
        assert message.metadata["username"] == "crypto_scammer"
        assert message.metadata["first_name"] == "John"
        assert message.metadata["language_code"] == "en"
        assert message.metadata["is_bot"] is False

    def test_normalize_incoming_message_minimal(self):
        """Test normalizing minimal Telegram message"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        # Create minimal update
        update = MagicMock()
        update.message.message_id = 999
        update.message.from_user.id = 888
        update.message.text = "Hi"
        update.message.chat_id = 777
        update.message.from_user.username = None
        update.message.from_user.first_name = None
        update.message.from_user.last_name = None
        update.message.from_user.language_code = None
        update.message.from_user.is_bot = True

        message = adapter.normalize_incoming_message(update)

        assert message.message_id == "999"
        assert message.sender_id == "888"
        assert message.content == "Hi"
        assert message.chat_id == "777"
        assert message.metadata["username"] is None
        assert message.metadata["is_bot"] is True


class TestTelegramBotAdapterPlatformInfo:
    """Test platform information methods"""

    def test_get_platform_info(self):
        """Test getting platform information"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        info = adapter.get_platform_info()

        assert info["platform"] == "telegram"
        assert info["version"] == "v20.0+"
        assert "text_messages" in info["capabilities"]
        assert "typing_indicator" in info["capabilities"]
        assert "running" in info

    def test_get_platform_info_running_status(self):
        """Test platform info reflects running status"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        # Initially not running
        info = adapter.get_platform_info()
        assert info["running"] is False

        # After starting
        adapter.is_running = True
        info = adapter.get_platform_info()
        assert info["running"] is True

    def test_get_required_config_fields(self):
        """Test getting required config fields"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        fields = adapter.get_required_config_fields()

        assert fields == ["bot_token"]


class TestTelegramBotAdapterHealthCheck:
    """Test health check functionality"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_telegram_application):
        """Test successful health check"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.application = mock_telegram_application
        adapter.is_running = True

        result = await adapter.health_check()

        assert result is True
        mock_telegram_application.bot.get_me.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_not_running(self):
        """Test health check when bot is not running"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.is_running = False

        with patch("src.scaipot.bots.base_adapter.logger") as mock_logger:
            result = await adapter.health_check()

            assert result is False
            mock_logger.warning.assert_called_with("telegram adapter is not running")

    @pytest.mark.asyncio
    async def test_health_check_no_application(self, mock_telegram_application):
        """Test health check without initialized application"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.is_running = True
        # No application set

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            result = await adapter.health_check()

            assert result is False
            mock_logger.warning.assert_called_with("Telegram application not initialized")

    @pytest.mark.asyncio
    async def test_health_check_api_failure(self, mock_telegram_application):
        """Test health check when API call fails"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.application = mock_telegram_application
        adapter.is_running = True

        mock_telegram_application.bot.get_me.side_effect = Exception("API Error")

        with patch("src.scaipot.bots.telegram_adapter.logger") as mock_logger:
            result = await adapter.health_check()

            assert result is False
            mock_logger.error.assert_called()


class TestTelegramBotAdapterHandlers:
    """Test handler registration"""

    def test_register_handlers(self, mock_telegram_application):
        """Test registering Telegram handlers"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)
        adapter.application = mock_telegram_application

        adapter._register_handlers()

        # Verify handlers were added
        assert mock_telegram_application.add_handler.call_count == 2

        # Check first handler (text messages)
        text_handler_call = mock_telegram_application.add_handler.call_args_list[0]
        text_handler = text_handler_call[0][0]

        # Check second handler (/start command)
        command_handler_call = mock_telegram_application.add_handler.call_args_list[1]
        command_handler = command_handler_call[0][0]

    def test_register_handlers_no_application(self):
        """Test handler registration without application"""
        config = {"bot_token": "test_token"}
        adapter = TelegramBotAdapter(config)

        with pytest.raises(RuntimeError, match="Application not initialized"):
            adapter._register_handlers()