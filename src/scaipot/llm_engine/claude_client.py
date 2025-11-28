"""
Claude API client wrapper with prompt caching and streaming support
"""
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message, MessageStreamEvent

logger = logging.getLogger(__name__)


class ClaudeClient:
    """
    Wrapper for Anthropic Claude API with prompt caching and streaming support
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 2048,
        temperature: float = 1.0,
    ):
        """
        Initialize Claude API client

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize both sync and async clients
        self.client = Anthropic(api_key=api_key)
        self.async_client = AsyncAnthropic(api_key=api_key)

        logger.info(f"Initialized Claude client with model: {model}")

    def generate_response(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        use_cache: bool = True,
    ) -> str:
        """
        Generate synchronous response from Claude

        Args:
            system_prompt: System prompt defining persona behavior
            messages: List of conversation messages
            use_cache: Enable prompt caching for cost reduction

        Returns:
            Generated response text
        """
        try:
            # Prepare system blocks with cache control if enabled
            system_blocks = self._prepare_system_blocks(system_prompt, use_cache)

            # Call Claude API
            response: Message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_blocks,
                messages=messages,
            )

            # Extract text from response
            response_text = self._extract_response_text(response)

            # Log cache usage if available
            if hasattr(response, "usage"):
                self._log_cache_usage(response.usage)

            logger.debug(f"Generated response: {response_text[:100]}...")
            return response_text

        except Exception as e:
            logger.error(f"Error generating Claude response: {e}")
            raise

    async def generate_response_async(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        use_cache: bool = True,
    ) -> str:
        """
        Generate asynchronous response from Claude

        Args:
            system_prompt: System prompt defining persona behavior
            messages: List of conversation messages
            use_cache: Enable prompt caching for cost reduction

        Returns:
            Generated response text
        """
        try:
            # Prepare system blocks with cache control if enabled
            system_blocks = self._prepare_system_blocks(system_prompt, use_cache)

            # Call Claude API asynchronously
            response: Message = await self.async_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_blocks,
                messages=messages,
            )

            # Extract text from response
            response_text = self._extract_response_text(response)

            # Log cache usage if available
            if hasattr(response, "usage"):
                self._log_cache_usage(response.usage)

            logger.debug(f"Generated async response: {response_text[:100]}...")
            return response_text

        except Exception as e:
            logger.error(f"Error generating async Claude response: {e}")
            raise

    async def generate_response_stream(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        use_cache: bool = True,
    ) -> AsyncIterator[str]:
        """
        Generate streaming response from Claude

        Args:
            system_prompt: System prompt defining persona behavior
            messages: List of conversation messages
            use_cache: Enable prompt caching for cost reduction

        Yields:
            Text chunks as they are generated
        """
        try:
            # Prepare system blocks with cache control if enabled
            system_blocks = self._prepare_system_blocks(system_prompt, use_cache)

            # Create streaming request
            async with self.async_client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_blocks,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text

                # Log usage after stream completes
                final_message = await stream.get_final_message()
                if hasattr(final_message, "usage"):
                    self._log_cache_usage(final_message.usage)

        except Exception as e:
            logger.error(f"Error in streaming Claude response: {e}")
            raise

    def _prepare_system_blocks(
        self, system_prompt: str, use_cache: bool
    ) -> List[Dict[str, Any]]:
        """
        Prepare system prompt blocks with optional cache control

        Args:
            system_prompt: System prompt text
            use_cache: Whether to enable prompt caching

        Returns:
            List of system prompt blocks
        """
        system_block = {
            "type": "text",
            "text": system_prompt,
        }

        # Add cache control directive for 90% cost reduction
        if use_cache:
            system_block["cache_control"] = {"type": "ephemeral"}

        return [system_block]

    def _extract_response_text(self, response: Message) -> str:
        """
        Extract text content from Claude API response

        Args:
            response: Claude API message response

        Returns:
            Extracted text content
        """
        if not response.content:
            return ""

        # Handle multiple content blocks (usually just one text block)
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)

        return "".join(text_parts)

    def _log_cache_usage(self, usage: Any) -> None:
        """
        Log prompt caching statistics for cost analysis

        Args:
            usage: Usage statistics from API response
        """
        if not hasattr(usage, "cache_read_input_tokens"):
            return

        cache_read = getattr(usage, "cache_read_input_tokens", 0)
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0)
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)

        if cache_read > 0:
            cache_hit_rate = (cache_read / (cache_read + input_tokens)) * 100
            logger.info(
                f"Cache usage - Read: {cache_read}, "
                f"Creation: {cache_creation}, "
                f"Hit rate: {cache_hit_rate:.1f}%, "
                f"Input: {input_tokens}, "
                f"Output: {output_tokens}"
            )
        else:
            logger.debug(
                f"Token usage - Input: {input_tokens}, Output: {output_tokens}"
            )

    def format_conversation_messages(
        self, conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Format conversation history for Claude API

        Args:
            conversation_history: List of messages with 'role' and 'content'

        Returns:
            Formatted messages for Claude API
        """
        formatted_messages = []

        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Claude API only accepts 'user' and 'assistant' roles
            if role not in ["user", "assistant"]:
                logger.warning(f"Invalid role '{role}', defaulting to 'user'")
                role = "user"

            formatted_messages.append({"role": role, "content": content})

        return formatted_messages

    async def test_connection(self) -> bool:
        """
        Test API connection and authentication

        Returns:
            True if connection successful, False otherwise
        """
        try:
            test_response = await self.generate_response_async(
                system_prompt="You are a helpful assistant.",
                messages=[{"role": "user", "content": "Hello"}],
                use_cache=False,
            )

            if test_response:
                logger.info("Claude API connection test successful")
                return True
            else:
                logger.error("Claude API returned empty response")
                return False

        except Exception as e:
            logger.error(f"Claude API connection test failed: {e}")
            return False
