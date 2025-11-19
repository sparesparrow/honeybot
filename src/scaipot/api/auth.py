"""
JWT authentication for API endpoints
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

security = HTTPBearer()


def create_access_token(
    data: dict, secret_key: str, expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token

    Args:
        data: Data to encode in token
        secret_key: JWT secret key
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)

    return encoded_jwt


def verify_token(token: str, secret_key: str) -> dict:
    """
    Verify JWT token

    Args:
        token: JWT token to verify
        secret_key: JWT secret key

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    secret_key: str = None,
) -> dict:
    """
    Dependency to get current authenticated user

    Args:
        credentials: HTTP bearer credentials
        secret_key: JWT secret key

    Returns:
        User data from token

    Raises:
        HTTPException: If authentication fails
    """
    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication not configured",
        )

    token = credentials.credentials
    return verify_token(token, secret_key)


class AuthDependency:
    """Dependency class for authentication with secret key injection"""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    async def __call__(
        self, credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> dict:
        """Verify token and return user data"""
        return verify_token(credentials.credentials, self.secret_key)
