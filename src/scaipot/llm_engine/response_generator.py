"""
Response generation engine integrating Claude API with MCP-Prompts
"""
import logging
from typing import Any, Dict, List, Optional

from ..mcp_integration.mcp_client import MCPPromptsClient
from .claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """
    Generates honeypot responses by combining Claude AI with MCP-Prompts personas
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        mcp_client: MCPPromptsClient,
        use_cache: bool = True,
    ):
        """
        Initialize response generator

        Args:
            claude_client: Claude API client instance
            mcp_client: MCP-Prompts client instance
            use_cache: Enable prompt caching (90% cost reduction)
        """
        self.claude = claude_client
        self.mcp = mcp_client
        self.use_cache = use_cache

        # In-memory cache for category prompts
        self._category_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("Initialized ResponseGenerator")

    async def generate_honeypot_response(
        self,
        category: str,
        incoming_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        platform: Optional[str] = None,
    ) -> str:
        """
        Generate a honeypot response for an incoming scammer message

        Args:
            category: Honeypot category (e.g., 'bitcoin_investment')
            incoming_message: Message received from potential scammer
            conversation_history: Previous messages in this conversation
            platform: Platform name (telegram, signal, whatsapp)

        Returns:
            Generated response text from AI honeypot persona
        """
        try:
            # Load category configuration from MCP-Prompts
            category_config = await self._get_category_config(category, platform)

            if not category_config:
                logger.error(f"Failed to load category: {category}")
                return self._get_fallback_response()

            # Extract system prompt from category
            system_prompt = self._build_system_prompt(category_config)

            # Build conversation context
            messages = self._build_conversation_context(
                incoming_message, conversation_history
            )

            # Generate response using Claude
            response = await self.claude.generate_response_async(
                system_prompt=system_prompt,
                messages=messages,
                use_cache=self.use_cache,
            )

            # Apply any platform-specific formatting
            formatted_response = self._format_response_for_platform(
                response, platform, category_config
            )

            logger.info(
                f"Generated response for category '{category}' "
                f"(platform: {platform}, cached: {self.use_cache})"
            )

            return formatted_response

        except Exception as e:
            logger.error(f"Error generating honeypot response: {e}")
            return self._get_fallback_response()

    async def generate_streaming_response(
        self,
        category: str,
        incoming_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        platform: Optional[str] = None,
    ):
        """
        Generate a streaming honeypot response for real-time interactions

        Args:
            category: Honeypot category
            incoming_message: Message from potential scammer
            conversation_history: Previous messages
            platform: Platform name

        Yields:
            Text chunks as they are generated
        """
        try:
            # Load category configuration
            category_config = await self._get_category_config(category, platform)

            if not category_config:
                yield self._get_fallback_response()
                return

            # Build system prompt and context
            system_prompt = self._build_system_prompt(category_config)
            messages = self._build_conversation_context(
                incoming_message, conversation_history
            )

            # Stream response from Claude
            async for chunk in self.claude.generate_response_stream(
                system_prompt=system_prompt,
                messages=messages,
                use_cache=self.use_cache,
            ):
                yield chunk

            logger.info(f"Completed streaming response for category '{category}'")

        except Exception as e:
            logger.error(f"Error in streaming response generation: {e}")
            yield self._get_fallback_response()

    async def _get_category_config(
        self, category: str, platform: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch category configuration from MCP-Prompts with caching

        Args:
            category: Category name
            platform: Optional platform name

        Returns:
            Category configuration dictionary or None
        """
        # Check in-memory cache first
        cache_key = f"{category}:{platform or 'default'}"
        if cache_key in self._category_cache:
            logger.debug(f"Using cached config for {cache_key}")
            return self._category_cache[cache_key]

        try:
            # Fetch from MCP-Prompts server
            config = await self.mcp.get_category_prompt(
                category=category, platform=platform
            )

            # Cache the result
            if config:
                self._category_cache[cache_key] = config
                logger.debug(f"Cached config for {cache_key}")

            return config

        except Exception as e:
            logger.error(f"Failed to fetch category config: {e}")
            return None

    def _build_system_prompt(self, category_config: Dict[str, Any]) -> str:
        """
        Build comprehensive system prompt from category configuration

        Args:
            category_config: Category configuration from MCP-Prompts

        Returns:
            Complete system prompt for Claude
        """
        # Extract components from config
        system_prompt = category_config.get("system_prompt", "")
        persona = category_config.get("persona", {})
        behavior_notes = category_config.get("behavior_notes", "")

        # Build comprehensive prompt
        prompt_parts = [system_prompt]

        # Add persona details if available
        if persona:
            persona_desc = self._format_persona_description(persona)
            if persona_desc:
                prompt_parts.append(f"\n\n{persona_desc}")

        # Add behavioral guidelines
        if behavior_notes:
            prompt_parts.append(f"\n\n{behavior_notes}")

        # Add honeypot-specific instructions
        prompt_parts.append(
            "\n\nIMPORTANT: You are a honeypot designed to waste scammer time. "
            "Be believable but slow to act. Ask many questions. Express confusion "
            "or hesitation when appropriate. Never reveal you are an AI."
        )

        return "".join(prompt_parts)

    def _format_persona_description(self, persona: Dict[str, Any]) -> str:
        """
        Format persona details into readable description

        Args:
            persona: Persona configuration dict

        Returns:
            Formatted persona description
        """
        parts = []

        if name := persona.get("name"):
            parts.append(f"Your name is {name}.")

        if age := persona.get("age"):
            parts.append(f"You are {age} years old.")

        if background := persona.get("background"):
            parts.append(background)

        return " ".join(parts) if parts else ""

    def _build_conversation_context(
        self,
        incoming_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        """
        Build conversation context for Claude API

        Args:
            incoming_message: Latest message from scammer
            conversation_history: Previous messages

        Returns:
            Formatted message list for Claude
        """
        messages = []

        # Add conversation history if provided
        if conversation_history:
            messages.extend(
                self.claude.format_conversation_messages(conversation_history)
            )

        # Add current incoming message
        messages.append({"role": "user", "content": incoming_message})

        return messages

    def _format_response_for_platform(
        self,
        response: str,
        platform: Optional[str],
        category_config: Dict[str, Any],
    ) -> str:
        """
        Apply platform-specific formatting to response

        Args:
            response: Generated response text
            platform: Platform name (telegram, signal, etc.)
            category_config: Category configuration

        Returns:
            Formatted response text
        """
        # For now, return as-is
        # Future: Add emoji support, character limits, markdown formatting
        return response.strip()

    def _get_fallback_response(self) -> str:
        """
        Generate fallback response when something goes wrong

        Returns:
            Generic confused response
        """
        fallback_responses = [
            "Sorry, I'm not sure I understand. Could you explain more?",
            "Hmm, that's interesting. Tell me more about that.",
            "I'm a bit confused. Can you clarify what you mean?",
            "That sounds complicated. Can you break it down for me?",
        ]

        # Simple rotation (in production, use random.choice)
        import random

        return random.choice(fallback_responses)

    async def list_available_categories(self) -> List[str]:
        """
        List all available honeypot categories from MCP-Prompts

        Returns:
            List of category names
        """
        try:
            categories = await self.mcp.list_categories()
            logger.info(f"Found {len(categories)} available categories")
            return categories
        except Exception as e:
            logger.error(f"Failed to list categories: {e}")
            return []

    async def clear_category_cache(self) -> None:
        """
        Clear the in-memory category configuration cache
        """
        self._category_cache.clear()
        logger.info("Cleared category cache")
