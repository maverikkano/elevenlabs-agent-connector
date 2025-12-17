# Dialer Integration Migration Guide

## Overview

This document outlines the steps required to migrate from the current **local microphone/speaker setup** to a **production dialer integration** for the ElevenLabs Agent Connector.

---

## Current Architecture vs. Target Architecture

### Current (Local Audio)
```
N8N Webhook → FastAPI Endpoint → ElevenLabs WebSocket
                     ↓
              Local Microphone Input
                     ↓
              ElevenLabs Agent Processing
                     ↓
              Local Speaker Output
```

### Target (Dialer Integration)
```
Incoming Call → Dialer System → FastAPI Endpoint → ElevenLabs WebSocket
                      ↓
              Dialer Audio Stream (Input)
                      ↓
              ElevenLabs Agent Processing
                      ↓
              Dialer Audio Stream (Output)
                      ↓
              Back to Caller
```

---

## Required Changes

### 1. Audio Service Refactoring

**File:** `app/services/audio_service.py`

#### Current Implementation Issues:
- Uses `sounddevice` for local microphone/speaker
- Single audio stream (not scalable for multiple calls)
- No call session management
- Audio I/O tied to local hardware

#### Required Changes:

**A. Create Abstract Audio Interface**
```python
# app/services/audio_interface.py (NEW FILE)

from abc import ABC, abstractmethod
from typing import AsyncIterator

class AudioInterface(ABC):
    """Abstract interface for audio input/output"""

    @abstractmethod
    async def read_audio_chunk(self) -> bytes:
        """Read audio chunk from source (mic, phone line, etc.)"""
        pass

    @abstractmethod
    async def write_audio_chunk(self, audio_data: bytes) -> None:
        """Write audio chunk to output (speaker, phone line, etc.)"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close audio streams"""
        pass
```

**B. Implement Local Audio (Keep for Testing)**
```python
# app/services/local_audio.py (NEW FILE)

import sounddevice as sd
import numpy as np
import asyncio
from app.services.audio_interface import AudioInterface

class LocalAudioInterface(AudioInterface):
    """Local microphone/speaker implementation (current behavior)"""

    def __init__(self):
        self.audio_queue = asyncio.Queue()
        self.stream = None
        # ... existing sounddevice logic
```

**C. Implement Dialer Audio**
```python
# app/services/dialer_audio.py (NEW FILE)

from app.services.audio_interface import AudioInterface

class DialerAudioInterface(AudioInterface):
    """Dialer audio stream implementation"""

    def __init__(self, call_id: str, dialer_client):
        self.call_id = call_id
        self.dialer = dialer_client
        self.input_buffer = asyncio.Queue()
        self.output_buffer = asyncio.Queue()

    async def read_audio_chunk(self) -> bytes:
        """Read audio from dialer's RTP/SIP stream"""
        # TODO: Implement based on dialer API
        pass

    async def write_audio_chunk(self, audio_data: bytes) -> None:
        """Write audio to dialer's output stream"""
        # TODO: Implement based on dialer API
        pass
```

**D. Refactor MicrophoneStreamer**
```python
# app/services/audio_service.py (MODIFIED)

class ConversationStreamer:  # Renamed from MicrophoneStreamer
    """Manages audio streaming for ElevenLabs conversation"""

    def __init__(self, audio_interface: AudioInterface):
        self.audio_interface = audio_interface  # Injected dependency
        self.websocket = None
        self.is_streaming = False

    async def _send_audio(self):
        """Send audio from interface to WebSocket"""
        while self.is_streaming:
            audio_chunk = await self.audio_interface.read_audio_chunk()
            # Encode and send to ElevenLabs (existing logic)

    async def _receive_audio(self):
        """Receive audio from WebSocket and play via interface"""
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_base64)
        await self.audio_interface.write_audio_chunk(audio_bytes)
```

---

### 2. Session Management

**File:** `app/services/session_manager.py` (NEW FILE)

#### Purpose:
Handle multiple concurrent calls, each with its own WebSocket and audio streams.

```python
# app/services/session_manager.py

from typing import Dict, Optional
import asyncio
from datetime import datetime

class CallSession:
    """Represents a single active call"""

    def __init__(self, session_id: str, call_id: str, agent_id: str):
        self.session_id = session_id
        self.call_id = call_id
        self.agent_id = agent_id
        self.websocket = None
        self.audio_interface = None
        self.streamer = None
        self.started_at = datetime.utcnow()
        self.ended_at = None
        self.status = "initializing"  # initializing, active, ended

    def duration(self) -> float:
        """Get call duration in seconds"""
        end = self.ended_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()


class SessionManager:
    """Manages multiple concurrent call sessions"""

    def __init__(self):
        self.sessions: Dict[str, CallSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, session_id: str, call_id: str, agent_id: str) -> CallSession:
        """Create a new call session"""
        async with self._lock:
            session = CallSession(session_id, call_id, agent_id)
            self.sessions[session_id] = session
            return session

    async def get_session(self, session_id: str) -> Optional[CallSession]:
        """Get session by ID"""
        return self.sessions.get(session_id)

    async def end_session(self, session_id: str):
        """End and clean up a session"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.ended_at = datetime.utcnow()
                session.status = "ended"

                # Clean up resources
                if session.audio_interface:
                    await session.audio_interface.close()
                if session.websocket:
                    await session.websocket.close()

                # Remove from active sessions after a delay (for logging)
                await asyncio.sleep(60)
                self.sessions.pop(session_id, None)

    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        return sum(1 for s in self.sessions.values() if s.status == "active")


# Global session manager instance
session_manager = SessionManager()
```

---

### 3. Webhook Endpoint Updates

**File:** `app/routers/webhooks.py` (MODIFIED)

#### Current Issues:
- No call ID or phone number handling
- No session lifecycle management
- Assumes single conversation

#### Required Changes:

```python
# app/routers/webhooks.py

from app.services.session_manager import session_manager
from app.services.dialer_audio import DialerAudioInterface
from app.services.local_audio import LocalAudioInterface
from app.config import settings

@router.post("/webhook/initiate-call")
async def initiate_call(
    request: InitiateCallRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """Initiate a call to an ElevenLabs agent"""

    session_id = request.session_id or str(uuid.uuid4())

    # Extract call metadata
    call_id = request.metadata.get("call_id") if request.metadata else None
    caller_number = request.metadata.get("caller_number") if request.metadata else None

    logger.info(
        f"Initiating call - Session: {session_id}, Call: {call_id}, "
        f"Caller: {caller_number}, Agent: {request.agent_id}"
    )

    # Create session
    session = await session_manager.create_session(session_id, call_id, request.agent_id)

    try:
        # Get signed URL
        signed_url = await elevenlabs_service.get_signed_url(request.agent_id)

        # Establish WebSocket
        websocket = await elevenlabs_service.create_websocket_connection(signed_url)
        session.websocket = websocket

        # Determine audio interface based on configuration
        if settings.use_dialer_audio:
            # Production: Use dialer audio
            dialer_client = get_dialer_client()  # TODO: Implement
            audio_interface = DialerAudioInterface(call_id, dialer_client)
        else:
            # Development: Use local audio
            audio_interface = LocalAudioInterface()

        session.audio_interface = audio_interface

        # Start audio streaming
        async def run_audio_stream():
            try:
                session.status = "active"
                dynamic_variables = request.metadata.get("dynamic_variables") if request.metadata else None

                await audio_service.start_conversation_stream(
                    websocket,
                    audio_interface=audio_interface,
                    duration=None,
                    dynamic_variables=dynamic_variables
                )
            except Exception as e:
                logger.error(f"Error in audio stream: {str(e)}")
            finally:
                await session_manager.end_session(session_id)

        background_tasks.add_task(run_audio_stream)

        return InitiateCallResponse(
            success=True,
            session_id=session_id,
            websocket_url=signed_url,
            message="Call initiated successfully",
            call_id=call_id
        )

    except Exception as e:
        await session_manager.end_session(session_id)
        raise


@router.post("/webhook/end-call")
async def end_call(session_id: str):
    """End an active call"""

    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await session_manager.end_session(session_id)

    return {
        "success": True,
        "session_id": session_id,
        "duration": session.duration(),
        "message": "Call ended"
    }


@router.get("/sessions")
async def list_sessions():
    """List all active sessions (for monitoring)"""

    return {
        "active_sessions": session_manager.get_active_sessions_count(),
        "sessions": [
            {
                "session_id": s.session_id,
                "call_id": s.call_id,
                "agent_id": s.agent_id,
                "status": s.status,
                "duration": s.duration()
            }
            for s in session_manager.sessions.values()
        ]
    }
```

---

### 4. Configuration Updates

**File:** `app/config.py` (MODIFIED)

```python
# Add new configuration fields

class Settings(BaseSettings):
    # ... existing fields

    # Dialer Configuration
    use_dialer_audio: bool = False  # Toggle between local/dialer audio
    dialer_api_url: str = ""
    dialer_api_key: str = ""
    dialer_type: str = "local"  # local, twilio, custom

    # Twilio Configuration (if using Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Call Settings
    max_concurrent_calls: int = 10
    call_timeout_seconds: int = 600  # 10 minutes
```

**File:** `.env.example` (MODIFIED)

```bash
# ... existing variables

# Dialer Configuration
USE_DIALER_AUDIO=false
DIALER_API_URL=
DIALER_API_KEY=
DIALER_TYPE=local

# Twilio Configuration (if applicable)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# Call Settings
MAX_CONCURRENT_CALLS=10
CALL_TIMEOUT_SECONDS=600
```

---

### 5. Request/Response Models Updates

**File:** `app/models.py` (MODIFIED)

```python
# Add call-specific fields

class InitiateCallRequest(BaseModel):
    agent_id: str = Field(..., description="ElevenLabs agent ID")
    session_id: Optional[str] = Field(None, description="Optional session identifier")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata including call_id, caller_number, dynamic_variables"
    )

    # New fields for dialer integration
    call_id: Optional[str] = Field(None, description="Dialer's call identifier")
    caller_number: Optional[str] = Field(None, description="Caller's phone number")
    called_number: Optional[str] = Field(None, description="Called phone number")


class InitiateCallResponse(BaseModel):
    success: bool
    session_id: str
    websocket_url: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # New fields
    call_id: Optional[str] = Field(None, description="Dialer's call identifier")


class EndCallRequest(BaseModel):
    """Request to end an active call"""
    session_id: str = Field(..., description="Session to terminate")
    reason: Optional[str] = Field(None, description="Reason for ending call")


class EndCallResponse(BaseModel):
    """Response for ended call"""
    success: bool
    session_id: str
    call_id: Optional[str]
    duration: float = Field(..., description="Call duration in seconds")
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

---

### 6. Dependencies Updates

**File:** `requirements.txt` (MODIFIED)

```txt
# Existing dependencies
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
python-dotenv==1.0.0
httpx==0.25.0
websockets==12.0
sounddevice==0.4.6
numpy==1.26.0

# New dependencies for dialer integration
# Choose based on dialer type:

# Option 1: Twilio
twilio==8.10.0

# Option 2: SIP/VoIP
# pjsua2==2.13  # Python bindings for PJSIP

# Option 3: Generic RTP
# aiortc==1.5.0  # WebRTC and RTP

# Database for call logging (optional)
sqlalchemy==2.0.23
asyncpg==0.29.0  # PostgreSQL async driver
```

---

### 7. Dialer Client Implementation

**File:** `app/services/dialer_client.py` (NEW FILE)

This will vary based on your dialer. Examples:

#### Twilio Example:
```python
# app/services/twilio_client.py

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from app.config import settings

class TwilioDialerClient:
    """Twilio dialer integration"""

    def __init__(self):
        self.client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token
        )

    def generate_twiml_response(self, stream_url: str) -> str:
        """Generate TwiML to stream audio to our WebSocket"""
        response = VoiceResponse()
        connect = Connect()
        connect.stream(url=stream_url)
        response.append(connect)
        return str(response)

    async def initiate_call(self, to_number: str, webhook_url: str):
        """Make outbound call via Twilio"""
        call = self.client.calls.create(
            to=to_number,
            from_=settings.twilio_phone_number,
            url=webhook_url
        )
        return call.sid
```

#### Custom Dialer Example:
```python
# app/services/custom_dialer.py

import httpx
from app.config import settings

class CustomDialerClient:
    """Custom dialer API integration"""

    def __init__(self):
        self.api_url = settings.dialer_api_url
        self.api_key = settings.dialer_api_key
        self.client = httpx.AsyncClient()

    async def get_audio_stream(self, call_id: str):
        """Get audio stream for a specific call"""
        # TODO: Implement based on dialer's API
        # This would typically return a WebSocket or RTP stream URL
        pass

    async def send_audio(self, call_id: str, audio_data: bytes):
        """Send audio data to the call"""
        # TODO: Implement based on dialer's API
        pass

    async def hangup_call(self, call_id: str):
        """Hang up a call"""
        response = await self.client.post(
            f"{self.api_url}/calls/{call_id}/hangup",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()
```

---

## Integration Paths

### Path 1: Twilio Integration (Recommended)

**Pros:**
- ElevenLabs has native Twilio integration
- No audio bridging needed on your server
- Simpler implementation
- Twilio handles call routing, recording, etc.

**Cons:**
- Additional Twilio costs
- Less control over audio pipeline

**Implementation:**
1. Set up Twilio account
2. Configure Twilio phone numbers
3. Point Twilio webhooks to your FastAPI endpoints
4. Use Twilio's Media Streams to connect to ElevenLabs
5. Minimal audio handling in your code

**Documentation:**
- Twilio Media Streams: https://www.twilio.com/docs/voice/media-streams
- ElevenLabs + Twilio: https://elevenlabs.io/docs/agents-platform/integrate/telephony

### Path 2: SIP/VoIP Integration

**Pros:**
- Direct control over audio
- Works with any SIP-compatible dialer
- No third-party dependencies

**Cons:**
- Complex implementation (RTP, codecs, NAT traversal)
- Requires understanding of SIP protocol
- More infrastructure management

**Implementation:**
1. Set up SIP trunk between dialer and your server
2. Use PJSIP library for SIP handling
3. Bridge RTP audio streams with ElevenLabs WebSocket
4. Handle codec conversion (G.711 → PCM)
5. Manage NAT/firewall issues

### Path 3: Custom Dialer API

**Pros:**
- Tailored to your specific dialer
- Full control over integration

**Cons:**
- Depends entirely on dialer's capabilities
- May require custom audio format handling

**Implementation:**
1. Study dialer's API documentation
2. Implement audio stream retrieval
3. Bridge audio between dialer and ElevenLabs
4. Handle call lifecycle events

---

## Migration Checklist

### Phase 1: Preparation
- [ ] Choose dialer integration path (Twilio/SIP/Custom)
- [ ] Review dialer API documentation
- [ ] Set up test dialer account
- [ ] Identify audio format requirements
- [ ] Plan session management strategy

### Phase 2: Code Changes
- [ ] Create audio interface abstraction
- [ ] Implement dialer audio interface
- [ ] Refactor audio service to use interfaces
- [ ] Implement session manager
- [ ] Update webhook endpoints
- [ ] Add configuration for dialer
- [ ] Update models for call metadata
- [ ] Install new dependencies

### Phase 3: Testing
- [ ] Test with local audio (regression)
- [ ] Test with dialer in development
- [ ] Test multiple concurrent calls
- [ ] Test call timeout handling
- [ ] Test error scenarios (disconnect, network issues)
- [ ] Load testing with expected call volume

### Phase 4: Deployment
- [ ] Update environment variables
- [ ] Deploy to staging environment
- [ ] Configure dialer to point to staging
- [ ] End-to-end testing in staging
- [ ] Monitor session management
- [ ] Production deployment
- [ ] Update documentation

### Phase 5: Monitoring
- [ ] Set up call logging
- [ ] Monitor concurrent session count
- [ ] Track call duration metrics
- [ ] Monitor WebSocket errors
- [ ] Set up alerts for failures

---

## Testing Strategy

### Unit Tests
```python
# tests/test_audio_interfaces.py

import pytest
from app.services.local_audio import LocalAudioInterface
from app.services.dialer_audio import DialerAudioInterface

@pytest.mark.asyncio
async def test_local_audio_interface():
    """Test local audio interface"""
    interface = LocalAudioInterface()
    # Test read/write operations

@pytest.mark.asyncio
async def test_dialer_audio_interface():
    """Test dialer audio interface with mock dialer"""
    # Mock dialer client
    # Test audio bridging
```

### Integration Tests
```python
# tests/test_session_management.py

import pytest
from app.services.session_manager import session_manager

@pytest.mark.asyncio
async def test_multiple_sessions():
    """Test handling multiple concurrent calls"""
    # Create multiple sessions
    # Verify isolation
    # Test cleanup
```

### End-to-End Tests
- Make test call through dialer
- Verify audio flows both directions
- Test call hangup
- Verify session cleanup

---

## Rollback Plan

If issues arise during migration:

1. **Immediate Rollback:**
   - Set `USE_DIALER_AUDIO=false` in environment
   - Restart application
   - System reverts to local audio mode

2. **Code Rollback:**
   - Keep local audio implementation intact
   - Use feature flags to toggle dialer mode
   - Maintain backward compatibility

---

## Estimated Timeline

- **Path 1 (Twilio):** 2-3 days
  - Day 1: Twilio setup, TwiML configuration
  - Day 2: Integration testing
  - Day 3: Deployment and monitoring

- **Path 2 (SIP):** 1-2 weeks
  - Week 1: SIP implementation, audio bridging
  - Week 2: Testing, debugging, deployment

- **Path 3 (Custom):** Varies based on dialer API complexity

---

## Support and Resources

### ElevenLabs Documentation
- Telephony Integration: https://elevenlabs.io/docs/agents-platform/integrate/telephony
- WebSocket API: https://elevenlabs.io/docs/agents-platform/api-reference/agents-platform/websocket

### Twilio Resources (if using)
- Media Streams: https://www.twilio.com/docs/voice/media-streams
- Programmable Voice: https://www.twilio.com/docs/voice

### SIP Resources (if using)
- PJSIP: https://www.pjsip.org/
- RFC 3261 (SIP): https://tools.ietf.org/html/rfc3261

---

## Contact

For questions about this migration, refer to:
- Main documentation: `README.md`
- Project context: `CLAUDE.md`
- ElevenLabs support: support@elevenlabs.io
