"""
Pydantic models for API request/response validation
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# Request Models
# ============================================================================


class CreateHoneypotRequest(BaseModel):
    """Request model for creating a new honeypot"""

    platform: str = Field(..., description="Platform name (telegram, signal, etc.)")
    category: str = Field(..., description="Honeypot category", example="bitcoin_investment")
    name: Optional[str] = Field(None, description="Friendly name for honeypot")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class LoginRequest(BaseModel):
    """Request model for authentication"""

    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


# ============================================================================
# Response Models
# ============================================================================


class HealthCheckResponse(BaseModel):
    """Response model for health check"""

    status: str
    timestamp: str
    components: Dict[str, bool]
    version: str = "0.1.0"


class StatisticsResponse(BaseModel):
    """Response model for system statistics"""

    active_sessions: int
    total_messages: int
    total_alerts: int
    fraud_detections: int
    platforms_active: List[str]
    uptime_seconds: Optional[int] = None


class SessionResponse(BaseModel):
    """Response model for session data"""

    session_id: str
    platform: str
    category: str
    status: str
    message_count: int
    created_at: str
    last_activity: str
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None


class SessionListResponse(BaseModel):
    """Response model for list of sessions"""

    sessions: List[SessionResponse]
    total: int
    page: int = 1
    page_size: int = 50


class AlertResponse(BaseModel):
    """Response model for alert data"""

    alert_id: str
    session_id: str
    risk_level: str
    risk_score: float
    indicators: Dict[str, Any]
    message_preview: str
    platform: str
    created_at: str
    acknowledged: bool = False


class AlertListResponse(BaseModel):
    """Response model for list of alerts"""

    alerts: List[AlertResponse]
    total: int
    unacknowledged: int


class ConversationResponse(BaseModel):
    """Response model for conversation data"""

    session_id: str
    platform: str
    messages: List[Dict[str, Any]]
    message_count: int
    risk_assessment: Optional[Dict[str, Any]] = None
    indicators: Optional[Dict[str, Any]] = None


class HoneypotResponse(BaseModel):
    """Response model for honeypot configuration"""

    honeypot_id: str
    platform: str
    category: str
    name: Optional[str] = None
    status: str
    created_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenResponse(BaseModel):
    """Response model for authentication token"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours in seconds


class ErrorResponse(BaseModel):
    """Response model for errors"""

    detail: str
    error_code: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class IndicatorsResponse(BaseModel):
    """Response model for extracted indicators"""

    btc_addresses: List[str] = Field(default_factory=list)
    eth_addresses: List[str] = Field(default_factory=list)
    urls: List[str] = Field(default_factory=list)
    phone_numbers: List[str] = Field(default_factory=list)
    email_addresses: List[str] = Field(default_factory=list)
    iban_numbers: List[str] = Field(default_factory=list)
    suspicious_keywords: List[str] = Field(default_factory=list)
    financial_amounts: List[str] = Field(default_factory=list)
    total_count: int = 0


class RiskAssessmentResponse(BaseModel):
    """Response model for risk assessment"""

    risk_score: float
    risk_level: str
    confidence: float
    risk_factors: List[str]
    recommendations: List[str]
    should_alert: bool
