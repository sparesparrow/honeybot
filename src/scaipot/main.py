"""
SCAIPOT - AI-Powered Cryptocurrency Scammer Honeypot
Main application entry point
"""
import asyncio
import logging
import signal
import sys
from typing import Optional

from scaipot.utils.config import load_config
from scaipot.storage.db import init_database
from scaipot.storage.session_manager import SessionManager
from scaipot.mcp_integration import MCPPromptsClient
from scaipot.llm_engine import ClaudeClient, ResponseGenerator
from scaipot.bots import TelegramBotAdapter, SignalBotAdapter
from scaipot.orchestrator import MessageOrchestrator

logger = logging.getLogger(__name__)

VERSION = "0.1.0"

# Global orchestrator for signal handling
orchestrator = None


async def main():
    """Main application entry point"""
    global orchestrator

    logger.info(f"Starting SCAIPOT v{VERSION}")
    logger.info("=" * 60)

    try:
        # Load configuration
        config = load_config()
        logger.info(f"✓ Loaded configuration (ENV: {config.get('ENV')})")

        # Initialize database
        db = await init_database(config["DATABASE_URL"])
        logger.info("✓ Database initialized")

        # Initialize session manager (Redis)
        session_manager = SessionManager(
            redis_url=config.get("REDIS_URL"),
            redis_password=config.get("REDIS_PASSWORD"),
            default_ttl=7200,  # 2 hours
        )
        logger.info("✓ Session manager initialized")

        # Initialize MCP-Prompts client
        mcp_client = MCPPromptsClient(
            base_url=config.get("MCP_PROMPTS_URL"),
            api_key=config.get("MCP_PROMPTS_API_KEY"),
        )

        # Test MCP connection
        if await mcp_client.health_check():
            logger.info("✓ MCP-Prompts server connected")
        else:
            logger.warning("⚠ MCP-Prompts health check failed, continuing anyway")

        # Initialize Claude client
        claude_client = ClaudeClient(
            api_key=config.get("ANTHROPIC_API_KEY"),
            model=config.get("CLAUDE_MODEL"),
            max_tokens=2048,
            temperature=1.0,
        )

        # Test Claude connection
        if await claude_client.test_connection():
            logger.info("✓ Claude API connected")
        else:
            raise RuntimeError("Claude API connection failed")

        # Initialize response generator
        response_generator = ResponseGenerator(
            claude_client=claude_client,
            mcp_client=mcp_client,
            use_cache=True,
        )
        logger.info("✓ Response generator initialized")

        # Initialize message orchestrator
        orchestrator = MessageOrchestrator(
            session_manager=session_manager,
            response_generator=response_generator,
            default_category="bitcoin_investment",
        )
        logger.info("✓ Message orchestrator initialized")

        # Initialize bot adapters based on configuration
        if telegram_token := config.get("TELEGRAM_BOT_TOKEN"):
            telegram_adapter = TelegramBotAdapter(
                config={"bot_token": telegram_token}
            )
            orchestrator.register_bot_adapter("telegram", telegram_adapter)
            logger.info("✓ Telegram bot adapter registered")
        else:
            logger.warning("⚠ Telegram bot token not configured, skipping")

        # Initialize Signal bot adapter if configured
        if signal_phone := config.get("SIGNAL_PHONE_NUMBER"):
            try:
                signal_adapter = SignalBotAdapter(
                    config={
                        "phone_number": signal_phone,
                        "signal_service": config.get("SIGNAL_SERVICE", "signal-cli-rest-api:8080"),
                        "storage_path": config.get("SIGNAL_STORAGE_PATH"),
                    }
                )
                orchestrator.register_bot_adapter("signal", signal_adapter)
                logger.info("✓ Signal bot adapter registered")
            except ImportError as e:
                logger.warning(f"⚠ Signal adapter unavailable: {e}")
        else:
            logger.warning("⚠ Signal phone number not configured, skipping")

        # TODO: Add WhatsApp adapter when implemented

        # Set up signal handlers for graceful shutdown
        setup_signal_handlers(orchestrator)

        # Start the orchestrator (this starts all bot adapters)
        logger.info("=" * 60)
        logger.info("Starting SCAIPOT honeypot...")
        logger.info("=" * 60)

        await orchestrator.start()

        # Log statistics
        stats = await orchestrator.get_statistics()
        logger.info(f"Active platforms: {', '.join(stats.get('platforms', []))}")
        logger.info(f"Default category: {stats.get('default_category')}")
        logger.info("=" * 60)
        logger.info("🍯 SCAIPOT is now active and waiting for scammers...")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        # Keep running indefinitely
        while True:
            # Periodic health checks
            await asyncio.sleep(60)

            health = await orchestrator.health_check()
            if not all(health.values()):
                logger.warning(f"Health check issues detected: {health}")

    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Received shutdown signal...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Graceful shutdown
        if orchestrator:
            logger.info("Shutting down SCAIPOT...")
            await orchestrator.stop()
            logger.info("✓ SCAIPOT stopped successfully")


def setup_signal_handlers(orch):
    """
    Set up signal handlers for graceful shutdown

    Args:
        orch: Orchestrator instance
    """
    def signal_handler(sig, frame):
        logger.info(f"\nReceived signal {sig}")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
