"""
Unit tests for ClaudeClient class
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from anthropic.types import Message

from scaipot.llm_engine.claude_client import ClaudeClient


class TestClaudeClientInit:
    """Test ClaudeClient initialization"""

    def test_init_default_values(self):
        """Test initialization with default values"""
        client = ClaudeClient("test_api_key")

        assert client.api_key == "test_api_key"
        assert client.model == "claude-3-5-sonnet-20241022"
        assert client.max_tokens == 2048
        assert client.temperature == 1.0

    def test_init_custom_values(self):
        """Test initialization with custom values"""
        client = ClaudeClient(
            api_key="test_key",
            model="claude-3-haiku-20240307",
            max_tokens=1024,
            temperature=0.5
        )

        assert client.api_key == "test_key"
        assert client.model == "claude-3-haiku-20240307"
        assert client.max_tokens == 1024
        assert client.temperature == 0.5

    def test_init_creates_clients(self):
        """Test that both sync and async clients are created"""
        client = ClaudeClient("test_key")

        assert hasattr(client, 'client')
        assert hasattr(client, 'async_client')


class TestClaudeClientGenerateResponse:
    """Test synchronous response generation"""

    def test_generate_response_success(self, mock_claude_client, mock_anthropic_response):
        """Test successful synchronous response generation"""
        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "Hello!"}]

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            response = mock_claude_client.generate_response(system_prompt, messages)

            assert response == "Hello! I'm interested in crypto investments."
            mock_logger.debug.assert_called()

        # Verify API was called correctly
        mock_claude_client.client.messages.create.assert_called_once()
        call_args = mock_claude_client.client.messages.create.call_args
        assert call_args[1]["model"] == "claude-3-5-sonnet-20241022"
        assert call_args[1]["max_tokens"] == 1024
        assert call_args[1]["temperature"] == 0.7
        assert "system" in call_args[1]
        assert call_args[1]["messages"] == messages

    def test_generate_response_with_cache_enabled(self, mock_claude_client):
        """Test response generation with caching enabled"""
        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "Hello!"}]

        mock_claude_client.generate_response(system_prompt, messages, use_cache=True)

        # Verify system blocks include cache control
        call_args = mock_claude_client.client.messages.create.call_args
        system_blocks = call_args[1]["system"]
        assert len(system_blocks) == 1
        assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}

    def test_generate_response_with_cache_disabled(self, mock_claude_client):
        """Test response generation with caching disabled"""
        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "Hello!"}]

        mock_claude_client.generate_response(system_prompt, messages, use_cache=False)

        # Verify system blocks do not include cache control
        call_args = mock_claude_client.client.messages.create.call_args
        system_blocks = call_args[1]["system"]
        assert len(system_blocks) == 1
        assert "cache_control" not in system_blocks[0]

    def test_generate_response_failure(self, mock_claude_client):
        """Test response generation failure"""
        mock_claude_client.client.messages.create.side_effect = Exception("API Error")

        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "Hello!"}]

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            with pytest.raises(Exception, match="API Error"):
                mock_claude_client.generate_response(system_prompt, messages)

            mock_logger.error.assert_called()


class TestClaudeClientGenerateResponseAsync:
    """Test asynchronous response generation"""

    @pytest.mark.asyncio
    async def test_generate_response_async_success(self, mock_claude_client, mock_anthropic_response):
        """Test successful asynchronous response generation"""
        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "Hello!"}]

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            response = await mock_claude_client.generate_response_async(system_prompt, messages)

            assert response == "Hello! I'm interested in crypto investments."
            mock_logger.debug.assert_called()

        # Verify async API was called correctly
        mock_claude_client.async_client.messages.create.assert_called_once()
        call_args = mock_claude_client.async_client.messages.create.call_args
        assert call_args[1]["model"] == "claude-3-5-sonnet-20241022"
        assert call_args[1]["max_tokens"] == 1024
        assert call_args[1]["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_generate_response_async_with_cache(self, mock_claude_client):
        """Test async response generation with caching"""
        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "Hello!"}]

        await mock_claude_client.generate_response_async(system_prompt, messages, use_cache=True)

        # Verify cache control in system blocks
        call_args = mock_claude_client.async_client.messages.create.call_args
        system_blocks = call_args[1]["system"]
        assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}

    @pytest.mark.asyncio
    async def test_generate_response_async_failure(self, mock_claude_client):
        """Test async response generation failure"""
        mock_claude_client.async_client.messages.create.side_effect = Exception("Async API Error")

        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "Hello!"}]

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            with pytest.raises(Exception, match="Async API Error"):
                await mock_claude_client.generate_response_async(system_prompt, messages)

            mock_logger.error.assert_called()


class TestClaudeClientGenerateResponseStream:
    """Test streaming response generation"""

    @pytest.mark.asyncio
    async def test_generate_response_stream_success(self, mock_claude_client):
        """Test successful streaming response generation"""
        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "Hello!"}]

        # Mock stream object
        mock_stream = AsyncMock()
        mock_stream.text_stream = [
            "Hello! ",
            "I'm interested ",
            "in crypto investments."
        ]
        mock_stream.get_final_message.return_value = MagicMock(usage=MagicMock(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0
        ))

        mock_claude_client.async_client.messages.stream.return_value.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_claude_client.async_client.messages.stream.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            chunks = []
            async for chunk in mock_claude_client.generate_response_stream(system_prompt, messages):
                chunks.append(chunk)

            assert chunks == ["Hello! ", "I'm interested ", "in crypto investments."]
            mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_response_stream_with_cache(self, mock_claude_client):
        """Test streaming with cache control"""
        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "Hello!"}]

        mock_stream = AsyncMock()
        mock_stream.text_stream = ["Response"]
        mock_stream.get_final_message.return_value = MagicMock(usage=None)

        mock_claude_client.async_client.messages.stream.return_value.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_claude_client.async_client.messages.stream.return_value.__aexit__ = AsyncMock(return_value=None)

        async for _ in mock_claude_client.generate_response_stream(system_prompt, messages, use_cache=True):
            break  # Just consume one chunk

        # Verify cache control was set
        call_args = mock_claude_client.async_client.messages.stream.call_args
        system_blocks = call_args[1]["system"]
        assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}

    @pytest.mark.asyncio
    async def test_generate_response_stream_failure(self, mock_claude_client):
        """Test streaming response failure"""
        mock_claude_client.async_client.messages.stream.side_effect = Exception("Stream Error")

        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "Hello!"}]

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            with pytest.raises(Exception, match="Stream Error"):
                async for _ in mock_claude_client.generate_response_stream(system_prompt, messages):
                    pass

            mock_logger.error.assert_called()


class TestClaudeClientHelperMethods:
    """Test helper methods"""

    def test_prepare_system_blocks_with_cache(self, mock_claude_client):
        """Test system block preparation with cache control"""
        system_prompt = "You are a helpful assistant."

        blocks = mock_claude_client._prepare_system_blocks(system_prompt, use_cache=True)

        assert len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert blocks[0]["text"] == system_prompt
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}

    def test_prepare_system_blocks_without_cache(self, mock_claude_client):
        """Test system block preparation without cache control"""
        system_prompt = "You are a helpful assistant."

        blocks = mock_claude_client._prepare_system_blocks(system_prompt, use_cache=False)

        assert len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert blocks[0]["text"] == system_prompt
        assert "cache_control" not in blocks[0]

    def test_extract_response_text_single_block(self, mock_claude_client):
        """Test text extraction from single content block"""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text="Hello world!")
        ]

        result = mock_claude_client._extract_response_text(mock_response)
        assert result == "Hello world!"

    def test_extract_response_text_multiple_blocks(self, mock_claude_client):
        """Test text extraction from multiple content blocks"""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text="Hello "),
            MagicMock(type="text", text="world!"),
            MagicMock(type="text", text=" How are you?")
        ]

        result = mock_claude_client._extract_response_text(mock_response)
        assert result == "Hello world! How are you?"

    def test_extract_response_text_no_content(self, mock_claude_client):
        """Test text extraction when no content"""
        mock_response = MagicMock()
        mock_response.content = None

        result = mock_claude_client._extract_response_text(mock_response)
        assert result == ""

    def test_extract_response_text_empty_content(self, mock_claude_client):
        """Test text extraction with empty content list"""
        mock_response = MagicMock()
        mock_response.content = []

        result = mock_claude_client._extract_response_text(mock_response)
        assert result == ""

    def test_extract_response_text_non_text_blocks(self, mock_claude_client):
        """Test text extraction with non-text blocks"""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="image", text="ignored"),
            MagicMock(type="text", text="Hello!"),
            MagicMock(type="tool_use", text="ignored")
        ]

        result = mock_claude_client._extract_response_text(mock_response)
        assert result == "Hello!"

    def test_log_cache_usage_with_cache_data(self, mock_claude_client):
        """Test cache usage logging with cache statistics"""
        usage = MagicMock()
        usage.cache_read_input_tokens = 100
        usage.cache_creation_input_tokens = 50
        usage.input_tokens = 20
        usage.output_tokens = 15

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            mock_claude_client._log_cache_usage(usage)

            mock_logger.info.assert_called_once()
            log_call = mock_logger.info.call_args[0][0]
            assert "Cache usage" in log_call
            assert "Read: 100" in log_call
            assert "Creation: 50" in log_call
            assert "Hit rate: 83.3%" in log_call

    def test_log_cache_usage_without_cache_data(self, mock_claude_client):
        """Test cache usage logging without cache statistics"""
        usage = MagicMock()
        # Simulate no cache attributes
        del usage.cache_read_input_tokens

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            mock_claude_client._log_cache_usage(usage)

            mock_logger.debug.assert_called_once()
            log_call = mock_logger.debug.call_args[0][0]
            assert "Token usage" in log_call

    def test_log_cache_usage_none_usage(self, mock_claude_client):
        """Test cache usage logging with None usage"""
        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            mock_claude_client._log_cache_usage(None)

            # Should not log anything
            mock_logger.info.assert_not_called()
            mock_logger.debug.assert_not_called()


class TestClaudeClientFormatMessages:
    """Test message formatting"""

    def test_format_conversation_messages_valid(self, mock_claude_client):
        """Test formatting valid conversation messages"""
        conversation = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]

        result = mock_claude_client.format_conversation_messages(conversation)

        assert len(result) == 3
        assert result[0] == {"role": "user", "content": "Hello!"}
        assert result[1] == {"role": "assistant", "content": "Hi there!"}
        assert result[2] == {"role": "user", "content": "How are you?"}

    def test_format_conversation_messages_invalid_role(self, mock_claude_client):
        """Test formatting with invalid role defaults to user"""
        conversation = [
            {"role": "invalid_role", "content": "Hello!"}
        ]

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            result = mock_claude_client.format_conversation_messages(conversation)

            assert result[0]["role"] == "user"  # Should default to user
            assert result[0]["content"] == "Hello!"
            mock_logger.warning.assert_called_with("Invalid role 'invalid_role', defaulting to 'user'")

    def test_format_conversation_messages_missing_role(self, mock_claude_client):
        """Test formatting with missing role defaults to user"""
        conversation = [
            {"content": "Hello!"}  # Missing role
        ]

        result = mock_claude_client.format_conversation_messages(conversation)

        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello!"

    def test_format_conversation_messages_empty_conversation(self, mock_claude_client):
        """Test formatting empty conversation"""
        result = mock_claude_client.format_conversation_messages([])
        assert result == []


class TestClaudeClientTestConnection:
    """Test connection testing"""

    @pytest.mark.asyncio
    async def test_test_connection_success(self, mock_claude_client):
        """Test successful connection test"""
        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            result = await mock_claude_client.test_connection()

            assert result is True
            mock_logger.info.assert_called_with("Claude API connection test successful")

        # Verify the API was called
        mock_claude_client.generate_response_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_failure_empty_response(self, mock_claude_client):
        """Test connection test failure with empty response"""
        mock_claude_client.generate_response_async.return_value = ""

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            result = await mock_claude_client.test_connection()

            assert result is False
            mock_logger.error.assert_called_with("Claude API returned empty response")

    @pytest.mark.asyncio
    async def test_test_connection_api_failure(self, mock_claude_client):
        """Test connection test failure with API error"""
        mock_claude_client.generate_response_async.side_effect = Exception("Connection failed")

        with patch("src.scaipot.llm_engine.claude_client.logger") as mock_logger:
            result = await mock_claude_client.test_connection()

            assert result is False
            mock_logger.error.assert_called_with("Claude API connection test failed: Connection failed")