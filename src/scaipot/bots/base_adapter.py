"""
Base adapter interface for messaging platform bots
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class IncomingMessage:
    """
    Standardized representation of an incoming message across platforms
    """

    message_id: str  # Platform-specific message ID
    sender_id: str  # Platform-specific user/sender ID
    content: str  # Message text content
    platform: str  # Platform name (telegram, signal, whatsapp)
    timestamp: str  # ISO format timestamp
    chat_id: str  # Platform-specific chat/conversation ID
    metadata: Dict[str, Any]  # Platform-specific metadata

    def __repr__(self) -> str:
        return (
            f"IncomingMessage(platform={self.platform}, "
            f"sender={self.sender_id}, "
            f"content={self.content[:50]}...)"
        )


@dataclass
class OutgoingMessage:
    """
    Standardized representation of an outgoing response message
    """

    chat_id: str  # Where to send the message
    content: str  # Message text content
    reply_to_message_id: Optional[str] = None  # Optional reply reference
    metadata: Dict[str, Any] = None  # Platform-specific options

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseBotAdapter(ABC):
    """
    Abstract base class for messaging platform bot adapters

    All platform adapters (Telegram, Signal, WhatsApp) must implement
    this interface to ensure consistent behavior across platforms.
    """

    def __init__(
        self,
        platform_name: str,
        config: Dict[str, Any],
    ):
        """
        Initialize bot adapter

        Args:
            platform_name: Name of the platform (telegram, signal, etc.)
            config: Platform-specific configuration dictionary
        """
        self.platform_name = platform_name
        self.config = config
        self.is_running = False

        logger.info(f"Initialized {platform_name} bot adapter")

    @abstractmethod
    async def start(self) -> None:
        """
        Start the bot and begin listening for messages

        Raises:
            RuntimeError: If bot fails to start
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the bot gracefully
        """
        pass

    @abstractmethod
    async def send_message(self, message: OutgoingMessage) -> bool:
        """
        Send a message to a chat/user

        Args:
            message: OutgoingMessage instance

        Returns:
            True if message sent successfully

        Raises:
            Exception: If sending fails
        """
        pass

    @abstractmethod
    async def send_typing_action(self, chat_id: str) -> bool:
        """
        Send "typing..." indicator to make bot seem more human

        Args:
            chat_id: Target chat identifier

        Returns:
            True if action sent successfully
        """
        pass

    @abstractmethod
    def register_message_handler(self, handler) -> None:
        """
        Register a callback function to handle incoming messages

        Args:
            handler: Async function that processes IncomingMessage
                    Signature: async def handler(message: IncomingMessage) -> None
        """
        pass

    @abstractmethod
    def get_platform_info(self) -> Dict[str, Any]:
        """
        Get information about the platform and bot configuration

        Returns:
            Dictionary with platform details (name, version, capabilities)
        """
        pass

    async def validate_config(self) -> bool:
        """
        Validate that required configuration parameters are present

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        required_fields = self.get_required_config_fields()

        missing_fields = [
            field for field in required_fields if field not in self.config
        ]

        if missing_fields:
            raise ValueError(
                f"{self.platform_name} adapter missing required config fields: "
                f"{', '.join(missing_fields)}"
            )

        logger.info(f"{self.platform_name} configuration validated successfully")
        return True

    @abstractmethod
    def get_required_config_fields(self) -> List[str]:
        """
        Return list of required configuration field names

        Returns:
            List of required config keys
        """
        pass

    def normalize_incoming_message(
        self, platform_message: Any
    ) -> IncomingMessage:
        """
        Convert platform-specific message object to standardized IncomingMessage

        Args:
            platform_message: Platform-specific message object

        Returns:
            Standardized IncomingMessage instance

        Note:
            Subclasses should override this method if needed
        """
        raise NotImplementedError(
            f"{self.platform_name} adapter must implement normalize_incoming_message()"
        )

    async def health_check(self) -> bool:
        """
        Check if the bot adapter is healthy and operational

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Basic health check - verify bot is running
            if not self.is_running:
                logger.warning(f"{self.platform_name} adapter is not running")
                return False

            # Subclasses can add platform-specific health checks
            return True

        except Exception as e:
            logger.error(f"{self.platform_name} health check failed: {e}")
            return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(platform={self.platform_name}, running={self.is_running})"
