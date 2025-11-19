"""
Unit tests for ResponseGenerator class
"""
import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scaipot.llm_engine.claude_client import ClaudeClient
from src.scaipot.llm_engine.response_generator import ResponseGenerator
from src.scaipot.mcp_integration.mcp_client import MCPPromptsClient


class TestResponseGeneratorInit:
    """Test ResponseGenerator initialization"""

    def test_init_default_values(self, mock_claude_client):
        """Test initialization with default values"""
        mock_mcp_client = MagicMock(spec=MCPPromptsClient)

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        assert generator.claude == mock_claude_client
        assert generator.mcp == mock_mcp_client
        assert generator.use_cache is True
        assert generator._category_cache == {}

    def test_init_custom_values(self, mock_claude_client):
        """Test initialization with custom values"""
        mock_mcp_client = MagicMock(spec=MCPPromptsClient)

        generator = ResponseGenerator(
            claude_client=mock_claude_client,
            mcp_client=mock_mcp_client,
            use_cache=False
        )

        assert generator.use_cache is False


class TestResponseGeneratorGenerateResponse:
    """Test honeypot response generation"""

    @pytest.mark.asyncio
    async def test_generate_honeypot_response_success(self, mock_claude_client):
        """Test successful response generation"""
        # Setup mocks
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        category_config = {
            "system_prompt": "You are a crypto investor.",
            "persona": {"name": "John", "age": 25},
            "behavior_notes": "Be enthusiastic about crypto."
        }
        mock_mcp_client.get_category_prompt.return_value = category_config
        mock_claude_client.generate_response_async.return_value = "That sounds amazing! Tell me more."

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        response = await generator.generate_honeypot_response(
            category="bitcoin_investment",
            incoming_message="I can help you invest in Bitcoin!"
        )

        assert response == "That sounds amazing! Tell me more."
        mock_mcp_client.get_category_prompt.assert_called_once_with(
            category="bitcoin_investment", platform=None
        )
        mock_claude_client.generate_response_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_honeypot_response_with_history(self, mock_claude_client):
        """Test response generation with conversation history"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        category_config = {"system_prompt": "You are a crypto investor."}
        mock_mcp_client.get_category_prompt.return_value = category_config
        mock_claude_client.generate_response_async.return_value = "Interesting!"

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        conversation_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        await generator.generate_honeypot_response(
            category="bitcoin_investment",
            incoming_message="Want to invest?",
            conversation_history=conversation_history
        )

        # Verify conversation history was passed
        call_args = mock_claude_client.generate_response_async.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 3  # history + new message
        assert messages[0]["content"] == "Hello"
        assert messages[2]["content"] == "Want to invest?"

    @pytest.mark.asyncio
    async def test_generate_honeypot_response_with_platform(self, mock_claude_client):
        """Test response generation with platform specification"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        category_config = {"system_prompt": "You are a crypto investor."}
        mock_mcp_client.get_category_prompt.return_value = category_config
        mock_claude_client.generate_response_async.return_value = "Telegram response"

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        response = await generator.generate_honeypot_response(
            category="bitcoin_investment",
            incoming_message="Hello!",
            platform="telegram"
        )

        assert response == "Telegram response"
        mock_mcp_client.get_category_prompt.assert_called_once_with(
            category="bitcoin_investment", platform="telegram"
        )

    @pytest.mark.asyncio
    async def test_generate_honeypot_response_category_not_found(self, mock_claude_client):
        """Test response generation when category not found"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        mock_mcp_client.get_category_prompt.return_value = None

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        with patch("src.scaipot.llm_engine.response_generator.logger") as mock_logger:
            response = await generator.generate_honeypot_response(
                category="unknown_category",
                incoming_message="Hello!"
            )

            # Should return fallback response
            assert isinstance(response, str)
            assert len(response) > 0
            mock_logger.error.assert_called_with("Failed to load category: unknown_category")
            mock_claude_client.generate_response_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_honeypot_response_claude_failure(self, mock_claude_client):
        """Test response generation when Claude API fails"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        category_config = {"system_prompt": "You are a crypto investor."}
        mock_mcp_client.get_category_prompt.return_value = category_config
        mock_claude_client.generate_response_async.side_effect = Exception("API Error")

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        with patch("src.scaipot.llm_engine.response_generator.logger") as mock_logger:
            response = await generator.generate_honeypot_response(
                category="bitcoin_investment",
                incoming_message="Hello!"
            )

            # Should return fallback response
            assert isinstance(response, str)
            assert len(response) > 0
            mock_logger.error.assert_called()


class TestResponseGeneratorStreamingResponse:
    """Test streaming response generation"""

    @pytest.mark.asyncio
    async def test_generate_streaming_response_success(self, mock_claude_client):
        """Test successful streaming response generation"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        category_config = {"system_prompt": "You are a crypto investor."}
        mock_mcp_client.get_category_prompt.return_value = category_config

        # Mock streaming response
        async def mock_stream():
            yield "Hello! "
            yield "I'm interested "
            yield "in crypto."

        mock_claude_client.generate_response_stream = mock_stream

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        chunks = []
        async for chunk in generator.generate_streaming_response(
            category="bitcoin_investment",
            incoming_message="Want to invest?"
        ):
            chunks.append(chunk)

        assert chunks == ["Hello! ", "I'm interested ", "in crypto."]
        mock_mcp_client.get_category_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_streaming_response_category_not_found(self, mock_claude_client):
        """Test streaming response when category not found"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        mock_mcp_client.get_category_prompt.return_value = None

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        chunks = []
        async for chunk in generator.generate_streaming_response(
            category="unknown_category",
            incoming_message="Hello!"
        ):
            chunks.append(chunk)

        # Should yield fallback response
        assert len(chunks) == 1
        assert isinstance(chunks[0], str)
        assert len(chunks[0]) > 0

    @pytest.mark.asyncio
    async def test_generate_streaming_response_claude_failure(self, mock_claude_client):
        """Test streaming response when Claude API fails"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        category_config = {"system_prompt": "You are a crypto investor."}
        mock_mcp_client.get_category_prompt.return_value = category_config

        # Mock streaming failure
        async def mock_stream():
            raise Exception("Streaming error")

        mock_claude_client.generate_response_stream = mock_stream

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        with patch("src.scaipot.llm_engine.response_generator.logger") as mock_logger:
            chunks = []
            async for chunk in generator.generate_streaming_response(
                category="bitcoin_investment",
                incoming_message="Hello!"
            ):
                chunks.append(chunk)

            # Should yield fallback response
            assert len(chunks) == 1
            assert isinstance(chunks[0], str)
            mock_logger.error.assert_called()


class TestResponseGeneratorCategoryConfig:
    """Test category configuration loading and caching"""

    @pytest.mark.asyncio
    async def test_get_category_config_from_cache(self, mock_claude_client):
        """Test getting category config from cache"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        # Pre-populate cache
        cache_key = "bitcoin_investment:default"
        cached_config = {"system_prompt": "Cached config"}
        generator._category_cache[cache_key] = cached_config

        config = await generator._get_category_config("bitcoin_investment", None)

        assert config == cached_config
        mock_mcp_client.get_category_prompt.assert_not_called()  # Should not call MCP

    @pytest.mark.asyncio
    async def test_get_category_config_from_mcp(self, mock_claude_client):
        """Test getting category config from MCP server"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        mcp_config = {"system_prompt": "From MCP server"}
        mock_mcp_client.get_category_prompt.return_value = mcp_config

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        config = await generator._get_category_config("bitcoin_investment", "telegram")

        assert config == mcp_config
        mock_mcp_client.get_category_prompt.assert_called_once_with(
            category="bitcoin_investment", platform="telegram"
        )

        # Verify caching
        cache_key = "bitcoin_investment:telegram"
        assert generator._category_cache[cache_key] == mcp_config

    @pytest.mark.asyncio
    async def test_get_category_config_mcp_failure(self, mock_claude_client):
        """Test category config loading failure"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        mock_mcp_client.get_category_prompt.side_effect = Exception("MCP Error")

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        with patch("src.scaipot.llm_engine.response_generator.logger") as mock_logger:
            config = await generator._get_category_config("bitcoin_investment", None)

            assert config is None
            mock_logger.error.assert_called()


class TestResponseGeneratorPromptBuilding:
    """Test system prompt building"""

    def test_build_system_prompt_minimal(self, mock_claude_client):
        """Test building minimal system prompt"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        category_config = {"system_prompt": "You are an investor."}

        prompt = generator._build_system_prompt(category_config)

        assert "You are an investor." in prompt
        assert "honeypot designed to waste scammer time" in prompt

    def test_build_system_prompt_with_persona(self, mock_claude_client):
        """Test building system prompt with persona"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        category_config = {
            "system_prompt": "You are interested in crypto.",
            "persona": {
                "name": "Alice",
                "age": 28,
                "background": "Recent graduate interested in investments."
            },
            "behavior_notes": "Ask lots of questions."
        }

        prompt = generator._build_system_prompt(category_config)

        assert "You are interested in crypto." in prompt
        assert "Your name is Alice." in prompt
        assert "You are 28 years old." in prompt
        assert "Recent graduate interested in investments." in prompt
        assert "Ask lots of questions." in prompt
        assert "honeypot designed to waste scammer time" in prompt

    def test_build_system_prompt_empty_config(self, mock_claude_client):
        """Test building system prompt with empty config"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        category_config = {}

        prompt = generator._build_system_prompt(category_config)

        # Should still contain honeypot instructions
        assert "honeypot designed to waste scammer time" in prompt

    def test_format_persona_description_complete(self, mock_claude_client):
        """Test formatting complete persona description"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        persona = {
            "name": "Bob",
            "age": 35,
            "background": "Experienced trader."
        }

        description = generator._format_persona_description(persona)

        assert "Your name is Bob." in description
        assert "You are 35 years old." in description
        assert "Experienced trader." in description

    def test_format_persona_description_partial(self, mock_claude_client):
        """Test formatting partial persona description"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        persona = {"name": "Charlie"}  # Only name

        description = generator._format_persona_description(persona)

        assert description == "Your name is Charlie."

    def test_format_persona_description_empty(self, mock_claude_client):
        """Test formatting empty persona description"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        persona = {}

        description = generator._format_persona_description(persona)

        assert description == ""


class TestResponseGeneratorConversationContext:
    """Test conversation context building"""

    def test_build_conversation_context_no_history(self, mock_claude_client):
        """Test building context without conversation history"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        messages = generator._build_conversation_context(
            incoming_message="Hello there!",
            conversation_history=None
        )

        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello there!"}

    def test_build_conversation_context_with_history(self, mock_claude_client):
        """Test building context with conversation history"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        conversation_history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"}
        ]

        messages = generator._build_conversation_context(
            incoming_message="How are you?",
            conversation_history=conversation_history
        )

        assert len(messages) == 3
        assert messages[0] == {"role": "user", "content": "Hi"}
        assert messages[1] == {"role": "assistant", "content": "Hello!"}
        assert messages[2] == {"role": "user", "content": "How are you?"}

    def test_build_conversation_context_empty_history(self, mock_claude_client):
        """Test building context with empty conversation history"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        messages = generator._build_conversation_context(
            incoming_message="Hello!",
            conversation_history=[]
        )

        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello!"}


class TestResponseGeneratorResponseFormatting:
    """Test response formatting"""

    def test_format_response_for_platform_basic(self, mock_claude_client):
        """Test basic response formatting"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        response = generator._format_response_for_platform(
            response="  Hello world!  ",
            platform="telegram",
            category_config={}
        )

        assert response == "Hello world!"  # Should strip whitespace

    def test_get_fallback_response_variety(self, mock_claude_client):
        """Test that fallback responses vary"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        # Get multiple fallback responses
        responses = set()
        for _ in range(10):
            response = generator._get_fallback_response()
            responses.add(response)

        # Should get some variety (at least 2-3 different responses)
        assert len(responses) >= 2

        # All responses should be strings and contain question marks
        for response in responses:
            assert isinstance(response, str)
            assert "?" in response


class TestResponseGeneratorListCategories:
    """Test category listing functionality"""

    @pytest.mark.asyncio
    async def test_list_available_categories_success(self, mock_claude_client):
        """Test successful category listing"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        categories = ["bitcoin_investment", "romance_scam", "tech_support"]
        mock_mcp_client.list_categories.return_value = categories

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        with patch("src.scaipot.llm_engine.response_generator.logger") as mock_logger:
            result = await generator.list_available_categories()

            assert result == categories
            mock_logger.info.assert_called_with("Found 3 available categories")

    @pytest.mark.asyncio
    async def test_list_available_categories_failure(self, mock_claude_client):
        """Test category listing failure"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        mock_mcp_client.list_categories.side_effect = Exception("MCP Error")

        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        with patch("src.scaipot.llm_engine.response_generator.logger") as mock_logger:
            result = await generator.list_available_categories()

            assert result == []
            mock_logger.error.assert_called()


class TestResponseGeneratorCacheManagement:
    """Test category cache management"""

    def test_clear_category_cache(self, mock_claude_client):
        """Test clearing category cache"""
        mock_mcp_client = AsyncMock(spec=MCPPromptsClient)
        generator = ResponseGenerator(mock_claude_client, mock_mcp_client)

        # Add some cached items
        generator._category_cache["test1"] = {"config": "1"}
        generator._category_cache["test2"] = {"config": "2"}

        with patch("src.scaipot.llm_engine.response_generator.logger") as mock_logger:
            generator.clear_category_cache()

            assert generator._category_cache == {}
            mock_logger.info.assert_called_with("Cleared category cache")