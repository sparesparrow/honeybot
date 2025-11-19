"""
Message orchestrator coordinating bot adapters, LLM engine, and session management
"""
import logging
import asyncio
import uuid
from typing import Dict, Any, Optional
from .bots import BaseBotAdapter, IncomingMessage, OutgoingMessage
from .llm_engine import ClaudeClient, ResponseGenerator
from .mcp_integration import MCPPromptsClient
from .storage.session_manager import SessionManager
from .fraud_detection import PatternDetector
from .reporting import AlertManager, BitcoinWhosWhoReporter

logger = logging.getLogger(__name__)


class MessageOrchestrator:
    """
    Coordinates message handling across bot platforms, LLM generation,
    and session management for honeypot conversations
    """

    def __init__(
        self,
        session_manager: SessionManager,
        response_generator: ResponseGenerator,
        default_category: str = "bitcoin_investment",
        pattern_detector: Optional[PatternDetector] = None,
        alert_manager: Optional[AlertManager] = None,
        btc_reporter: Optional[BitcoinWhosWhoReporter] = None,
    ):
        """
        Initialize message orchestrator

        Args:
            session_manager: Session management instance
            response_generator: Response generation engine
            default_category: Default honeypot category for new conversations
            pattern_detector: Optional fraud detection engine
            alert_manager: Optional alert manager for admin notifications
            btc_reporter: Optional Bitcoin Who's Who reporter
        """
        self.session_manager = session_manager
        self.response_generator = response_generator
        self.default_category = default_category
        self.pattern_detector = pattern_detector or PatternDetector()
        self.alert_manager = alert_manager
        self.btc_reporter = btc_reporter

        self.bot_adapters: Dict[str, BaseBotAdapter] = {}
        self.is_running = False

        logger.info(
            "Initialized MessageOrchestrator with fraud detection and reporting"
        )

    def register_bot_adapter(
        self, platform_name: str, adapter: BaseBotAdapter
    ) -> None:
        """
        Register a bot adapter for a messaging platform

        Args:
            platform_name: Platform identifier (telegram, signal, etc.)
            adapter: Bot adapter instance
        """
        self.bot_adapters[platform_name] = adapter

        # Register this orchestrator as the message handler
        adapter.register_message_handler(self.handle_incoming_message)

        logger.info(f"Registered bot adapter for platform: {platform_name}")

    async def start(self) -> None:
        """
        Start all registered bot adapters
        """
        try:
            logger.info("Starting message orchestrator...")

            # Connect to Redis
            await self.session_manager.connect()

            # Start all bot adapters
            start_tasks = [
                adapter.start()
                for adapter in self.bot_adapters.values()
            ]
            await asyncio.gather(*start_tasks)

            self.is_running = True
            logger.info(
                f"Message orchestrator started with {len(self.bot_adapters)} platforms"
            )

        except Exception as e:
            logger.error(f"Failed to start message orchestrator: {e}")
            raise

    async def stop(self) -> None:
        """
        Stop all registered bot adapters
        """
        try:
            logger.info("Stopping message orchestrator...")

            # Stop all bot adapters
            stop_tasks = [
                adapter.stop()
                for adapter in self.bot_adapters.values()
            ]
            await asyncio.gather(*stop_tasks)

            # Disconnect from Redis
            await self.session_manager.disconnect()

            self.is_running = False
            logger.info("Message orchestrator stopped")

        except Exception as e:
            logger.error(f"Error stopping message orchestrator: {e}")

    async def handle_incoming_message(
        self, incoming_msg: IncomingMessage
    ) -> None:
        """
        Handle an incoming message from a scammer

        Args:
            incoming_msg: Standardized incoming message
        """
        try:
            logger.info(
                f"Handling message from {incoming_msg.platform}:{incoming_msg.sender_id}"
            )

            # Generate session ID
            session_id = self._generate_session_id(
                incoming_msg.platform, incoming_msg.sender_id
            )

            # Get or create session
            session = await self._get_or_create_session(
                session_id, incoming_msg
            )

            if not session:
                logger.error(f"Failed to get/create session {session_id}")
                return

            # Get bot adapter for this platform
            adapter = self.bot_adapters.get(incoming_msg.platform)
            if not adapter:
                logger.error(f"No adapter for platform: {incoming_msg.platform}")
                return

            # Send typing indicator to seem more human
            await adapter.send_typing_action(incoming_msg.chat_id)

            # Add a realistic delay (1-3 seconds)
            await asyncio.sleep(1.5)

            # Get conversation history
            conversation_history = await self._get_formatted_history(
                session_id
            )

            # Generate honeypot response
            response_text = await self.response_generator.generate_honeypot_response(
                category=session["category"],
                incoming_message=incoming_msg.content,
                conversation_history=conversation_history,
                platform=incoming_msg.platform,
            )

            # Save incoming message to history
            await self.session_manager.add_message_to_history(
                session_id=session_id,
                role="user",
                content=incoming_msg.content,
                metadata=incoming_msg.metadata,
            )

            # Analyze message for fraud patterns
            analysis = await self.pattern_detector.analyze_message(
                message=incoming_msg.content,
                metadata={
                    "session_id": session_id,
                    "platform": incoming_msg.platform,
                    "sender_id": incoming_msg.sender_id,
                },
            )

            # Handle high-risk patterns
            if analysis.get("risk_assessment", {}).get("should_alert"):
                logger.warning(
                    f"HIGH RISK detected in {session_id}: "
                    f"{analysis['risk_assessment']['risk_level']} "
                    f"({analysis['indicators']['total_count']} indicators)"
                )

                # Send admin alert
                if self.alert_manager:
                    await self.alert_manager.send_high_risk_alert(
                        session_id=session_id,
                        risk_level=analysis["risk_assessment"]["risk_level"],
                        risk_score=analysis["risk_assessment"]["risk_score"],
                        indicators=analysis["indicators"],
                        message_preview=incoming_msg.content,
                        platform=incoming_msg.platform,
                        recommendations=analysis["risk_assessment"]["recommendations"],
                    )

                # Report BTC addresses to threat database
                if self.btc_reporter and analysis["indicators"].get("btc_addresses"):
                    await self.btc_reporter.report_scammer_addresses(
                        btc_addresses=analysis["indicators"]["btc_addresses"],
                        scam_type="crypto_scam",
                        description=f"Detected in honeypot conversation (risk: {analysis['risk_assessment']['risk_level']})",
                        session_id=session_id,
                    )

            # Save outgoing response to history
            await self.session_manager.add_message_to_history(
                session_id=session_id,
                role="assistant",
                content=response_text,
                metadata={"fraud_analysis": analysis},
            )

            # Send response
            outgoing_msg = OutgoingMessage(
                chat_id=incoming_msg.chat_id,
                content=response_text,
                reply_to_message_id=incoming_msg.message_id,
            )

            success = await adapter.send_message(outgoing_msg)

            if success:
                logger.info(
                    f"Successfully responded to {incoming_msg.platform}:{incoming_msg.sender_id}"
                )
            else:
                logger.error("Failed to send response message")

        except Exception as e:
            logger.error(f"Error handling incoming message: {e}", exc_info=True)

    async def _get_or_create_session(
        self, session_id: str, incoming_msg: IncomingMessage
    ) -> Optional[Dict[str, Any]]:
        """
        Get existing session or create a new one

        Args:
            session_id: Session identifier
            incoming_msg: Incoming message that triggered this

        Returns:
            Session data dictionary
        """
        try:
            # Try to get existing session
            session = await self.session_manager.get_session(session_id)

            if session:
                # Update last activity
                await self.session_manager.update_session(
                    session_id, {"status": "active"}
                )
                logger.debug(f"Found existing session: {session_id}")
                return session

            # Create new session
            success = await self.session_manager.create_session(
                session_id=session_id,
                platform=incoming_msg.platform,
                category=self.default_category,
                scammer_identifier=incoming_msg.sender_id,
                metadata={
                    "chat_id": incoming_msg.chat_id,
                    "first_contact": incoming_msg.timestamp,
                    **incoming_msg.metadata,
                },
            )

            if success:
                session = await self.session_manager.get_session(session_id)
                logger.info(f"Created new session: {session_id}")
                return session
            else:
                logger.error(f"Failed to create session: {session_id}")
                return None

        except Exception as e:
            logger.error(f"Error getting/creating session: {e}")
            return None

    async def _get_formatted_history(
        self, session_id: str, limit: int = 20
    ) -> list:
        """
        Get conversation history formatted for LLM

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve

        Returns:
            List of formatted messages
        """
        try:
            history = await self.session_manager.get_conversation_history(
                session_id, limit=limit
            )

            # Convert to format expected by Claude
            formatted = []
            for msg in history:
                formatted.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

            return formatted

        except Exception as e:
            logger.error(f"Error getting formatted history: {e}")
            return []

    def _generate_session_id(self, platform: str, sender_id: str) -> str:
        """
        Generate a unique session ID for a scammer

        Args:
            platform: Platform name
            sender_id: Sender identifier

        Returns:
            Session ID string
        """
        # Use platform:sender_id as deterministic session ID
        # This ensures same scammer always gets same session
        return f"{platform}:{sender_id}"

    async def get_active_sessions_count(self) -> int:
        """
        Get count of active sessions

        Returns:
            Number of active sessions
        """
        try:
            sessions = await self.session_manager.list_active_sessions()
            return len(sessions)
        except Exception as e:
            logger.error(f"Error getting active sessions count: {e}")
            return 0

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get orchestrator statistics

        Returns:
            Dictionary with statistics
        """
        try:
            active_sessions = await self.get_active_sessions_count()

            stats = {
                "is_running": self.is_running,
                "platforms": list(self.bot_adapters.keys()),
                "active_sessions": active_sessions,
                "default_category": self.default_category,
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all components

        Returns:
            Dictionary with health status of each component
        """
        try:
            health = {
                "orchestrator": self.is_running,
                "redis": await self.session_manager.health_check(),
                "fraud_detection": await self.pattern_detector.health_check(),
            }

            # Check each bot adapter
            for platform, adapter in self.bot_adapters.items():
                health[f"bot_{platform}"] = await adapter.health_check()

            return health

        except Exception as e:
            logger.error(f"Error performing health check: {e}")
            return {"error": True}
