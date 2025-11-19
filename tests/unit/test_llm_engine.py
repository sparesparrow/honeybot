"""
Unit tests for LLM Engine modules (Claude client and response generator)
"""
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.scaipot.llm_engine.claude_client import ClaudeClient
from src.scaipot.llm_engine.response_generator import ResponseGenerator


class TestClaudeClient:
    """Test ClaudeClient API wrapper functionality"""

    @pytest.fixture
    def sample_system_prompt(self) -> str:
        """Sample system prompt for testing"""
        return "You are a helpful crypto investment assistant."

    @pytest.fixture
    def sample_messages(self) -> List[Dict[str, str]]:
        """Sample conversation messages for testing"""
        return [
            {"role": "user", "content": "Hello! I'm interested in crypto investing"},
            {"role": "assistant", "content": "Hi! That's great. What kind of investments are you looking for?"},
        ]

    @pytest.fixture
    def mock_anthropic_response_with_cache(self):
        """Mock Claude API response with cache usage"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello! I'm interested in crypto investments.")]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 50
        mock_response.usage.output_tokens = 25
        mock_response.usage.cache_read_input_tokens = 40  # Cache hit
        mock_response.usage.cache_creation_input_tokens = 10
        return mock_response

    @pytest.fixture
    def mock_anthropic_response_no_cache(self):
        """Mock Claude API response without cache usage"""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello! I'm interested in crypto investments.")]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 50
        mock_response.usage.output_tokens = 25
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.usage.cache_creation_input_tokens = 0
        return mock_response

    def test_init_claude_client(self, test_config):
        """Test ClaudeClient initialization"""
        client = ClaudeClient(
            api_key=test_config["ANTHROPIC_API_KEY"],
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=1.0,
        )

        assert client.api_key == test_config["ANTHROPIC_API_KEY"]
        assert client.model == "claude-3-5-sonnet-20241022"
        assert client.max_tokens == 2048
        assert client.temperature == 1.0
        assert client.client is not None
        assert client.async_client is not None

    def test_prepare_system_blocks_with_cache_enabled(self, sample_system_prompt):
        """Test system prompt preparation with cache control enabled"""
        client = ClaudeClient(api_key="test_key")

        blocks = client._prepare_system_blocks(sample_system_prompt, use_cache=True)

        assert len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert blocks[0]["text"] == sample_system_prompt
        assert "cache_control" in blocks[0]
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}

    def test_prepare_system_blocks_with_cache_disabled(self, sample_system_prompt):
        """Test system prompt preparation with cache control disabled"""
        client = ClaudeClient(api_key="test_key")

        blocks = client._prepare_system_blocks(sample_system_prompt, use_cache=False)

        assert len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert blocks[0]["text"] == sample_system_prompt
        assert "cache_control" not in blocks[0]

    def test_extract_response_text_single_block(self):
        """Test extracting text from single content block"""
        client = ClaudeClient(api_key="test_key")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Hello world!")]

        result = client._extract_response_text(mock_response)
        assert result == "Hello world!"

    def test_extract_response_text_multiple_blocks(self):
        """Test extracting text from multiple content blocks"""
        client = ClaudeClient(api_key="test_key")

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text="Hello "),
            MagicMock(type="text", text="world!"),
        ]

        result = client._extract_response_text(mock_response)
        assert result == "Hello world!"

    def test_extract_response_text_no_content(self):
        """Test extracting text when response has no content"""
        client = ClaudeClient(api_key="test_key")

        mock_response = MagicMock()
        mock_response.content = []

        result = client._extract_response_text(mock_response)
        assert result == ""

    def test_extract_response_text_non_text_blocks(self):
        """Test extracting text when response has non-text blocks"""
        client = ClaudeClient(api_key="test_key")

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="image", text=""),  # Non-text block
            MagicMock(type="text", text="Hello!"),
        ]

        result = client._extract_response_text(mock_response)
        assert result == "Hello!"

    def test_log_cache_usage_with_cache_hit(self, mock_anthropic_response_with_cache, caplog):
        """Test logging cache usage statistics when cache is hit"""
        client = ClaudeClient(api_key="test_key")

        with caplog.at_level("INFO"):
            client._log_cache_usage(mock_anthropic_response_with_cache.usage)

        assert "Cache usage" in caplog.text
        assert "Read: 40" in caplog.text
        assert "Creation: 10" in caplog.text
        assert "Hit rate: 44.4%" in caplog.text  # (40) / (40 + 50) * 100 = 44.4%

    def test_log_cache_usage_no_cache_hit(self, mock_anthropic_response_no_cache, caplog):
        """Test logging cache usage when no cache hit"""
        client = ClaudeClient(api_key="test_key")

        with caplog.at_level("DEBUG"):
            client._log_cache_usage(mock_anthropic_response_no_cache.usage)

        assert "Token usage" in caplog.text
        assert "Input: 50" in caplog.text
        assert "Output: 25" in caplog.text

    def test_log_cache_usage_no_usage_attr(self, caplog):
        """Test logging when usage object lacks cache attributes"""
        client = ClaudeClient(api_key="test_key")

        mock_usage = MagicMock()
        del mock_usage.cache_read_input_tokens  # Remove cache attributes

        # Should not raise exception
        client._log_cache_usage(mock_usage)

    def test_format_conversation_messages_valid_roles(self, sample_conversation_data):
        """Test formatting conversation messages with valid roles"""
        client = ClaudeClient(api_key="test_key")

        result = client.format_conversation_messages(sample_conversation_data)

        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello, I'm interested in crypto investing"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "user"

    def test_format_conversation_messages_invalid_roles(self, sample_conversation_data, caplog):
        """Test formatting conversation messages with invalid roles"""
        client = ClaudeClient(api_key="test_key")

        messages_with_invalid_role = sample_conversation_data + [
            {"role": "system", "content": "This is a system message"}
        ]

        with caplog.at_level("WARNING"):
            result = client.format_conversation_messages(messages_with_invalid_role)

        assert len(result) == 4
        assert result[3]["role"] == "user"  # Invalid role converted to user
        assert "Invalid role 'system'" in caplog.text

    @pytest.mark.asyncio
    async def test_test_connection_success(self, mock_claude_client, caplog):
        """Test successful API connection test"""
        with caplog.at_level("INFO"):
            result = await mock_claude_client.test_connection()

        assert result is True
        assert "Claude API connection test successful" in caplog.text

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, caplog):
        """Test failed API connection test"""
        client = ClaudeClient(api_key="invalid_key")

        # Mock the async client to raise exception
        client.async_client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        with caplog.at_level("ERROR"):
            result = await client.test_connection()

        assert result is False
        assert "Claude API connection test failed" in caplog.text

    @pytest.mark.asyncio
    async def test_test_connection_empty_response(self, caplog):
        """Test connection test with empty response"""
        client = ClaudeClient(api_key="test_key")

        # Mock response with empty content
        mock_response = MagicMock()
        mock_response.content = []
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.usage.cache_read_input_tokens = 0
        mock_response.usage.cache_creation_input_tokens = 0
        client.async_client.messages.create = AsyncMock(return_value=mock_response)

        with caplog.at_level("ERROR"):
            result = await client.test_connection()

        assert result is False
        assert "Claude API returned empty response" in caplog.text

    def test_generate_response_sync(self, mock_claude_client, sample_system_prompt, sample_messages):
        """Test synchronous response generation"""
        response = mock_claude_client.generate_response(
            system_prompt=sample_system_prompt,
            messages=sample_messages,
            use_cache=True,
        )

        assert response == "Hello! I'm interested in crypto investments."
        mock_claude_client.client.messages.create.assert_called_once()

    def test_generate_response_sync_error(self, sample_system_prompt, sample_messages, caplog):
        """Test synchronous response generation with API error"""
        client = ClaudeClient(api_key="test_key")
        client.client.messages.create = MagicMock(side_effect=Exception("API Error"))

        with caplog.at_level("ERROR"):
            with pytest.raises(Exception, match="API Error"):
                client.generate_response(
                    system_prompt=sample_system_prompt,
                    messages=sample_messages,
                )

        assert "Error generating Claude response" in caplog.text

    @pytest.mark.asyncio
    async def test_generate_response_async(self, mock_claude_client, sample_system_prompt, sample_messages):
        """Test asynchronous response generation"""
        response = await mock_claude_client.generate_response_async(
            system_prompt=sample_system_prompt,
            messages=sample_messages,
            use_cache=True,
        )

        assert response == "Hello! I'm interested in crypto investments."
        mock_claude_client.async_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_async_error(self, sample_system_prompt, sample_messages, caplog):
        """Test asynchronous response generation with API error"""
        client = ClaudeClient(api_key="test_key")
        client.async_client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        with caplog.at_level("ERROR"):
            with pytest.raises(Exception, match="API Error"):
                await client.generate_response_async(
                    system_prompt=sample_system_prompt,
                    messages=sample_messages,
                )

        assert "Error generating async Claude response" in caplog.text

    @pytest.mark.asyncio
    async def test_generate_response_stream(self, mock_claude_client, sample_system_prompt, sample_messages):
        """Test streaming response generation"""
        chunks = []
        async for chunk in mock_claude_client.generate_response_stream(
            system_prompt=sample_system_prompt,
            messages=sample_messages,
        ):
            chunks.append(chunk)

        assert chunks == ["Hello! I'm interested in crypto investments."]
        mock_claude_client.async_client.messages.stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_stream_error(self, sample_system_prompt, sample_messages, caplog):
        """Test streaming response generation with API error"""
        client = ClaudeClient(api_key="test_key")

        # Mock stream context manager to raise exception
        mock_stream = MagicMock()
        mock_stream.__aenter__ = AsyncMock(side_effect=Exception("Streaming Error"))
        mock_stream.__aexit__ = AsyncMock(return_value=None)
        client.async_client.messages.stream = MagicMock(return_value=mock_stream)

        with caplog.at_level("ERROR"):
            with pytest.raises(Exception, match="Streaming Error"):
                async for chunk in client.generate_response_stream(
                    system_prompt=sample_system_prompt,
                    messages=sample_messages,
                ):
                    pass

        assert "Error in streaming Claude response" in caplog.text


class TestResponseGenerator:
    """Test ResponseGenerator orchestration functionality"""

    @pytest.fixture
    def mock_mcp_client(self):
        """Mock MCP-Prompts client"""
        client = MagicMock()
        client.get_category_prompt = AsyncMock()
        client.list_categories = AsyncMock(return_value=["bitcoin_investment", "romance_scam"])
        return client

    @pytest.fixture
    def sample_category_config(self) -> Dict[str, Any]:
        """Sample category configuration"""
        return {
            "system_prompt": "You are a crypto investment advisor.",
            "persona": {
                "name": "Alex Thompson",
                "age": 35,
                "background": "Experienced crypto trader with 5+ years in DeFi",
            },
            "behavior_notes": "Be cautious and ask many questions. Express hesitation about high-risk investments.",
            "conversation_style": "Professional but friendly",
            "risk_tolerance": "low",
        }

    def test_init_response_generator(self, mock_claude_client, mock_mcp_client):
        """Test ResponseGenerator initialization"""
        generator = ResponseGenerator(
            claude_client=mock_claude_client,
            mcp_client=mock_mcp_client,
            use_cache=True,
        )

        assert generator.claude == mock_claude_client
        assert generator.mcp == mock_mcp_client
        assert generator.use_cache is True
        assert generator._category_cache == {}

    @pytest.mark.asyncio
    async def test_generate_honeypot_response_success(
        self, mock_claude_client, mock_mcp_client, sample_category_config
    ):
        """Test successful honeypot response generation"""
        mock_mcp_client.get_category_prompt.return_value = sample_category_config

        generator = ResponseGenerator(
            claude_client=mock_claude_client,
            mcp_client=mock_mcp_client,
        )

        response = await generator.generate_honeypot_response(
            category="bitcoin_investment",
            incoming_message="Hello! Want to invest in crypto?",
            platform="telegram",
        )

        assert response == "Hello! I'm interested in crypto investments."
        mock_mcp_client.get_category_prompt.assert_called_once_with(
            category="bitcoin_investment",
            platform="telegram"
        )
        mock_claude_client.async_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_honeypot_response_with_history(
        self, mock_claude_client, mock_mcp_client, sample_category_config, sample_conversation_data
    ):
        """Test response generation with conversation history"""
        mock_mcp_client.get_category_prompt.return_value = sample_category_config

        generator = ResponseGenerator(
            claude_client=mock_claude_client,
            mcp_client=mock_mcp_client,
        )

        response = await generator.generate_honeypot_response(
            category="bitcoin_investment",
            incoming_message="Can you help me invest?",
            conversation_history=sample_conversation_data,
        )

        assert response == "Hello! I'm interested in crypto investments."
        # Verify conversation history was passed to Claude
        call_args = mock_claude_client.async_client.messages.create.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 4  # 3 history + 1 new message
        assert messages[-1]["content"] == "Can you help me invest?"

    @pytest.mark.asyncio
    async def test_generate_honeypot_response_category_not_found(self, mock_mcp_client, caplog):
        """Test response generation when category is not found"""
        mock_mcp_client.get_category_prompt.return_value = None

        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=mock_mcp_client,
        )

        with caplog.at_level("ERROR"):
            response = await generator.generate_honeypot_response(
                category="unknown_category",
                incoming_message="Hello?",
            )

        # Should return a fallback response (any of the predefined confused responses)
        assert isinstance(response, str)
        assert len(response) > 10  # Should be a meaningful response
        assert "Failed to load category: unknown_category" in caplog.text

    @pytest.mark.asyncio
    async def test_generate_honeypot_response_error_fallback(self, mock_mcp_client, caplog):
        """Test error handling with fallback response"""
        mock_mcp_client.get_category_prompt.side_effect = Exception("MCP Error")

        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=mock_mcp_client,
        )

        with caplog.at_level("ERROR"):
            response = await generator.generate_honeypot_response(
                category="bitcoin_investment",
                incoming_message="Hello?",
            )

        # Should return a fallback response (any of the predefined confused responses)
        assert isinstance(response, str)
        assert len(response) > 10  # Should be a meaningful response
        assert "Failed to load category: bitcoin_investment" in caplog.text

    @pytest.mark.asyncio
    async def test_generate_streaming_response(self, mock_claude_client, mock_mcp_client, sample_category_config):
        """Test streaming response generation"""
        mock_mcp_client.get_category_prompt.return_value = sample_category_config

        generator = ResponseGenerator(
            claude_client=mock_claude_client,
            mcp_client=mock_mcp_client,
        )

        chunks = []
        async for chunk in generator.generate_streaming_response(
            category="bitcoin_investment",
            incoming_message="Hello!",
        ):
            chunks.append(chunk)

        # Should get the mocked streaming response
        assert len(chunks) == 1
        assert isinstance(chunks[0], str)
        assert len(chunks[0]) > 0

    def test_build_system_prompt_complete_config(self, sample_category_config):
        """Test building system prompt from complete category config"""
        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=MagicMock(),
        )

        prompt = generator._build_system_prompt(sample_category_config)

        assert "You are a crypto investment advisor." in prompt
        assert "Your name is Alex Thompson." in prompt
        assert "You are 35 years old." in prompt
        assert "Experienced crypto trader" in prompt
        assert "Be cautious and ask many questions." in prompt
        assert "You are a honeypot designed to waste scammer time." in prompt

    def test_build_system_prompt_minimal_config(self):
        """Test building system prompt from minimal category config"""
        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=MagicMock(),
        )

        minimal_config = {"system_prompt": "You are a helpful assistant."}

        prompt = generator._build_system_prompt(minimal_config)

        assert prompt == "You are a helpful assistant.\n\nIMPORTANT: You are a honeypot designed to waste scammer time. Be believable but slow to act. Ask many questions. Express confusion or hesitation when appropriate. Never reveal you are an AI."

    def test_format_persona_description_complete(self):
        """Test formatting complete persona description"""
        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=MagicMock(),
        )

        persona = {
            "name": "John Doe",
            "age": 30,
            "background": "Software developer",
        }

        result = generator._format_persona_description(persona)

        assert result == "Your name is John Doe. You are 30 years old. Software developer"

    def test_format_persona_description_partial(self):
        """Test formatting partial persona description"""
        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=MagicMock(),
        )

        persona = {"name": "Jane Smith"}

        result = generator._format_persona_description(persona)

        assert result == "Your name is Jane Smith."

    def test_format_persona_description_empty(self):
        """Test formatting empty persona description"""
        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=MagicMock(),
        )

        result = generator._format_persona_description({})
        assert result == ""

    def test_build_conversation_context_with_history(self, sample_conversation_data):
        """Test building conversation context with history"""
        # Mock the claude client to return the conversation history as-is
        mock_claude = MagicMock()
        mock_claude.format_conversation_messages.return_value = sample_conversation_data

        generator = ResponseGenerator(
            claude_client=mock_claude,
            mcp_client=MagicMock(),
        )

        messages = generator._build_conversation_context(
            incoming_message="What's your investment strategy?",
            conversation_history=sample_conversation_data,
        )

        assert len(messages) == 4  # 3 history + 1 new
        assert messages[0]["role"] == "user"
        assert messages[-1]["content"] == "What's your investment strategy?"

    def test_build_conversation_context_no_history(self):
        """Test building conversation context without history"""
        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=MagicMock(),
        )

        messages = generator._build_conversation_context(
            incoming_message="Hello!",
            conversation_history=None,
        )

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello!"

    def test_format_response_for_platform_basic(self):
        """Test basic platform response formatting"""
        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=MagicMock(),
        )

        result = generator._format_response_for_platform(
            response="Hello world!",
            platform="telegram",
            category_config={},
        )

        assert result == "Hello world!"

    def test_get_fallback_response_variety(self):
        """Test that fallback responses are varied"""
        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=MagicMock(),
        )

        responses = set()
        for _ in range(10):
            responses.add(generator._get_fallback_response())

        # Should get some variety (at least 2 different responses)
        assert len(responses) >= 2

    @pytest.mark.asyncio
    async def test_list_available_categories(self, mock_mcp_client):
        """Test listing available categories"""
        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=mock_mcp_client,
        )

        categories = await generator.list_available_categories()

        assert categories == ["bitcoin_investment", "romance_scam"]
        mock_mcp_client.list_categories.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_available_categories_error(self, caplog):
        """Test error handling when listing categories"""
        mock_mcp_client = MagicMock()
        mock_mcp_client.list_categories = AsyncMock(side_effect=Exception("MCP Error"))

        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=mock_mcp_client,
        )

        with caplog.at_level("ERROR"):
            categories = await generator.list_available_categories()

        assert categories == []
        assert "Failed to list categories" in caplog.text

    @pytest.mark.asyncio
    async def test_clear_category_cache(self):
        """Test clearing category cache"""
        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=MagicMock(),
        )

        # Add something to cache
        generator._category_cache["test"] = {"data": "value"}

        await generator.clear_category_cache()

        assert generator._category_cache == {}

    @pytest.mark.asyncio
    async def test_get_category_config_caching(self, mock_mcp_client, sample_category_config):
        """Test category configuration caching"""
        mock_mcp_client.get_category_prompt.return_value = sample_category_config

        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=mock_mcp_client,
        )

        # First call should fetch from MCP
        config1 = await generator._get_category_config("bitcoin_investment", "telegram")
        assert config1 == sample_category_config
        assert mock_mcp_client.get_category_prompt.call_count == 1

        # Second call should use cache
        config2 = await generator._get_category_config("bitcoin_investment", "telegram")
        assert config2 == sample_category_config
        assert mock_mcp_client.get_category_prompt.call_count == 1  # Still 1

        # Different platform should fetch again
        config3 = await generator._get_category_config("bitcoin_investment", "signal")
        assert config3 == sample_category_config
        assert mock_mcp_client.get_category_prompt.call_count == 2

    @pytest.mark.asyncio
    async def test_get_category_config_error_handling(self, mock_mcp_client, caplog):
        """Test error handling in category config fetching"""
        mock_mcp_client.get_category_prompt.side_effect = Exception("MCP Error")

        generator = ResponseGenerator(
            claude_client=MagicMock(),
            mcp_client=mock_mcp_client,
        )

        with caplog.at_level("ERROR"):
            config = await generator._get_category_config("bitcoin_investment", "telegram")

        assert config is None
        assert "Failed to fetch category config" in caplog.text