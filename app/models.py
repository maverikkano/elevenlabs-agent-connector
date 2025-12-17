from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class InitiateCallRequest(BaseModel):
    """Request model for initiating a call to an ElevenLabs agent."""

    agent_id: str = Field(..., description="ElevenLabs agent ID")
    session_id: Optional[str] = Field(None, description="Optional session identifier")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata from the dialer"
    )


class InitiateCallResponse(BaseModel):
    """Response model for successful call initiation."""

    success: bool = Field(..., description="Whether the call was initiated successfully")
    session_id: str = Field(..., description="Session identifier")
    websocket_url: str = Field(..., description="ElevenLabs WebSocket URL")
    message: str = Field(..., description="Status message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = Field(False, description="Always false for error responses")
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
