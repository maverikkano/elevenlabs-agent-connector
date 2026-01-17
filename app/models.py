from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class InitiateCallRequest(BaseModel):
    agent_id: str
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class InitiateCallResponse(BaseModel):
    success: bool
    session_id: str
    websocket_url: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
