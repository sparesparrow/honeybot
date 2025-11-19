"""
Redis-based session management for scammer conversations
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages conversation sessions using Redis for persistence and caching
    """

    def __init__(
        self,
        redis_url: str,
        redis_password: Optional[str] = None,
        default_ttl: int = 7200,  # 2 hours
    ):
        """
        Initialize session manager

        Args:
            redis_url: Redis connection URL
            redis_password: Redis password (if required)
            default_ttl: Default session TTL in seconds
        """
        self.redis_url = redis_url
        self.redis_password = redis_password
        self.default_ttl = default_ttl
        self.redis_client: Optional[redis.Redis] = None

        logger.info("Initialized SessionManager")

    async def connect(self) -> None:
        """
        Establish connection to Redis
        """
        try:
            self.redis_client = await redis.from_url(
                self.redis_url,
                password=self.redis_password,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self) -> None:
        """
        Close Redis connection
        """
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")

    async def create_session(
        self,
        session_id: str,
        platform: str,
        category: str,
        scammer_identifier: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create a new scammer session

        Args:
            session_id: Unique session identifier
            platform: Platform name (telegram, signal, whatsapp)
            category: Honeypot category
            scammer_identifier: Scammer's ID or phone number
            metadata: Additional session metadata

        Returns:
            True if session created successfully
        """
        try:
            session_data = {
                "session_id": session_id,
                "platform": platform,
                "category": category,
                "scammer_identifier": scammer_identifier,
                "created_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat(),
                "message_count": 0,
                "status": "active",
                "metadata": metadata or {},
            }

            session_key = self._get_session_key(session_id)
            await self.redis_client.setex(
                session_key, self.default_ttl, json.dumps(session_data)
            )

            logger.info(
                f"Created session {session_id} for {platform}/{category}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return False

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data

        Args:
            session_id: Session identifier

        Returns:
            Session data dictionary or None if not found
        """
        try:
            session_key = self._get_session_key(session_id)
            data = await self.redis_client.get(session_key)

            if data:
                return json.loads(data)
            else:
                logger.warning(f"Session {session_id} not found")
                return None

        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None

    async def update_session(
        self, session_id: str, updates: Dict[str, Any]
    ) -> bool:
        """
        Update session data

        Args:
            session_id: Session identifier
            updates: Dictionary of fields to update

        Returns:
            True if update successful
        """
        try:
            session = await self.get_session(session_id)
            if not session:
                logger.error(f"Cannot update non-existent session: {session_id}")
                return False

            # Update fields
            session.update(updates)
            session["last_activity"] = datetime.utcnow().isoformat()

            # Save back to Redis
            session_key = self._get_session_key(session_id)
            await self.redis_client.setex(
                session_key, self.default_ttl, json.dumps(session)
            )

            logger.debug(f"Updated session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update session: {e}")
            return False

    async def add_message_to_history(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a message to conversation history

        Args:
            session_id: Session identifier
            role: Message role ('user' or 'assistant')
            content: Message content
            metadata: Additional message metadata

        Returns:
            True if message added successfully
        """
        try:
            history_key = self._get_history_key(session_id)

            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {},
            }

            # Append to conversation history list
            await self.redis_client.rpush(history_key, json.dumps(message))

            # Update TTL to match session TTL
            await self.redis_client.expire(history_key, self.default_ttl)

            # Increment message count in session
            await self.update_session(
                session_id,
                {"message_count": await self.get_message_count(session_id) + 1},
            )

            logger.debug(f"Added {role} message to session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add message to history: {e}")
            return False

    async def get_conversation_history(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history for a session

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve (None for all)

        Returns:
            List of message dictionaries
        """
        try:
            history_key = self._get_history_key(session_id)

            # Get all or limited messages
            if limit:
                messages = await self.redis_client.lrange(
                    history_key, -limit, -1
                )
            else:
                messages = await self.redis_client.lrange(
                    history_key, 0, -1
                )

            # Parse JSON messages
            parsed_messages = []
            for msg in messages:
                try:
                    parsed_messages.append(json.loads(msg))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse message: {msg}")
                    continue

            return parsed_messages

        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []

    async def get_message_count(self, session_id: str) -> int:
        """
        Get total message count for a session

        Args:
            session_id: Session identifier

        Returns:
            Number of messages in conversation
        """
        try:
            history_key = self._get_history_key(session_id)
            count = await self.redis_client.llen(history_key)
            return count or 0
        except Exception as e:
            logger.error(f"Failed to get message count: {e}")
            return 0

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its conversation history

        Args:
            session_id: Session identifier

        Returns:
            True if deletion successful
        """
        try:
            session_key = self._get_session_key(session_id)
            history_key = self._get_history_key(session_id)

            # Delete both keys
            await self.redis_client.delete(session_key, history_key)

            logger.info(f"Deleted session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False

    async def extend_session_ttl(
        self, session_id: str, additional_seconds: int = 3600
    ) -> bool:
        """
        Extend session TTL (useful for active conversations)

        Args:
            session_id: Session identifier
            additional_seconds: Additional time to add (default 1 hour)

        Returns:
            True if TTL extended successfully
        """
        try:
            session_key = self._get_session_key(session_id)
            history_key = self._get_history_key(session_id)

            # Get current TTL and add additional time
            current_ttl = await self.redis_client.ttl(session_key)
            if current_ttl > 0:
                new_ttl = current_ttl + additional_seconds
                await self.redis_client.expire(session_key, new_ttl)
                await self.redis_client.expire(history_key, new_ttl)

                logger.debug(
                    f"Extended TTL for session {session_id} by {additional_seconds}s"
                )
                return True
            else:
                logger.warning(f"Session {session_id} has no TTL or expired")
                return False

        except Exception as e:
            logger.error(f"Failed to extend session TTL: {e}")
            return False

    async def list_active_sessions(self, pattern: str = "*") -> List[str]:
        """
        List all active session IDs matching a pattern

        Args:
            pattern: Redis key pattern (default: all sessions)

        Returns:
            List of session IDs
        """
        try:
            search_pattern = f"session:{pattern}"
            keys = []

            async for key in self.redis_client.scan_iter(match=search_pattern):
                # Extract session ID from key
                session_id = key.replace("session:", "")
                keys.append(session_id)

            logger.info(f"Found {len(keys)} active sessions")
            return keys

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    def _get_session_key(self, session_id: str) -> str:
        """
        Generate Redis key for session data

        Args:
            session_id: Session identifier

        Returns:
            Redis key string
        """
        return f"session:{session_id}"

    def _get_history_key(self, session_id: str) -> str:
        """
        Generate Redis key for conversation history

        Args:
            session_id: Session identifier

        Returns:
            Redis key string
        """
        return f"history:{session_id}"

    async def health_check(self) -> bool:
        """
        Check if Redis connection is healthy

        Returns:
            True if connection is healthy
        """
        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
