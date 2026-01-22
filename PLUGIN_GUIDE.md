# Dialer Plugin Architecture Guide

## Overview

The gateway now uses a **plugin-based architecture** that makes it completely dialer-agnostic. You can easily swap between Twilio, Plivo, Exotel, or any other dialer provider, or support multiple dialers simultaneously.

## Architecture

### Core Components

1. **Abstract Interfaces** ([app/services/dialers/base.py](app/services/dialers/base.py))
   - `AudioConverter` - Handles audio format conversion
   - `MessageBuilder` - Builds dialer-specific messages
   - `ConnectionHandler` - Parses incoming dialer messages
   - `DialerService` - Main interface combining all components

2. **Plugin Registry** ([app/services/dialers/registry.py](app/services/dialers/registry.py))
   - Registers and manages dialer plugins
   - Provides lookup by dialer name

3. **Generic Router** ([app/routers/dialer.py](app/routers/dialer.py))
   - Dialer-agnostic endpoints
   - Works with any registered dialer

### Twilio Plugin Structure

```
app/services/dialers/twilio/
├── __init__.py
├── audio_converter.py    # Converts mu-law ↔ PCM
├── message_builder.py    # Builds TwiML/WebSocket messages
├── connection_handler.py # Parses Twilio messages
└── service.py            # Main Twilio service
```

## Using the Generic Endpoints

### Outbound Calls

**Format:** `POST /{dialer_name}/outbound-call`

```bash
# Using Twilio
curl -X POST http://localhost:8000/twilio/outbound-call \
  -H "X-API-Key: test_key_123" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_xxx",
    "metadata": {
      "to_number": "+1234567890",
      "dynamic_variables": {
        "name": "John Doe"
      }
    }
  }'

# Same API, different dialer (when implemented)
curl -X POST http://localhost:8000/plivo/outbound-call \
  -H "X-API-Key: test_key_123" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Incoming Calls

**Format:** `POST /{dialer_name}/incoming-call`

Configure your dialer to call this webhook when a call arrives.

### Media Streaming

**Format:** `WS /{dialer_name}/media-stream`

Automatically called by the dialer for audio streaming.

## Adding a New Dialer Plugin

Let's add Plivo as an example:

### Step 1: Create Directory Structure

```bash
mkdir -p app/services/dialers/plivo
touch app/services/dialers/plivo/__init__.py
touch app/services/dialers/plivo/audio_converter.py
touch app/services/dialers/plivo/message_builder.py
touch app/services/dialers/plivo/connection_handler.py
touch app/services/dialers/plivo/service.py
```

### Step 2: Implement Audio Converter

```python
# app/services/dialers/plivo/audio_converter.py
from app.services.dialers.base import AudioConverter
import base64

class PlivoAudioConverter(AudioConverter):
    def dialer_to_pcm(self, audio_data: str) -> bytes:
        """Convert Plivo audio format to PCM 16kHz"""
        # Plivo uses G.711 mu-law or A-law
        # Implement conversion logic here
        pass

    def pcm_to_dialer(self, pcm_data: bytes) -> str:
        """Convert PCM 16kHz to Plivo audio format"""
        # Implement conversion logic here
        pass
```

### Step 3: Implement Message Builder

```python
# app/services/dialers/plivo/message_builder.py
from app.services.dialers.base import MessageBuilder
from typing import Dict, Optional

class PlivoMessageBuilder(MessageBuilder):
    def build_audio_message(self, stream_id: str, audio_payload: str) -> Dict:
        """Build Plivo audio message"""
        return {
            "event": "playAudio",
            "media": audio_payload
        }

    def build_connection_response(
        self,
        websocket_url: str,
        custom_params: Optional[Dict] = None
    ) -> str:
        """Build Plivo XML response"""
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Stream bidirectional="true">{websocket_url}</Stream>
</Response>'''
```

### Step 4: Implement Connection Handler

```python
# app/services/dialers/plivo/connection_handler.py
from app.services.dialers.base import ConnectionHandler
from typing import Dict, Any

class PlivoConnectionHandler(ConnectionHandler):
    async def handle_incoming_message(self, message: Dict) -> Dict[str, Any]:
        """Parse Plivo message and standardize"""
        event = message.get("event")

        if event == "start":
            return {
                "event_type": "start",
                "call_id": message.get("callUuid"),
                "stream_id": message.get("streamId"),
                "custom_parameters": message.get("customParams", {})
            }
        elif event == "media":
            return {
                "event_type": "media",
                "audio_payload": message.get("media")
            }
        # ... handle other events

    async def extract_call_metadata(self, start_data: Dict) -> Dict:
        """Extract Plivo metadata"""
        return {
            "call_id": start_data.get("call_id"),
            "stream_id": start_data.get("stream_id")
        }
```

### Step 5: Implement Main Service

```python
# app/services/dialers/plivo/service.py
from app.services.dialers.base import DialerService
from app.config import settings
import plivo  # Plivo SDK

class PlivoDialerService(DialerService):
    def get_audio_converter(self):
        return PlivoAudioConverter()

    def get_message_builder(self):
        return PlivoMessageBuilder()

    def get_connection_handler(self):
        return PlivoConnectionHandler()

    async def initiate_outbound_call(
        self,
        to_number: str,
        agent_id: str,
        dynamic_variables: Dict,
        websocket_url: str
    ) -> Dict:
        """Initiate call using Plivo API"""
        client = plivo.RestClient(
            settings.plivo_auth_id,
            settings.plivo_auth_token
        )

        # Build answer URL with WebSocket info
        answer_url = f"http://your-server/plivo/answer?ws={websocket_url}"

        # Make call
        response = client.calls.create(
            from_=settings.plivo_phone_number,
            to_=to_number,
            answer_url=answer_url
        )

        return {
            "success": True,
            "call_id": response["request_uuid"],
            "status": "initiated"
        }

    def get_dialer_name(self) -> str:
        return "plivo"

    def validate_config(self) -> bool:
        """Validate Plivo configuration"""
        return bool(
            settings.plivo_auth_id and
            settings.plivo_auth_token and
            settings.plivo_phone_number
        )
```

### Step 6: Add Configuration

```python
# app/config.py
class Settings(BaseSettings):
    # ... existing settings ...

    # Plivo settings
    plivo_auth_id: str = ""
    plivo_auth_token: str = ""
    plivo_phone_number: str = ""
```

### Step 7: Register Plugin

```python
# app/main.py
from app.services.dialers.plivo.service import PlivoDialerService

# Register dialers
DialerRegistry.register("twilio", TwilioDialerService)
DialerRegistry.register("plivo", PlivoDialerService)
```

### Step 8: Add Environment Variables

```bash
# .env
PLIVO_AUTH_ID=your_auth_id
PLIVO_AUTH_TOKEN=your_auth_token
PLIVO_PHONE_NUMBER=+1234567890
```

### Step 9: Use It!

```bash
curl -X POST http://localhost:8000/plivo/outbound-call \
  -H "X-API-Key: test_key_123" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

## Benefits of Plugin Architecture

✅ **Swap Dialers Instantly**: Change from Twilio to Plivo by just updating the URL
✅ **No Core Code Changes**: Add new dialers without modifying gateway logic
✅ **Multi-Dialer Support**: Support multiple providers simultaneously
✅ **Easy Testing**: Mock dialers for testing without external dependencies
✅ **Clean Separation**: Dialer-specific code is isolated in plugins
✅ **Consistent API**: Same endpoints work for all dialers

## Available Dialers

Currently implemented:
- ✅ **Twilio** - Fully implemented and tested

Coming soon (implement using guide above):
- ⚪ **Plivo** - Indian dialer with local numbers
- ⚪ **Exotel** - Indian dialer with local support
- ⚪ **Vonage** - Global dialer with good coverage
- ⚪ **Custom SIP** - Your own SIP infrastructure

## Backward Compatibility

The old Twilio-specific endpoints are **deprecated but still work**:
- `POST /twilio/outbound-call` → Use `POST /twilio/outbound-call` (new router)
- `POST /twilio/incoming-call` → Use `POST /twilio/incoming-call` (new router)
- `WS /twilio/media-stream` → Use `WS /twilio/media-stream` (new router)

**Note:** The paths are the same, but they now use the generic router internally.

## Migration Guide

Your existing code **doesn't need changes** - the new architecture handles the same paths! But you gain the ability to add more dialers easily.

### Before (Twilio-specific):
```bash
POST /twilio/outbound-call
```

### After (Dialer-agnostic):
```bash
POST /twilio/outbound-call  # Same path!
POST /plivo/outbound-call   # Add more dialers!
POST /exotel/outbound-call  # Easy to extend!
```

## Testing

Test that your plugin works:

```python
from app.services.dialers.registry import DialerRegistry
from app.services.dialers.plivo.service import PlivoDialerService

# Register
DialerRegistry.register("plivo", PlivoDialerService)

# Get and use
dialer_class = DialerRegistry.get("plivo")
dialer = dialer_class()

# Validate config
assert dialer.validate_config(), "Plivo config invalid"

# Test audio conversion
pcm = dialer.audio_converter.dialer_to_pcm("base64_audio")
assert len(pcm) > 0, "Audio conversion failed"

print("✅ Plivo plugin working!")
```

## Troubleshooting

### "Dialer 'xxx' not registered"
- Make sure you called `DialerRegistry.register("xxx", XxxDialerService)` in [app/main.py](app/main.py:35-37)
- Check that the dialer name in URL matches registered name (case-insensitive)

### "xxx credentials not configured"
- Add required environment variables to `.env`
- Restart the server after updating `.env`
- Check `validate_config()` implementation in your service

### Audio issues
- Verify your `AudioConverter` handles the correct format
- Check ElevenLabs expects PCM 16kHz mono 16-bit
- Test conversion with sample audio files

### WebSocket connection fails
- Ensure your `MessageBuilder.build_connection_response()` returns correct format
- Check WebSocket URL is publicly accessible (use ngrok for testing)
- Verify your dialer's WebSocket protocol matches your handler

## Architecture Diagram

```
User API Call
    ↓
Generic Router (/{dialer_name}/outbound-call)
    ↓
DialerRegistry.get(dialer_name)
    ↓
DialerService Plugin (Twilio/Plivo/etc.)
    ├── AudioConverter
    ├── MessageBuilder
    ├── ConnectionHandler
    └── API Integration
    ↓
Dialer API (Twilio/Plivo/etc.)
    ↓
Customer Phone
    ↓
WebSocket Connection
    ↓
Generic Router (/{dialer_name}/media-stream)
    ↓
DialerService Plugin
    ├── Parse dialer messages (ConnectionHandler)
    ├── Convert audio (AudioConverter)
    └── Forward to ElevenLabs
    ↓
ElevenLabs Agent
    ↓
AI Conversation!
```

## Contributing

To contribute a new dialer plugin:
1. Follow the steps above to implement all interfaces
2. Add tests for your plugin
3. Update this guide with dialer-specific notes
4. Submit a pull request

## Support

For issues:
- **Plugin problems**: Check implementation of abstract interfaces
- **Audio issues**: Verify audio format conversion
- **Connection issues**: Check WebSocket handling
- **API errors**: Validate credentials and endpoint URLs

Happy dialer abstraction! 🎉
