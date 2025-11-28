"""
MCP-Prompts Client for fetching honeypot categories
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MCPPromptsClient:
    """Client for MCP-Prompts server"""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize MCP-Prompts client

        Args:
            base_url: MCP-Prompts server URL (e.g., http://mcp-prompts:3003)
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)

        logger.info(f"MCP-Prompts client initialized: {self.base_url}")

    async def get_category_prompt(
        self,
        category: str,
        platform: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get honeypot category prompt from MCP-Prompts

        Args:
            category: Scam category (e.g., "bitcoin_investment")
            platform: Optional platform filter (telegram, signal, whatsapp)

        Returns:
            Dict containing category prompt configuration

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}/v1/prompts/honeypot/category/{category}"
        params = {}

        if platform:
            params["platform"] = platform

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        logger.debug(f"Fetching category: {category} (platform: {platform or 'any'})")

        try:
            response = await self.client.get(url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Successfully fetched category: {category}")

            return data

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch category {category}: {e}")
            raise

    async def list_categories(self) -> List[str]:
        """
        List all available honeypot categories

        Returns:
            List of category names

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}/v1/prompts/honeypot/categories"

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            categories = data.get("categories", [])

            logger.info(f"Found {len(categories)} categories")

            return categories

        except httpx.HTTPError as e:
            logger.error(f"Failed to list categories: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check if MCP-Prompts server is healthy

        Returns:
            True if server is responsive, False otherwise
        """
        url = f"{self.base_url}/health"

        try:
            response = await self.client.get(url)
            return response.status_code == 200

        except Exception as e:
            logger.warning(f"MCP-Prompts health check failed: {e}")
            return False

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
