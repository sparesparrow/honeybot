"""
Configuration management for SCAIPOT
"""
import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv


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
        "DATABASE_POOL_SIZE": int(os.getenv("DATABASE_POOL_SIZE", "20")),

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
        "JWT_SECRET": os.getenv("JWT_SECRET", "change-this-in-production"),
        "ALLOWED_ORIGINS": os.getenv("ALLOWED_ORIGINS", "http://localhost:3001").split(","),

        # Logging
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        "LOG_FORMAT": os.getenv("LOG_FORMAT", "json"),
        "SENTRY_DSN": os.getenv("SENTRY_DSN", ""),

        # Environment
        "ENV": os.getenv("ENV", "development"),
        "DEBUG": os.getenv("DEBUG", "true").lower() == "true",
    }

    return config


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
