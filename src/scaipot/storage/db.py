"""
Database models and initialization
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class Conversation(Base):
    """Conversation model for storing scammer interactions"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    honeypot_id = Column(String(100), nullable=False, index=True)
    platform = Column(String(50), nullable=False)
    scammer_id = Column(String(255), nullable=False, index=True)
    message_text = Column(Text)
    message_type = Column(String(50))
    is_from_scammer = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON)


class ScamPattern(Base):
    """Detected scam patterns and indicators"""
    __tablename__ = "scam_patterns"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    pattern_type = Column(String(100), nullable=False)
    confidence = Column(Integer)  # 0-100
    indicators = Column(JSON)
    detected_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """Admin alerts for high-risk patterns"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, nullable=False)
    alert_type = Column(String(100), nullable=False)
    severity = Column(String(20))  # low, medium, high, critical
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    acknowledged = Column(Boolean, default=False)


async def init_database(database_url: str):
    """
    Initialize database connection and create tables

    Args:
        database_url: PostgreSQL connection string
    """
    # Security: Don't log database URLs as they may contain credentials
    logger.info("Initializing database connection")

    # Convert sync URL to async
    async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(async_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")

    return engine


async def get_session(engine):
    """
    Get async database session

    Args:
        engine: SQLAlchemy engine

    Returns:
        AsyncSession
    """
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
