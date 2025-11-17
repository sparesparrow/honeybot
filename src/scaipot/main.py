"""
SCAIPOT Main Application Entry Point
"""
import asyncio
import logging
from typing import Optional

from scaipot.utils.config import load_config
from scaipot.storage.db import init_database

logger = logging.getLogger(__name__)


async def main():
    """Main application entry point"""
    logger.info("Starting SCAIPOT v0.1.0")

    # Load configuration
    config = load_config()
    logger.info(f"Configuration loaded for environment: {config.get('ENV', 'development')}")

    # Initialize database
    await init_database(config["DATABASE_URL"])
    logger.info("Database initialized")

    # Initialize bot adapters (placeholder)
    logger.info("Initializing bot adapters...")

    # Start application loop
    logger.info("SCAIPOT is running. Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down SCAIPOT...")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())
