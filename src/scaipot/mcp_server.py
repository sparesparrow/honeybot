"""
SCAIPOT MCP Server — exposes honeypot intelligence tools to Claude Desktop,
Claude Code, and Cursor via the Model Context Protocol.

Run standalone:
    python -m scaipot.mcp_server

Or via Docker (see docker-compose.yml service: scaipot-mcp).

Register in Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "scaipot": {
          "command": "python",
          "args": ["-m", "scaipot.mcp_server"],
          "env": {
            "SCAIPOT_API_URL": "http://localhost:8000",
            "SCAIPOT_API_TOKEN": "<your-jwt-token>"
          }
        }
      }
    }

Register in Claude Code (settings.json → mcpServers):
    Same config as above but set via `claude mcp add` or settings UI.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP Protocol helpers — minimal implementation of stdio-based MCP transport
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "scaipot"
SERVER_VERSION = "0.1.0"

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_active_sessions",
        "description": (
            "List all currently active honeypot sessions (ongoing scammer conversations). "
            "Returns session IDs, platforms, honeypot categories, message counts, and "
            "last activity timestamps."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Filter by platform: telegram, signal, or whatsapp",
                    "enum": ["telegram", "signal", "whatsapp"],
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of sessions to return (default 50)",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_conversation",
        "description": (
            "Retrieve the full conversation history and metadata for a specific honeypot "
            "session. Returns all messages exchanged, risk assessments, and extracted "
            "scam indicators (BTC addresses, URLs, phone numbers, etc.)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID in format platform:user_id (e.g. telegram:123456)",
                }
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "analyze_message",
        "description": (
            "Run SCAIPOT's fraud detection engine on arbitrary text. Extracts scam indicators "
            "(BTC/ETH addresses, URLs, IBANs, phone numbers, suspicious keywords) and returns "
            "a risk score with confidence level and recommended actions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Message text to analyze for scam patterns",
                }
            },
            "required": ["text"],
        },
    },
    {
        "name": "get_statistics",
        "description": (
            "Get system-wide SCAIPOT statistics: active sessions count, total messages "
            "processed, fraud detections, alerts generated, platform breakdown, and "
            "system uptime."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_categories",
        "description": (
            "List all available honeypot persona categories (e.g. bitcoin_investment, "
            "romance_scam, pig_butchering). Returns category names with descriptions "
            "of the persona and the scam type they target."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_alerts",
        "description": (
            "Retrieve recent high-risk alerts triggered by the fraud detection system. "
            "Includes session IDs, alert types, severity levels, and whether they've been "
            "acknowledged by an admin."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of alerts to return (default 20)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
                "unacknowledged_only": {
                    "type": "boolean",
                    "description": "If true, return only unacknowledged alerts",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "terminate_session",
        "description": (
            "Terminate an active honeypot session, ending the conversation with the scammer "
            "and archiving the session data. Use when a session has been fully analyzed or "
            "poses an operational risk."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session ID to terminate",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for termination (for audit log)",
                    "default": "Manual termination via MCP",
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "health_check",
        "description": (
            "Check the health status of all SCAIPOT components: API server, Claude LLM "
            "connection, Redis session store, PostgreSQL database, and MCP-Prompts server."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


class ScaipotAPIClient:
    """Thin HTTP client wrapping the SCAIPOT FastAPI admin endpoints."""

    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: Dict[str, str] = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        client = await self._get_client()
        response = await client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def delete(self, path: str) -> None:
        client = await self._get_client()
        response = await client.delete(path)
        response.raise_for_status()


class ScaipotMCPServer:
    """
    Stdio-based MCP server that proxies SCAIPOT FastAPI endpoints as MCP tools.
    Implements the MCP 2024-11-05 protocol over stdin/stdout.
    """

    def __init__(self, api_url: str, api_token: Optional[str] = None):
        self.api = ScaipotAPIClient(api_url, api_token)
        self._initialized = False

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Dispatch a tool call and return result as a JSON string."""
        try:
            if name == "get_active_sessions":
                return await self._get_active_sessions(arguments)
            elif name == "get_conversation":
                return await self._get_conversation(arguments)
            elif name == "analyze_message":
                return await self._analyze_message(arguments)
            elif name == "get_statistics":
                return await self._get_statistics()
            elif name == "list_categories":
                return await self._list_categories()
            elif name == "get_alerts":
                return await self._get_alerts(arguments)
            elif name == "terminate_session":
                return await self._terminate_session(arguments)
            elif name == "health_check":
                return await self._health_check()
            else:
                return json.dumps({"error": f"Unknown tool: {name}"})
        except httpx.HTTPStatusError as e:
            return json.dumps(
                {"error": f"API error {e.response.status_code}: {e.response.text}"}
            )
        except httpx.ConnectError:
            return json.dumps(
                {
                    "error": (
                        f"Cannot connect to SCAIPOT at {self.api.base_url}. "
                        "Is the server running? Try: docker-compose up -d"
                    )
                }
            )
        except Exception as e:
            logger.exception(f"Tool call failed: {name}")
            return json.dumps({"error": str(e)})

    async def _get_active_sessions(self, args: Dict[str, Any]) -> str:
        params: Dict[str, Any] = {"page_size": args.get("limit", 50)}
        if platform := args.get("platform"):
            params["platform"] = platform
        data = await self.api.get("/api/sessions", params=params)
        return json.dumps(data, indent=2)

    async def _get_conversation(self, args: Dict[str, Any]) -> str:
        session_id = args["session_id"]
        data = await self.api.get(f"/api/sessions/{session_id}")
        return json.dumps(data, indent=2)

    async def _analyze_message(self, args: Dict[str, Any]) -> str:
        # Use the SCAIPOT fraud detection engine via a lightweight inline call
        # Falls back to a direct import if the API isn't running locally
        text = args["text"]
        try:
            # Try via API first (works when SCAIPOT is running in Docker)
            data = await self.api.get(
                "/api/analyze", params={"text": text}
            )
            return json.dumps(data, indent=2)
        except httpx.HTTPStatusError:
            # Endpoint not yet implemented — use local import fallback
            try:
                from scaipot.fraud_detection.pattern_detector import PatternDetector

                detector = PatternDetector()
                result = await detector.analyze_message(text)
                return json.dumps(result, indent=2)
            except ImportError:
                return json.dumps(
                    {"error": "analyze endpoint not available and local import failed"}
                )

    async def _get_statistics(self) -> str:
        data = await self.api.get("/api/statistics")
        return json.dumps(data, indent=2)

    async def _list_categories(self) -> str:
        data = await self.api.get("/api/categories")
        return json.dumps(data, indent=2)

    async def _get_alerts(self, args: Dict[str, Any]) -> str:
        params = {
            "limit": args.get("limit", 20),
            "unacknowledged_only": str(args.get("unacknowledged_only", False)).lower(),
        }
        data = await self.api.get("/api/alerts", params=params)
        return json.dumps(data, indent=2)

    async def _terminate_session(self, args: Dict[str, Any]) -> str:
        session_id = args["session_id"]
        await self.api.delete(f"/api/sessions/{session_id}")
        return json.dumps(
            {"success": True, "session_id": session_id, "status": "terminated"}
        )

    async def _health_check(self) -> str:
        data = await self.api.get("/api/health")
        return json.dumps(data, indent=2)

    # ------------------------------------------------------------------
    # MCP stdio transport
    # ------------------------------------------------------------------

    def _send(self, message: Dict[str, Any]) -> None:
        """Write a JSON-RPC message to stdout."""
        line = json.dumps(message)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    def _error_response(self, request_id: Any, code: int, message: str) -> Dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    async def _handle_request(self, request: Dict[str, Any]) -> None:
        method = request.get("method", "")
        request_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            self._initialized = True
            self._send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": SERVER_NAME,
                            "version": SERVER_VERSION,
                        },
                    },
                }
            )

        elif method == "initialized":
            # Notification — no response required
            pass

        elif method == "tools/list":
            self._send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": TOOLS},
                }
            )

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            content = await self.call_tool(tool_name, arguments)
            self._send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": content}],
                        "isError": content.startswith('{"error"'),
                    },
                }
            )

        elif method == "ping":
            self._send({"jsonrpc": "2.0", "id": request_id, "result": {}})

        else:
            if request_id is not None:
                self._send(
                    self._error_response(request_id, -32601, f"Method not found: {method}")
                )

    async def run(self) -> None:
        """Run the MCP server, reading JSON-RPC messages from stdin."""
        logger.info(
            f"SCAIPOT MCP server starting — API: {self.api.base_url}"
        )

        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        try:
            while True:
                try:
                    line = await reader.readline()
                    if not line:
                        break
                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue
                    request = json.loads(line_str)
                    await self._handle_request(request)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    self._send(
                        self._error_response(None, -32700, f"Parse error: {e}")
                    )
                except Exception as e:
                    logger.exception("Unhandled error in request loop")
                    self._send(self._error_response(None, -32603, str(e)))
        finally:
            await self.api.close()
            logger.info("SCAIPOT MCP server stopped")


def main() -> None:
    """Entry point for the MCP server."""
    logging.basicConfig(
        level=logging.WARNING,  # Keep quiet on stderr (MCP uses stdout)
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    api_url = os.environ.get("SCAIPOT_API_URL", "http://localhost:8000")
    api_token = os.environ.get("SCAIPOT_API_TOKEN")

    server = ScaipotMCPServer(api_url=api_url, api_token=api_token)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
