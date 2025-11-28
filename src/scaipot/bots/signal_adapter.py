"""
Signal bot adapter for scammer honeypot interactions
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

try:
    from signalbot import Command, Context, Message, SignalBot, triggered
    SIGNALBOT_AVAILABLE = True
except ImportError:
    SIGNALBOT_AVAILABLE = False
    SignalBot = None
    Command = None
    Context = None
    Message = None
    triggered = None

from .base_adapter import BaseBotAdapter, IncomingMessage, OutgoingMessage

logger = logging.getLogger(__name__)


class SignalMessageCommand:
    """Internal command to route all Signal messages to adapter callback"""

    def __init__(self, adapter):
        """
        Initialize command with adapter reference

        Args:
            adapter: SignalBotAdapter instance
        """
        if Command is not None:
            self.__class__ = type(
                'SignalMessageCommand',
                (Command,),
                dict(self.__class__.__dict__)
            )
        self.adapter = adapter

    def handle(self, c):
        """
        Handle incoming Signal message

        Args:
            c: Signal Context object
        """
        async def _async_handle():
            try:
                if self.adapter.message_handler_callback:
                    incoming = self.adapter.normalize_incoming_message(c.message)
                    await self.adapter.message_handler_callback(incoming)
            except Exception as e:
                logger.error(f"Error handling Signal message: {e}", exc_info=True)

        # Schedule async handling
        asyncio.create_task(_async_handle())


# Apply decorator if available
if triggered is not None:
    SignalMessageCommand.handle = triggered("")(SignalMessageCommand.handle)


class SignalBotAdapter(BaseBotAdapter):
    """
    Signal bot adapter for scammer honeypot interactions

    Integrates with signal-cli-rest-api via signalbot library
    to enable Signal messaging platform support.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Signal bot adapter

        Args:
            config: Configuration dictionary with:
                - phone_number: Bot's Signal phone number (e.g., "+1234567890")
                - signal_service: signal-cli-rest-api URL (default: "127.0.0.1:8080")
                - storage_path: Optional path for Signal data storage
        """
        super().__init__(platform_name="signal", config=config)

        if not SIGNALBOT_AVAILABLE:
            raise ImportError(
                "signalbot library not available. "
                "Install with: pip install signalbot>=0.6.0"
            )

        self.phone_number = config.get("phone_number")
        self.signal_service = config.get("signal_service", "127.0.0.1:8080")
        self.storage_path = config.get("storage_path")

        self.signal_bot: Optional[SignalBot] = None
        self.message_handler_callback: Optional[Callable] = None
        self._signal_command: Optional[SignalMessageCommand] = None
        self._bot_task: Optional[asyncio.Task] = None

        logger.info(
            f"Initialized Signal bot adapter for {self.phone_number} "
            f"(service: {self.signal_service})"
        )

    async def start(self) -> None:
        """
        Start the Signal bot and begin listening for messages

        Validates configuration, initializes SignalBot, registers
        message handlers, and starts the bot event loop in background.

        Raises:
            RuntimeError: If configuration invalid or startup fails
        """
        try:
            logger.info("Starting Signal bot adapter...")

            # Validate configuration
            if not await self.validate_config():
                raise RuntimeError("Signal bot configuration validation failed")

            # Initialize SignalBot
            bot_config = {
                "signal_service": self.signal_service,
                "phone_number": self.phone_number,
            }

            # Add storage configuration if provided
            if self.storage_path:
                bot_config["storage"] = {"path": self.storage_path}

            self.signal_bot = SignalBot(bot_config)
            logger.debug(f"SignalBot instance created for {self.phone_number}")

            # Register message command to route all messages to callback
            self._signal_command = SignalMessageCommand(self)
            self.signal_bot.register(self._signal_command)
            logger.debug("Registered Signal message handler")

            # Start bot in background task (non-blocking)
            # SignalBot.start() is blocking, so run in executor
            self._bot_task = asyncio.create_task(self._run_signal_bot())

            # Wait briefly for initialization
            await asyncio.sleep(2)

            self.is_running = True
            logger.info(
                f"✓ Signal bot started and listening on {self.phone_number}"
            )

        except Exception as e:
            logger.error(f"Failed to start Signal bot: {e}", exc_info=True)
            self.is_running = False
            raise RuntimeError(f"Signal bot startup failed: {e}")

    async def _run_signal_bot(self) -> None:
        """
        Run SignalBot event loop in background

        This method handles the blocking SignalBot.start() call by
        running it in a thread executor to prevent blocking the
        main asyncio event loop.
        """
        try:
            logger.debug("Starting Signal bot event loop...")

            # Run blocking start() in executor to avoid blocking asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.signal_bot.start)

        except asyncio.CancelledError:
            logger.info("Signal bot event loop cancelled")
        except Exception as e:
            logger.error(f"Signal bot event loop error: {e}", exc_info=True)
            self.is_running = False

    async def stop(self) -> None:
        """
        Stop the Signal bot gracefully

        Cancels the background task running the bot event loop
        and cleans up resources.
        """
        try:
            logger.info("Stopping Signal bot adapter...")

            if self._bot_task and not self._bot_task.done():
                self._bot_task.cancel()
                try:
                    await self._bot_task
                except asyncio.CancelledError:
                    logger.debug("Signal bot task cancelled successfully")

            self.is_running = False
            logger.info("✓ Signal bot stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping Signal bot: {e}", exc_info=True)

    async def send_message(self, message: OutgoingMessage) -> bool:
        """
        Send a message via Signal

        Args:
            message: Outgoing message containing chat_id and content

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            if not self.signal_bot:
                logger.error("Signal bot not initialized, cannot send message")
                return False

            if not self.is_running:
                logger.warning("Signal bot not running, message may fail")

            # Send the message via SignalBot
            # Returns timestamp of sent message
            timestamp = await self.signal_bot.send(
                receiver=message.chat_id,
                text=message.content,
            )

            logger.info(
                f"Sent Signal message (timestamp: {timestamp}) to {message.chat_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to send Signal message to {message.chat_id}: {e}",
                exc_info=True,
            )
            return False

    async def send_typing_action(self, chat_id: str) -> bool:
        """
        Send 'typing...' indicator to chat

        Args:
            chat_id: Chat/phone number to send typing indicator to

        Returns:
            True if typing indicator sent successfully
        """
        try:
            if not self.signal_bot:
                logger.error("Signal bot not initialized, cannot send typing action")
                return False

            # Send typing indicator
            await self.signal_bot.start_typing(chat_id)

            logger.debug(f"Sent typing action to Signal chat {chat_id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to send typing action to {chat_id}: {e}",
                exc_info=True,
            )
            return False

    def register_message_handler(self, handler: Callable) -> None:
        """
        Register callback function for processing incoming messages

        The handler will be called with IncomingMessage when
        messages are received from Signal.

        Args:
            handler: Async callable that accepts IncomingMessage
        """
        self.message_handler_callback = handler
        logger.info("Registered message handler callback for Signal adapter")

    def normalize_incoming_message(self, message: Any) -> IncomingMessage:
        """
        Convert Signal Message to standardized IncomingMessage format

        Args:
            message: Signal Message object from signalbot

        Returns:
            Normalized IncomingMessage instance
        """
        try:
            # Signal uses phone numbers as sender IDs
            sender_id = message.source

            # Signal uses millisecond timestamps
            timestamp_ms = message.timestamp
            timestamp_iso = datetime.fromtimestamp(
                timestamp_ms / 1000
            ).isoformat()

            # Message ID is timestamp (Signal doesn't have native message IDs)
            message_id = str(timestamp_ms)

            # Chat ID is recipient (phone number or group ID)
            chat_id = message.recipient()

            # Extract text content
            content = message.text if message.text else ""

            # Build metadata
            metadata = {
                "type": message.type.name if hasattr(message.type, "name") else str(message.type),
                "timestamp_ms": timestamp_ms,
            }

            # Add group info if present
            if message.group:
                metadata["group"] = message.group

            # Add reaction if present
            if message.reaction:
                metadata["reaction"] = message.reaction

            # Add attachment info if present
            if message.base64_attachments:
                metadata["has_attachments"] = True
                metadata["attachment_count"] = len(message.base64_attachments)

            return IncomingMessage(
                message_id=message_id,
                sender_id=sender_id,
                content=content,
                platform="signal",
                timestamp=timestamp_iso,
                chat_id=chat_id,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(
                f"Error normalizing Signal message: {e}",
                exc_info=True,
            )
            # Return minimal message on error
            return IncomingMessage(
                message_id="error",
                sender_id="unknown",
                content="",
                platform="signal",
                timestamp=datetime.utcnow().isoformat(),
                chat_id="unknown",
                metadata={"error": str(e)},
            )

    def get_platform_info(self) -> Dict[str, Any]:
        """
        Get Signal platform information and capabilities

        Returns:
            Dictionary with platform metadata
        """
        return {
            "platform": "signal",
            "adapter_version": "1.0.0",
            "signalbot_version": "0.6.0",
            "phone_number": self.phone_number,
            "signal_service": self.signal_service,
            "capabilities": [
                "text_messages",
                "typing_indicator",
                "reactions",
                "file_attachments",
                "group_chats",
            ],
            "running": self.is_running,
            "message_handler_registered": self.message_handler_callback is not None,
        }

    def get_required_config_fields(self) -> List[str]:
        """
        Get list of required configuration fields

        Returns:
            List of required config field names
        """
        return ["phone_number", "signal_service"]

    async def health_check(self) -> bool:
        """
        Check if Signal bot adapter is healthy

        Verifies:
        - Base adapter health (configuration, running state)
        - SignalBot instance initialized
        - Background task running

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check base health
            base_healthy = await super().health_check()
            if not base_healthy:
                logger.warning("Signal adapter base health check failed")
                return False

            # Check SignalBot initialized
            if not self.signal_bot:
                logger.warning("Signal bot not initialized")
                return False

            # Check background task running
            if self._bot_task and self._bot_task.done():
                logger.warning("Signal bot background task terminated unexpectedly")
                return False

            # TODO: Add actual health check to signal-cli-rest-api
            # Could use httpx to ping the health endpoint

            logger.debug("Signal adapter health check: OK")
            return True

        except Exception as e:
            logger.error(f"Signal health check failed: {e}", exc_info=True)
            return False
