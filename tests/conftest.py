"""
Shared test fixtures and configuration for SCAIPOT tests
"""
import asyncio
import os
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from scaipot.bots.base_adapter import IncomingMessage, OutgoingMessage
from scaipot.llm_engine.claude_client import ClaudeClient
from scaipot.storage.session_manager import SessionManager

# Import modules to be tested
from scaipot.utils.config import load_config


# Test configuration fixtures
@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Valid test configuration dictionary"""
    return {
        "TELEGRAM_BOT_TOKEN": "test_telegram_token_12345",
        "SIGNAL_PHONE_NUMBER": "+1234567890",
        "SIGNAL_STORAGE_PATH": "/tmp/test_signal",
        "ANTHROPIC_API_KEY": "test_anthropic_key_12345",
        "CLAUDE_MODEL": "claude-3-5-sonnet-20241022",
        "MCP_PROMPTS_URL": "http://localhost:3003",
        "MCP_PROMPTS_API_KEY": "test_mcp_key",
        "DATABASE_URL": "postgresql://scaipot:testpass@localhost:5432/test_scaipot",
        "DATABASE_POOL_SIZE": "20",  # String for env vars
        "REDIS_URL": "redis://localhost:6379/1",  # Use DB 1 for testing
        "REDIS_PASSWORD": "",
        "ADMIN_SLACK_WEBHOOK": "https://hooks.slack.com/test",
        "ADMIN_DISCORD_WEBHOOK": "https://discord.com/api/webhooks/test",
        "ADMIN_EMAIL": "test@scaipot.dev",
        "HONEYPOT_VM_ENABLED": "false",  # String for env vars
        "HONEYPOT_NETWORK_ANALYSIS_ENABLED": "false",  # String for env vars
        "DOCKER_HOST": "unix:///var/run/docker.sock",
        "JWT_SECRET": "test_jwt_secret_very_secure_12345",
        "ALLOWED_ORIGINS": "http://localhost:3001,http://localhost:3000",  # Comma-separated string
        "LOG_LEVEL": "DEBUG",
        "LOG_FORMAT": "json",
        "SENTRY_DSN": "",
        "ENV": "test",
        "DEBUG": "true",  # String for env vars
    }


@pytest.fixture
def sample_conversation_data() -> List[Dict[str, str]]:
    """Sample conversation history for testing"""
    return [
        {"role": "user", "content": "Hello, I'm interested in crypto investing"},
        {"role": "assistant", "content": "Hi! That's great. What kind of investments are you looking for?"},
        {"role": "user", "content": "I want to invest in Bitcoin, can you help?"},
    ]


@pytest.fixture
def incoming_message() -> IncomingMessage:
    """Sample incoming message for testing"""
    return IncomingMessage(
        message_id="12345",
        sender_id="user_123",
        content="Hello, I'm interested in crypto investments",
        platform="telegram",
        timestamp="2024-01-15T10:30:00Z",
        chat_id="chat_123",
        metadata={
            "username": "crypto_newbie",
            "first_name": "John",
            "last_name": "Doe",
            "language_code": "en",
            "is_bot": False,
        },
    )


@pytest.fixture
def outgoing_message() -> OutgoingMessage:
    """Sample outgoing message for testing"""
    return OutgoingMessage(
        chat_id="chat_123",
        content="Hi! I'd love to learn about crypto investing. What are you interested in?",
        reply_to_message_id="12345",
        metadata={"parse_mode": "markdown"},
    )


# Redis fixtures
@pytest.fixture
async def redis_client() -> AsyncGenerator[redis.Redis, None]:
    """Redis client for testing - uses test database"""
    client = redis.Redis.from_url(
        "redis://localhost:6379/1",  # Use DB 1 for testing
        encoding="utf-8",
        decode_responses=True,
    )

    # Clear test database
    await client.flushdb()

    yield client

    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
async def session_manager(redis_client: redis.Redis) -> SessionManager:
    """SessionManager instance with test Redis client"""
    manager = SessionManager(
        redis_url="redis://localhost:6379/1",
        default_ttl=3600,  # Shorter TTL for testing
    )

    # Manually set the client for testing
    manager.redis_client = redis_client

    yield manager

    # Cleanup is handled by redis_client fixture


# Claude API mocks
@pytest.fixture
def mock_anthropic_response():
    """Mock Claude API response"""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Hello! I'm interested in crypto investments.")]
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 25
    mock_response.usage.cache_read_input_tokens = 0
    mock_response.usage.cache_creation_input_tokens = 0
    return mock_response


@pytest.fixture
def mock_claude_client(mock_anthropic_response) -> ClaudeClient:
    """Mocked ClaudeClient for testing"""
    client = ClaudeClient(
        api_key="test_key",
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        temperature=0.7,
    )

    # Mock the sync client
    client.client.messages.create = MagicMock(return_value=mock_anthropic_response)

    # Mock the async client
    client.async_client.messages.create = AsyncMock(return_value=mock_anthropic_response)

    # Mock streaming
    async def mock_stream():
        yield "Hello! I'm interested in crypto investments."

    mock_final_message = MagicMock()
    mock_final_message.usage = MagicMock()
    mock_final_message.usage.input_tokens = 50
    mock_final_message.usage.output_tokens = 25
    mock_final_message.usage.cache_read_input_tokens = 0
    mock_final_message.usage.cache_creation_input_tokens = 0

    # Ensure attributes are actual integers, not AsyncMock
    type(mock_final_message.usage).input_tokens = 50
    type(mock_final_message.usage).output_tokens = 25
    type(mock_final_message.usage).cache_read_input_tokens = 0
    type(mock_final_message.usage).cache_creation_input_tokens = 0

    client.async_client.messages.stream = MagicMock()
    client.async_client.messages.stream.return_value.__aenter__ = AsyncMock()
    client.async_client.messages.stream.return_value.__aexit__ = AsyncMock(return_value=None)
    client.async_client.messages.stream.return_value.text_stream = mock_stream()
    client.async_client.messages.stream.return_value.get_final_message = AsyncMock(return_value=mock_final_message)

    return client


# Telegram bot mocks
@pytest.fixture
def mock_telegram_update():
    """Mock Telegram Update object"""
    update = MagicMock()
    update.message.message_id = 12345
    update.message.from_user.id = 67890
    update.message.from_user.username = "crypto_scammer"
    update.message.from_user.first_name = "John"
    update.message.from_user.last_name = "Scammer"
    update.message.from_user.language_code = "en"
    update.message.from_user.is_bot = False
    update.message.text = "Hello! Want to invest in crypto?"
    update.message.chat_id = 11111
    return update


@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot for testing"""
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=True)
    bot.send_chat_action = AsyncMock(return_value=True)
    bot.get_me = AsyncMock(return_value=MagicMock(username="test_bot"))
    return bot


@pytest.fixture
def mock_telegram_application(mock_telegram_bot):
    """Mock Telegram Application for testing"""
    app = MagicMock()
    app.bot = mock_telegram_bot
    app.initialize = AsyncMock()
    app.start = AsyncMock()
    app.stop = AsyncMock()
    app.shutdown = AsyncMock()
    app.updater.start_polling = AsyncMock()
    app.updater.stop = AsyncMock()
    app.add_handler = MagicMock()
    return app


# Environment setup fixtures
@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment variables before each test"""
    # Store original environment
    original_env = dict(os.environ)

    # Clear test-related environment variables
    test_env_vars = [
        "TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY", "DATABASE_URL", "REDIS_URL",
        "MCP_PROMPTS_URL", "JWT_SECRET", "LOG_LEVEL", "ENV", "DEBUG"
    ]

    for var in test_env_vars:
        os.environ.pop(var, None)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def set_test_env(test_config):
    """Set environment variables for testing"""
    for key, value in test_config.items():
        if isinstance(value, list):
            os.environ[key] = ",".join(value)
        elif isinstance(value, bool):
            os.environ[key] = "true" if value else "false"
        else:
            os.environ[key] = str(value)


# PostgreSQL fixtures (for integration tests)
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def postgres_session():
    """PostgreSQL async session for integration testing"""
    # Use SQLite for unit tests to avoid requiring PostgreSQL
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables (would normally be done by SQLAlchemy models)
    async with engine.begin() as conn:
        # Create basic test tables
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                platform VARCHAR NOT NULL,
                message TEXT NOT NULL,
                role VARCHAR NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


# Utility fixtures
@pytest.fixture
def mock_logger():
    """Mock logger to avoid log output during tests"""
    logger = MagicMock()
    return logger