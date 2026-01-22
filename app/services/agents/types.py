"""
Standardized types for Agent Abstraction
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class AgentEventTypes:
    """Standard event types emitted by agents"""
    AUDIO = "audio"
    TEXT = "text"
    TRANSCRIPTION = "transcription"
    INTERRUPTION = "interruption"
    ERROR = "error"
    PONG = "pong"
    METADATA = "metadata"


@dataclass
class AgentEvent:
    """
    Standardized event emitted by an agent stream.
    
    The 'data' field contains the payload:
    - AUDIO: bytes (PCM 16kHz mono 16-bit signed little-endian)
    - TEXT/TRANSCRIPTION: str
    - ERROR: Exception object or error message string
    """
    type: str
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None

    @property
    def is_error(self) -> bool:
        return self.type == AgentEventTypes.ERROR

    @property
    def is_audio(self) -> bool:
        return self.type == AgentEventTypes.AUDIO
