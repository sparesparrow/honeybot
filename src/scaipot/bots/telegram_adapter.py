"""
Telegram bot adapter implementation
"""
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ChatAction

from .base_adapter import BaseBotAdapter, IncomingMessage, OutgoingMessage

logger = logging.getLogger(__name__)


class TelegramBotAdapter(BaseBotAdapter):
    """
    Telegram bot adapter for scammer honeypot interactions
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Telegram bot adapter

        Args:
            config: Configuration dictionary with 'bot_token' key
        """
        super().__init__(platform_name="telegram", config=config)

        self.bot_token = config.get("bot_token")
        self.application: Optional[Application] = None
        self.message_handler_callback: Optional[Callable] = None

        logger.info("Initialized Telegram bot adapter")

    async def start(self) -> None:
        """
        Start the Telegram bot
        """
        try:
            # Validate configuration
            await self.validate_config()

            # Build application
            self.application = (
                ApplicationBuilder()
                .token(self.bot_token)
                .build()
            )

            # Register handlers
            self._register_handlers()

            # Start polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()

            self.is_running = True
            logger.info("Telegram bot started and polling for messages")

        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            raise RuntimeError(f"Telegram bot startup failed: {e}")

    async def stop(self) -> None:
        """
        Stop the Telegram bot gracefully
        """
        try:
            if self.application and self.is_running:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()

                self.is_running = False
                logger.info("Telegram bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")

    async def send_message(self, message: OutgoingMessage) -> bool:
        """
        Send a message via Telegram

        Args:
            message: OutgoingMessage instance

        Returns:
            True if message sent successfully
        """
        try:
            if not self.application:
                logger.error("Telegram application not initialized")
                return False

            # Send the message
            await self.application.bot.send_message(
                chat_id=message.chat_id,
                text=message.content,
                reply_to_message_id=message.reply_to_message_id,
                **message.metadata,
            )

            logger.debug(f"Sent Telegram message to chat {message.chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_typing_action(self, chat_id: str) -> bool:
        """
        Send "typing..." indicator

        Args:
            chat_id: Target chat ID

        Returns:
            True if action sent successfully
        """
        try:
            if not self.application:
                logger.error("Telegram application not initialized")
                return False

            await self.application.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING,
            )

            logger.debug(f"Sent typing action to chat {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send typing action: {e}")
            return False

    def register_message_handler(self, handler: Callable) -> None:
        """
        Register callback for processing incoming messages

        Args:
            handler: Async function with signature:
                    async def handler(message: IncomingMessage) -> None
        """
        self.message_handler_callback = handler
        logger.info("Registered message handler callback")

    def _register_handlers(self) -> None:
        """
        Register Telegram message and command handlers
        """
        if not self.application:
            raise RuntimeError("Application not initialized")

        # Handle all text messages
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_telegram_message,
            )
        )

        # Handle /start command
        self.application.add_handler(
            CommandHandler("start", self._handle_start_command)
        )

        logger.info("Registered Telegram handlers")

    async def _handle_telegram_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Internal handler for Telegram messages

        Args:
            update: Telegram update object
            context: Bot context
        """
        try:
            if not update.message or not update.message.text:
                return

            # Normalize to IncomingMessage
            incoming_msg = self.normalize_incoming_message(update)

            # Call registered callback if available
            if self.message_handler_callback:
                await self.message_handler_callback(incoming_msg)
            else:
                logger.warning("No message handler registered, ignoring message")

        except Exception as e:
            logger.error(f"Error handling Telegram message: {e}")

    async def _handle_start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /start command

        Args:
            update: Telegram update object
            context: Bot context
        """
        try:
            if not update.message:
                return

            chat_id = update.message.chat_id

            welcome_message = (
                "👋 Hello! I'm interested in learning about cryptocurrency investing. "
                "Do you have any tips?"
            )

            await self.application.bot.send_message(
                chat_id=chat_id,
                text=welcome_message,
            )

            logger.info(f"Sent welcome message to chat {chat_id}")

        except Exception as e:
            logger.error(f"Error handling /start command: {e}")

    def normalize_incoming_message(
        self, update: Update
    ) -> IncomingMessage:
        """
        Convert Telegram Update to standardized IncomingMessage

        Args:
            update: Telegram Update object

        Returns:
            IncomingMessage instance
        """
        message = update.message

        return IncomingMessage(
            message_id=str(message.message_id),
            sender_id=str(message.from_user.id),
            content=message.text or "",
            platform="telegram",
            timestamp=datetime.utcnow().isoformat(),
            chat_id=str(message.chat_id),
            metadata={
                "username": message.from_user.username,
                "first_name": message.from_user.first_name,
                "last_name": message.from_user.last_name,
                "language_code": message.from_user.language_code,
                "is_bot": message.from_user.is_bot,
            },
        )

    def get_platform_info(self) -> Dict[str, Any]:
        """
        Get Telegram platform information

        Returns:
            Platform details dictionary
        """
        return {
            "platform": "telegram",
            "version": "v20.0+",
            "capabilities": [
                "text_messages",
                "typing_indicator",
                "inline_keyboards",
                "file_uploads",
                "group_chats",
            ],
            "running": self.is_running,
        }

    def get_required_config_fields(self) -> List[str]:
        """
        Return required configuration fields

        Returns:
            List of required config keys
        """
        return ["bot_token"]

    async def health_check(self) -> bool:
        """
        Check if Telegram bot is healthy

        Returns:
            True if healthy
        """
        try:
            # Call parent health check
            base_healthy = await super().health_check()
            if not base_healthy:
                return False

            # Check if application is initialized
            if not self.application:
                logger.warning("Telegram application not initialized")
                return False

            # Try to get bot info
            bot_info = await self.application.bot.get_me()
            logger.debug(f"Telegram bot health check: {bot_info.username}")
            return True

        except Exception as e:
            logger.error(f"Telegram health check failed: {e}")
            return False
