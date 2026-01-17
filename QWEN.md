# ElevenLabs Agent Connector - Development Context

## Project Overview

The ElevenLabs Agent Connector is a FastAPI service that bridges external dialers (such as N8N) with ElevenLabs conversational AI agents. The service receives webhook calls, generates signed ElevenLabs URLs, and establishes WebSocket-based voice conversations using local microphone input for real-time audio streaming.

## Architecture & Components

### Core Services
- `app/main.py` - FastAPI application entry point with CORS configuration for development
- `app/config.py` - Settings management using Pydantic Settings with environment variable loading
- `app/models.py` - Pydantic models for request/response validation
- `app/auth.py` - API key authentication middleware
- `app/routers/webhooks.py` - Webhook endpoint handler
- `app/services/elevenlabs_service.py` - ElevenLabs API integration for signed URLs and WebSocket connections
- `app/services/audio_service.py` - Real-time audio streaming using microphone input

### Key Features
- Webhook integration for receiving calls from external systems like N8N
- ElevenLabs conversational AI integration via signed URLs
- Real-time audio streaming with WebSocket protocol
- API key authentication for security
- Background audio processing to prevent blocking
- Comprehensive structured logging

## Environment Configuration

The service relies on environment variables loaded from `.env`:
- `ELEVENLABS_API_KEY` - Your ElevenLabs API key (required)
- `API_KEYS` - Comma-separated list of allowed webhook API keys (required)
- `ENVIRONMENT` - Development/production mode (default: development)
- `LOG_LEVEL` - Logging level (default: INFO)
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)

## Audio Configuration

The audio service is optimized for ElevenLabs compatibility:
- Sample Rate: 16kHz
- Channels: Mono
- Format: 16-bit PCM
- Chunk Size: 100ms duration (1600 samples)

## Audio Service Flow

The `audio_service.py` implements the following flow:
1. Initializes a `MicrophoneStreamer` with audio configuration
2. Sends an initialization message containing dynamic variables to ElevenLabs
3. Captures microphone input through a callback function and streams to WebSocket
4. Receives audio responses from the agent and plays them through speakers
5. Handles ping/pong events and interruption detection

## API Endpoints

### Health Check
- GET `/health` - Returns service health status

### Initiate Call
- POST `/webhook/initiate-call` - Initiates a conversation with an ElevenLabs agent
  - Headers: `X-API-Key` (required), `Content-Type: application/json`
  - Request body: Contains `agent_id`, optional `session_id`, and `metadata`
  - Response: Contains session info and WebSocket URL

## Dependencies

Primary dependencies defined in `requirements.txt`:
- FastAPI: Web framework
- Uvicorn: ASGI server
- Pydantic: Data validation
- Pydantic Settings: Configuration management
- httpx: Async HTTP client
- websockets: WebSocket client/server
- sounddevice: Audio I/O library
- numpy: Audio data processing

## Development Commands

### Running the Application
- Development: `python -m app.main` or `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Production: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4`

### Testing
- Interactive API docs available at `/docs` in development mode
- Use cURL or Python requests for programmatic testing

## Security Considerations

- API keys are validated through the `verify_api_key` dependency
- ElevenLabs API key is kept secure and never exposed in logs/responses
- CORS is disabled in production for security
- Use HTTPS in production environments

## Project Structure

```
elevenlabs-agent-connector/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration management
│   ├── models.py                  # Pydantic models
│   ├── auth.py                    # API key authentication
│   ├── routers/
│   │   ├── __init__.py
│   │   └── webhooks.py            # Webhook endpoints
│   └── services/
│       ├── __init__.py
│       ├── elevenlabs_service.py  # ElevenLabs API integration
│       └── audio_service.py       # Audio streaming
├── .env                           # Environment variables
├── .env.example                   # Environment template
├── requirements.txt               # Python dependencies
└── README.md
```

## Future Enhancements (Planned)

- Audio playback for agent responses
- Session management and tracking
- Multiple concurrent conversations
- Audio recording and storage
- Metrics and monitoring
- Rate limiting
- Database integration

## Troubleshooting

Common issues include microphone permissions, ElevenLabs API key validity, and WebSocket connection problems. Check logs with appropriate log levels set in the environment configuration.