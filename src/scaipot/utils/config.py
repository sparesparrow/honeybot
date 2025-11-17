"""
Configuration management for SCAIPOT
"""
import os
import secrets
import logging
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables

    Returns:
        Dict containing configuration values
    """
    # Load .env file if it exists
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)

    config = {
        # Platform API Keys
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "SIGNAL_PHONE_NUMBER": os.getenv("SIGNAL_PHONE_NUMBER", ""),
        "SIGNAL_STORAGE_PATH": os.getenv("SIGNAL_STORAGE_PATH", "/var/lib/scaipot/signal"),

        # Claude API
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "CLAUDE_MODEL": os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),

        # MCP-Prompts Server
        "MCP_PROMPTS_URL": os.getenv("MCP_PROMPTS_URL", "http://localhost:3003"),
        "MCP_PROMPTS_API_KEY": os.getenv("MCP_PROMPTS_API_KEY", ""),

        # Database
        "DATABASE_URL": os.getenv("DATABASE_URL", "postgresql://scaipot:password@localhost:5432/scaipot"),
        "DATABASE_POOL_SIZE": _get_database_pool_size(),

        # Redis
        "REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "REDIS_PASSWORD": os.getenv("REDIS_PASSWORD", ""),

        # Admin & Alerting
        "ADMIN_SLACK_WEBHOOK": os.getenv("ADMIN_SLACK_WEBHOOK", ""),
        "ADMIN_DISCORD_WEBHOOK": os.getenv("ADMIN_DISCORD_WEBHOOK", ""),
        "ADMIN_EMAIL": os.getenv("ADMIN_EMAIL", ""),

        # Honeypot Configuration
        "HONEYPOT_VM_ENABLED": os.getenv("HONEYPOT_VM_ENABLED", "false").lower() == "true",
        "HONEYPOT_NETWORK_ANALYSIS_ENABLED": os.getenv("HONEYPOT_NETWORK_ANALYSIS_ENABLED", "false").lower() == "true",
        "DOCKER_HOST": os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock"),

        # Security
        "JWT_SECRET": _get_jwt_secret(),
        "ALLOWED_ORIGINS": _get_allowed_origins(),

        # Logging
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        "LOG_FORMAT": os.getenv("LOG_FORMAT", "json"),
        "SENTRY_DSN": os.getenv("SENTRY_DSN", ""),

        # Environment
        "ENV": os.getenv("ENV", "development"),
        "DEBUG": os.getenv("DEBUG", "true").lower() == "true",
    }

    # Validate production configuration
    _validate_production_config(config)

    return config


def _get_database_pool_size() -> int:
    """
    Safely parse DATABASE_POOL_SIZE with validation

    Returns:
        int: Database pool size (1-100)
    """
    try:
        pool_size = int(os.getenv("DATABASE_POOL_SIZE", "20"))
        if not 1 <= pool_size <= 100:
            raise ValueError("Pool size must be between 1 and 100")
        return pool_size
    except ValueError as e:
        logger.warning(f"Invalid DATABASE_POOL_SIZE: {e}, using default 20")
        return 20


def _get_jwt_secret() -> str:
    """
    Get JWT secret with production validation

    Returns:
        str: JWT secret (random for dev, must be set for production)
    """
    jwt_secret = os.getenv("JWT_SECRET", "")
    env = os.getenv("ENV", "development")

    if not jwt_secret or jwt_secret == "change-this-in-production":
        if env == "production":
            raise ValueError(
                "JWT_SECRET must be set to a secure random value in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        # Generate random secret for development
        logger.info("Generating random JWT_SECRET for development environment")
        return secrets.token_urlsafe(32)

    return jwt_secret


def _get_allowed_origins() -> list:
    """
    Parse and validate ALLOWED_ORIGINS

    Returns:
        list: List of allowed origin URLs
    """
    origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3001")
    origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]

    if not origins:
        logger.warning("No ALLOWED_ORIGINS configured, using default localhost:3001")
        return ["http://localhost:3001"]

    return origins


def _validate_production_config(config: Dict[str, Any]) -> None:
    """
    Validate critical security settings for production environment

    Args:
        config: Configuration dictionary

    Raises:
        ValueError: If production configuration is insecure
    """
    if config.get("ENV") != "production":
        return

    logger.info("Validating production security configuration")

    # Check for weak database password
    db_url = config.get("DATABASE_URL", "")
    if ":password@" in db_url or "scaipot:password@" in db_url:
        raise ValueError(
            "DATABASE_URL contains default password 'password' in production. "
            "Set a strong password in DATABASE_PASSWORD environment variable."
        )

    # Require Anthropic API key for production
    if not config.get("ANTHROPIC_API_KEY"):
        raise ValueError(
            "ANTHROPIC_API_KEY is required for production deployment. "
            "Obtain an API key from https://console.anthropic.com/"
        )

    # Warn about Docker socket access
    if config.get("HONEYPOT_VM_ENABLED"):
        logger.warning(
            "HONEYPOT_VM_ENABLED is active in production. "
            "Ensure Docker socket is protected via docker-socket-proxy."
        )

    logger.info("Production security validation passed")


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate that required configuration values are present

    Args:
        config: Configuration dictionary

    Returns:
        True if valid, raises ValueError if invalid
    """
    required_fields = [
        "ANTHROPIC_API_KEY",
        "DATABASE_URL",
        "REDIS_URL",
    ]

    missing = [field for field in required_fields if not config.get(field)]

    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")

    return True
