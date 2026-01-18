# Twilio Integration Guide

This guide shows how to integrate Twilio with your ElevenLabs Agent Connector to handle real phone calls.

## Architecture

```
Caller → Twilio Phone Number → Twilio Media Streams (WebSocket) → Your FastAPI → ElevenLabs Agent
```

## How Twilio Media Streams Work

1. **Caller dials** your Twilio number
2. **Twilio calls** your webhook with call details
3. **You respond** with TwiML instructing Twilio to stream audio
4. **Twilio opens** WebSocket connection to your server
5. **Audio flows bidirectionally**:
   - Caller audio → Twilio → Your server → ElevenLabs
   - ElevenLabs → Your server → Twilio → Caller

## Twilio Audio Format

- **Encoding**: mu-law (G.711)
- **Sample Rate**: 8kHz
- **Channels**: Mono
- **Transport**: Base64-encoded in JSON over WebSocket

**Important**: ElevenLabs uses 16kHz PCM, so you need to convert between formats.

## Setup Steps

### 1. Install Additional Dependencies

Add to `requirements.txt`:
```
audioop-lts==0.2.1  # For mu-law to PCM conversion
```

Install:
```bash
pip install audioop-lts
```

### 2. Environment Variables

Add to `.env`:
```ini
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

### 3. Update Configuration

Update `app/config.py` to include Twilio settings.

### 4. Create Twilio Service

Create `app/services/twilio_service.py` to handle:
- Audio format conversion (mu-law 8kHz ↔ PCM 16kHz)
- WebSocket message handling
- Bridging between Twilio and ElevenLabs

### 5. Add Twilio Endpoints

Add to `app/routers/webhooks.py`:
- `POST /twilio/incoming-call` - Initial webhook when call arrives
- `WS /twilio/media-stream` - WebSocket for audio streaming

## Implementation Flow

### Step 1: Incoming Call Webhook

When someone calls your Twilio number:

```python
@router.post("/twilio/incoming-call")
async def twilio_incoming_call(
    From: str = Form(...),  # Caller's phone number
    To: str = Form(...),    # Your Twilio number
    CallSid: str = Form(...)  # Unique call identifier
):
    # 1. Lookup customer context from database
    customer_data = await get_customer_by_phone(From)

    # 2. Store context for when WebSocket connects
    await store_call_context(CallSid, customer_data)

    # 3. Return TwiML to start media stream
    return Response(content=twiml_response, media_type="application/xml")
```

**TwiML Response**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://your-server.com/twilio/media-stream" />
    </Connect>
</Response>
```

### Step 2: WebSocket Media Stream

```python
@router.websocket("/twilio/media-stream")
async def twilio_media_stream(websocket: WebSocket):
    await websocket.accept()

    # Get call context
    call_sid = None
    customer_context = None
    elevenlabs_ws = None

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            event_type = data.get("event")

            if event_type == "start":
                # First message with call metadata
                call_sid = data["start"]["callSid"]
                customer_context = await get_call_context(call_sid)

                # Connect to ElevenLabs
                agent_id = select_agent(customer_context)
                signed_url = await get_signed_url(agent_id)
                elevenlabs_ws = await create_websocket_connection(signed_url)

                # Send initialization to ElevenLabs
                await send_elevenlabs_init(elevenlabs_ws, customer_context)

                # Start background task to receive from ElevenLabs
                asyncio.create_task(
                    receive_from_elevenlabs(elevenlabs_ws, websocket)
                )

            elif event_type == "media":
                # Audio from caller
                payload = data["media"]["payload"]  # Base64 mu-law

                # Convert mu-law 8kHz → PCM 16kHz
                pcm_audio = convert_mulaw_to_pcm(payload)

                # Send to ElevenLabs
                await send_to_elevenlabs(elevenlabs_ws, pcm_audio)

            elif event_type == "stop":
                # Call ended
                break

    finally:
        if elevenlabs_ws:
            await elevenlabs_ws.close()
        await websocket.close()
```

### Step 3: Audio Conversion

```python
import audioop
import base64

def convert_mulaw_to_pcm(mulaw_base64: str) -> bytes:
    """Convert Twilio's mu-law 8kHz to ElevenLabs PCM 16kHz"""
    # Decode base64
    mulaw_data = base64.b64decode(mulaw_base64)

    # mu-law to linear PCM
    pcm_8khz = audioop.ulaw2lin(mulaw_data, 2)  # 2 bytes per sample

    # Resample 8kHz → 16kHz
    pcm_16khz, _ = audioop.ratecv(
        pcm_8khz,
        2,      # Sample width (2 bytes = 16-bit)
        1,      # Channels (mono)
        8000,   # Input rate
        16000,  # Output rate
        None
    )

    return pcm_16khz

def convert_pcm_to_mulaw(pcm_16khz: bytes) -> str:
    """Convert ElevenLabs PCM 16kHz to Twilio's mu-law 8kHz"""
    # Resample 16kHz → 8kHz
    pcm_8khz, _ = audioop.ratecv(
        pcm_16khz,
        2,      # Sample width
        1,      # Channels
        16000,  # Input rate
        8000,   # Output rate
        None
    )

    # PCM to mu-law
    mulaw_data = audioop.lin2ulaw(pcm_8khz, 2)

    # Encode to base64
    return base64.b64encode(mulaw_data).decode('utf-8')
```

### Step 4: Send Audio Back to Caller

```python
async def receive_from_elevenlabs(elevenlabs_ws, twilio_ws):
    """Receive audio from ElevenLabs and send to Twilio"""
    try:
        while True:
            message = await elevenlabs_ws.recv()

            if isinstance(message, str):
                data = json.loads(message)

                if "audio_event" in data:
                    # Get PCM audio from ElevenLabs
                    pcm_base64 = data["audio_event"]["audio_base_64"]
                    pcm_bytes = base64.b64decode(pcm_base64)

                    # Convert PCM 16kHz → mu-law 8kHz
                    mulaw_base64 = convert_pcm_to_mulaw(pcm_bytes)

                    # Send to Twilio
                    twilio_message = {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": mulaw_base64
                        }
                    }
                    await twilio_ws.send_text(json.dumps(twilio_message))

    except Exception as e:
        logger.error(f"Error receiving from ElevenLabs: {e}")
```

## Testing

### 1. Expose Local Server (Development)

Use ngrok to expose your local server:
```bash
ngrok http 8000
```

You'll get a URL like: `https://abc123.ngrok.io`

### 2. Configure Twilio Number

1. Go to Twilio Console → Phone Numbers
2. Click your phone number
3. Under "Voice & Fax", set:
   - **A CALL COMES IN**: Webhook
   - **URL**: `https://abc123.ngrok.io/twilio/incoming-call`
   - **HTTP Method**: POST

### 3. Make a Test Call

Call your Twilio number from your phone. You should:
1. Hear ElevenLabs agent speaking
2. Be able to talk and get responses

## Customer Context Integration

```python
# Example: Database lookup when call arrives
@router.post("/twilio/incoming-call")
async def twilio_incoming_call(From: str = Form(...), CallSid: str = Form(...)):
    # Lookup customer in your database
    customer = await db.get_customer_by_phone(From)

    if customer:
        context = {
            "name": customer.name,
            "customer_id": customer.id,
            "due_date": customer.due_date,
            "total_enr_amount": str(customer.amount_due),
            "emi_eligible": customer.emi_eligible
        }

        # Select appropriate agent
        agent_id = select_agent_based_on_context(context)
    else:
        # Unknown caller
        context = {"name": "Valued Customer"}
        agent_id = "general_support_agent_id"

    # Store for WebSocket connection
    await redis.setex(f"call:{CallSid}", 3600, json.dumps({
        "agent_id": agent_id,
        "context": context
    }))

    # Return TwiML
    return generate_twiml_response()
```

## Session Management

For handling multiple concurrent calls:

```python
# Store active call sessions
active_calls = {}

class CallSession:
    def __init__(self, call_sid, agent_id, customer_context):
        self.call_sid = call_sid
        self.agent_id = agent_id
        self.customer_context = customer_context
        self.twilio_ws = None
        self.elevenlabs_ws = None
        self.start_time = datetime.utcnow()

    async def cleanup(self):
        if self.elevenlabs_ws:
            await self.elevenlabs_ws.close()
        if self.twilio_ws:
            await self.twilio_ws.close()

# In WebSocket handler
@router.websocket("/twilio/media-stream")
async def twilio_media_stream(websocket: WebSocket):
    call_sid = None
    session = None

    try:
        # ... handle events ...

        if event_type == "start":
            call_sid = data["start"]["callSid"]

            # Create session
            session = CallSession(call_sid, agent_id, customer_context)
            session.twilio_ws = websocket
            active_calls[call_sid] = session

    finally:
        if session:
            await session.cleanup()
            del active_calls[call_sid]
```

## Production Considerations

1. **Error Handling**: Handle WebSocket disconnections gracefully
2. **Logging**: Log all call events for debugging
3. **Monitoring**: Track call duration, success rate, errors
4. **Rate Limiting**: Limit concurrent calls if needed
5. **Security**: Validate Twilio requests using signature verification
6. **Failover**: Handle ElevenLabs API failures gracefully

## Cost Estimation

**Twilio Costs** (approximate, India):
- Phone number: ₹800/month
- Incoming calls: ₹0.60/minute
- Media Streams: No additional cost

**ElevenLabs Costs**:
- As per your ElevenLabs plan

**For 10-50 concurrent agents**:
- 1000 minutes/month ≈ ₹600 + ₹800 = ₹1,400/month (Twilio only)

## Next Steps

1. Install `audioop-lts` package
2. Create `twilio_service.py` with audio conversion functions
3. Add WebSocket endpoint for media streaming
4. Test with ngrok + real Twilio number
5. Add database lookup for customer context
6. Deploy to production server with proper domain

## Useful Resources

- [Twilio Media Streams Docs](https://www.twilio.com/docs/voice/media-streams)
- [Twilio Media Streams Quickstart](https://www.twilio.com/docs/voice/media-streams/quickstart)
- [ElevenLabs WebSocket API](https://elevenlabs.io/docs/agents-platform/api-reference/agents-platform/websocket)
