"""
FastAPI server for SCAIPOT admin dashboard
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth import AuthDependency, create_access_token
from .models import (
    HealthCheckResponse,
    StatisticsResponse,
    SessionListResponse,
    SessionResponse,
    AlertListResponse,
    AlertResponse,
    ConversationResponse,
    HoneypotResponse,
    CreateHoneypotRequest,
    LoginRequest,
    TokenResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)


def create_app(
    orchestrator=None,
    jwt_secret: str = "dev_secret_change_in_production",
    allowed_origins: Optional[List[str]] = None,
    admin_username: str = "admin",
    admin_password_hash: str = "admin",  # Change in production!
) -> FastAPI:
    """
    Create and configure FastAPI application

    Args:
        orchestrator: MessageOrchestrator instance
        jwt_secret: JWT secret key for authentication
        allowed_origins: CORS allowed origins
        admin_username: Admin username for authentication
        admin_password_hash: Admin password (hash in production)

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="SCAIPOT Admin API",
        description="REST API for SCAIPOT honeypot administration and monitoring",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS middleware
    if allowed_origins is None:
        allowed_origins = ["http://localhost:3000", "http://localhost:3001"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Authentication dependency
    auth_dependency = AuthDependency(jwt_secret)

    # Store dependencies
    app.state.orchestrator = orchestrator
    app.state.jwt_secret = jwt_secret
    app.state.admin_username = admin_username
    app.state.admin_password_hash = admin_password_hash
    app.state.start_time = datetime.utcnow()

    # ========================================================================
    # Public Endpoints
    # ========================================================================

    @app.get("/api/health", response_model=HealthCheckResponse, tags=["System"])
    async def health_check():
        """
        Health check endpoint

        Returns system health status and component availability
        """
        try:
            components = {"api": True}

            # Check orchestrator health
            if orchestrator:
                health = await orchestrator.health_check()
                components.update(health)

            return HealthCheckResponse(
                status="healthy" if all(components.values()) else "degraded",
                timestamp=datetime.utcnow().isoformat(),
                components=components,
            )

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unhealthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                },
            )

    @app.post(
        "/api/auth/login",
        response_model=TokenResponse,
        tags=["Authentication"],
        responses={401: {"model": ErrorResponse}},
    )
    async def login(request: LoginRequest):
        """
        Authenticate and receive JWT token

        Validates credentials and returns access token for API access
        """
        # Simple auth check (use proper password hashing in production!)
        if (
            request.username != admin_username
            or request.password != admin_password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create access token
        access_token = create_access_token(
            data={"sub": request.username, "role": "admin"},
            secret_key=jwt_secret,
            expires_delta=timedelta(hours=24),
        )

        return TokenResponse(access_token=access_token, expires_in=86400)

    # ========================================================================
    # Protected Endpoints
    # ========================================================================

    @app.get(
        "/api/statistics",
        response_model=StatisticsResponse,
        tags=["System"],
        dependencies=[Depends(auth_dependency)],
    )
    async def get_statistics():
        """
        Get system statistics

        Returns overall system metrics including active sessions,
        messages processed, and alerts generated
        """
        try:
            if not orchestrator:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Orchestrator not available",
                )

            stats = await orchestrator.get_statistics()

            # Calculate uptime
            uptime = (datetime.utcnow() - app.state.start_time).total_seconds()

            return StatisticsResponse(
                active_sessions=stats.get("active_sessions", 0),
                total_messages=0,  # TODO: Track in orchestrator
                total_alerts=0,  # TODO: Get from alert manager
                fraud_detections=0,  # TODO: Get from pattern detector
                platforms_active=stats.get("platforms", []),
                uptime_seconds=int(uptime),
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get statistics: {str(e)}",
            )

    @app.get(
        "/api/sessions",
        response_model=SessionListResponse,
        tags=["Sessions"],
        dependencies=[Depends(auth_dependency)],
    )
    async def list_sessions(
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(50, ge=1, le=100, description="Items per page"),
        platform: Optional[str] = Query(None, description="Filter by platform"),
        status: Optional[str] = Query(None, description="Filter by status"),
    ):
        """
        List all honeypot sessions

        Returns paginated list of active and historical sessions
        with basic metadata and risk scores
        """
        try:
            if not orchestrator:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Orchestrator not available",
                )

            # Get active sessions from session manager
            active_sessions = await orchestrator.session_manager.list_active_sessions()

            # Convert to response format
            sessions = []
            for session_id in active_sessions:
                session_data = await orchestrator.session_manager.get_session(
                    session_id
                )
                if session_data:
                    sessions.append(
                        SessionResponse(
                            session_id=session_id,
                            platform=session_data.get("platform", "unknown"),
                            category=session_data.get("category", "unknown"),
                            status=session_data.get("status", "active"),
                            message_count=session_data.get("message_count", 0),
                            created_at=session_data.get(
                                "created_at", datetime.utcnow().isoformat()
                            ),
                            last_activity=session_data.get(
                                "last_activity", datetime.utcnow().isoformat()
                            ),
                        )
                    )

            # Apply filters
            if platform:
                sessions = [s for s in sessions if s.platform == platform]
            if status:
                sessions = [s for s in sessions if s.status == status]

            # Pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_sessions = sessions[start_idx:end_idx]

            return SessionListResponse(
                sessions=paginated_sessions,
                total=len(sessions),
                page=page,
                page_size=page_size,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list sessions: {str(e)}",
            )

    @app.get(
        "/api/sessions/{session_id}",
        response_model=ConversationResponse,
        tags=["Sessions"],
        dependencies=[Depends(auth_dependency)],
    )
    async def get_session(session_id: str):
        """
        Get detailed session data

        Returns complete conversation history, risk assessment,
        and extracted indicators for a specific session
        """
        try:
            if not orchestrator:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Orchestrator not available",
                )

            # Get session metadata
            session_data = await orchestrator.session_manager.get_session(session_id)
            if not session_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Session {session_id} not found",
                )

            # Get conversation history
            messages = await orchestrator.session_manager.get_conversation_history(
                session_id, limit=1000
            )

            return ConversationResponse(
                session_id=session_id,
                platform=session_data.get("platform", "unknown"),
                messages=messages,
                message_count=len(messages),
                risk_assessment=None,  # TODO: Get from fraud analysis
                indicators=None,  # TODO: Get from fraud analysis
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get session: {str(e)}",
            )

    @app.get(
        "/api/alerts",
        response_model=AlertListResponse,
        tags=["Alerts"],
        dependencies=[Depends(auth_dependency)],
    )
    async def list_alerts(
        limit: int = Query(50, ge=1, le=200, description="Number of alerts to return"),
        unacknowledged_only: bool = Query(
            False, description="Show only unacknowledged alerts"
        ),
    ):
        """
        List recent high-risk alerts

        Returns alerts generated by fraud detection system
        for manual review and acknowledgment
        """
        # TODO: Implement alert storage and retrieval
        # For now, return empty list
        return AlertListResponse(alerts=[], total=0, unacknowledged=0)

    @app.post(
        "/api/honeypots",
        response_model=HoneypotResponse,
        tags=["Honeypots"],
        dependencies=[Depends(auth_dependency)],
        status_code=status.HTTP_201_CREATED,
    )
    async def create_honeypot(request: CreateHoneypotRequest):
        """
        Create a new honeypot instance

        Provisions a new honeypot with specified platform and category
        """
        # TODO: Implement honeypot creation
        # For now, return mock response
        honeypot_id = f"{request.platform}_{int(datetime.utcnow().timestamp())}"

        return HoneypotResponse(
            honeypot_id=honeypot_id,
            platform=request.platform,
            category=request.category,
            name=request.name,
            status="pending",
            created_at=datetime.utcnow().isoformat(),
            metadata=request.metadata,
        )

    @app.get(
        "/api/honeypots",
        response_model=List[HoneypotResponse],
        tags=["Honeypots"],
        dependencies=[Depends(auth_dependency)],
    )
    async def list_honeypots():
        """
        List all configured honeypots

        Returns list of honeypot configurations across all platforms
        """
        # TODO: Implement honeypot listing
        return []

    @app.delete(
        "/api/sessions/{session_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["Sessions"],
        dependencies=[Depends(auth_dependency)],
    )
    async def terminate_session(session_id: str):
        """
        Terminate an active session

        Ends conversation with scammer and archives session data
        """
        try:
            if not orchestrator:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Orchestrator not available",
                )

            # Update session status to terminated
            await orchestrator.session_manager.update_session(
                session_id, {"status": "terminated"}
            )

            return None

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error terminating session {session_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to terminate session: {str(e)}",
            )

    logger.info("FastAPI application created successfully")

    return app


# Create default app instance (can be overridden)
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
