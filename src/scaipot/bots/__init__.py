"""
Bot adapters for messaging platforms

This module provides bot adapters for Telegram, Signal, and WhatsApp,
allowing SCAIPOT to interact with scammers across multiple platforms.
"""

from .base_adapter import BaseBotAdapter, IncomingMessage, OutgoingMessage
from .signal_adapter import SignalBotAdapter
from .telegram_adapter import TelegramBotAdapter

__all__ = [
    "BaseBotAdapter",
    "IncomingMessage",
    "OutgoingMessage",
    "TelegramBotAdapter",
    "SignalBotAdapter",
]
