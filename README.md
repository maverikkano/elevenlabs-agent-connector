# ElevenLabs Agent Connector

FastAPI service that connects external dialers (like N8N) to ElevenLabs conversational AI agents. The service receives webhook calls, creates signed ElevenLabs URLs, and initiates WebSocket-based voice conversations using local microphone input.

## Features

- **Webhook Integration**: Receive calls from N8N and external dialers
- **ElevenLabs Integration**: Automatically generate signed URLs for agent conversations
- **Real-time Audio**: WebSocket-based audio streaming with local microphone
- **API Key Authentication**: Secure endpoints with API key validation
- **Background Processing**: Non-blocking audio streaming with FastAPI background tasks
- **Comprehensive Logging**: Structured logging for debugging and monitoring

## Architecture

```
External Dialer/N8N
        ↓
   [POST /webhook/initiate-call]
        ↓
   API Key Validation
        ↓
   Get Signed URL from ElevenLabs
        ↓
   Establish WebSocket Connection
        ↓
   Start Microphone Audio Stream
        ↓
   Return Session Info
```

## Prerequisites

- Python 3.9 or higher
- ElevenLabs API key
- Active ElevenLabs conversational AI agent
- Microphone for audio input

## Installation

1. **Clone or navigate to the project directory**

```bash
cd elevenlabs-agent-connector
```

2. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```bash
# ElevenLabs Configuration
ELEVENLABS_API_KEY=your_actual_elevenlabs_api_key

# Webhook Authentication (comma-separated)
API_KEYS=your_secret_key_1,your_secret_key_2

# Application Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
```

## Running the Application

### Development Mode

```bash
python -m app.main
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
# Set environment to production in .env
ENVIRONMENT=production

# Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The service will be available at `http://localhost:8000`

## API Endpoints

### Health Check

**GET** `/health`

Check if the service is running.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-17T12:00:00.000000"
}
```

### Initiate Call

**POST** `/webhook/initiate-call`

Initiate a conversation with an ElevenLabs agent.

**Headers:**
```
X-API-Key: your_api_key_here
Content-Type: application/json
```

**Request Body:**
```json
{
  "agent_id": "your_elevenlabs_agent_id",
  "session_id": "optional_session_identifier",
  "metadata": {
    "caller_id": "+1234567890",
    "custom_field": "value"
  }
}
```

**Response (Success - 200):**
```json
{
  "success": true,
  "session_id": "uuid-or-provided-session-id",
  "websocket_url": "wss://...",
  "message": "Call initiated successfully. Audio streaming started.",
  "timestamp": "2025-12-17T12:00:00.000000"
}
```

**Response (Unauthorized - 401):**
```json
{
  "success": false,
  "error": "Invalid or missing API key",
  "detail": null,
  "timestamp": "2025-12-17T12:00:00.000000"
}
```

**Response (Error - 500):**
```json
{
  "success": false,
  "error": "Failed to connect to ElevenLabs",
  "detail": "Error details here",
  "timestamp": "2025-12-17T12:00:00.000000"
}
```

### API Documentation

When running in development mode, interactive API documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## N8N Integration

To integrate with N8N:

1. **Add an HTTP Request node** in your N8N workflow

2. **Configure the node:**
   - **Method**: POST
   - **URL**: `http://your-server:8000/webhook/initiate-call`
   - **Authentication**: None (we use custom header)
   - **Headers**:
     - `X-API-Key`: Your API key
     - `Content-Type`: application/json
   - **Body**:
     ```json
     {
       "agent_id": "{{ $json.agent_id }}",
       "session_id": "{{ $json.session_id }}",
       "metadata": {
         "source": "n8n",
         "workflow_id": "{{ $workflow.id }}"
       }
     }
     ```

3. **Handle the response** in subsequent nodes

## Testing

### Using cURL

```bash
curl -X POST http://localhost:8000/webhook/initiate-call \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "your_agent_id",
    "session_id": "test-session-123",
    "metadata": {
      "test": true
    }
  }'
```

### Using Python

```python
import requests

url = "http://localhost:8000/webhook/initiate-call"
headers = {
    "X-API-Key": "your_api_key_here",
    "Content-Type": "application/json"
}
data = {
    "agent_id": "your_agent_id",
    "session_id": "test-session-123",
    "metadata": {
        "test": True
    }
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

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
├── .env                           # Environment variables (create from .env.example)
├── .env.example                   # Environment template
├── .gitignore                     # Git ignore rules
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Configuration

All configuration is managed through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ELEVENLABS_API_KEY` | Your ElevenLabs API key | Required |
| `API_KEYS` | Comma-separated webhook API keys | Required |
| `ENVIRONMENT` | Environment mode (development/production) | development |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | INFO |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8000 |

## Audio Configuration

The audio service is configured for optimal compatibility with ElevenLabs:

- **Sample Rate**: 16kHz
- **Channels**: Mono
- **Format**: 16-bit PCM
- **Chunk Size**: 100ms

These settings are defined in `app/services/audio_service.py` and can be adjusted if needed.

## Security Considerations

1. **API Keys**: Never commit `.env` file. Use different API keys for development and production.
2. **ElevenLabs Key**: Keep your ElevenLabs API key secure. It's never logged or exposed in responses.
3. **CORS**: Disabled in production. Only enabled in development mode.
4. **HTTPS**: Use HTTPS in production (configure via reverse proxy like Nginx).

## Troubleshooting

### Microphone Access Issues

If you get microphone permission errors:
- Ensure your terminal/IDE has microphone access permissions
- On macOS: System Preferences > Security & Privacy > Microphone
- On Linux: Check ALSA/PulseAudio configuration

### ElevenLabs API Errors

- Verify your API key is correct in `.env`
- Check that the agent_id exists in your ElevenLabs account
- Ensure you have sufficient API credits

### WebSocket Connection Failures

- Check firewall settings
- Verify network connectivity
- Ensure signed URL is used within 15 minutes

### Logs

Check application logs for detailed error information:
```bash
# The application logs to stdout
# Adjust LOG_LEVEL in .env for more/less verbosity
```

## Dependencies

- **FastAPI**: Modern web framework for APIs
- **Uvicorn**: ASGI server
- **Pydantic**: Data validation
- **httpx**: Async HTTP client
- **websockets**: WebSocket client/server
- **sounddevice**: Audio I/O library
- **numpy**: Audio data processing

## Future Enhancements

- [ ] Audio playback for agent responses
- [ ] Session management and tracking
- [ ] Multiple concurrent conversations
- [ ] Audio recording and storage
- [ ] Metrics and monitoring
- [ ] Rate limiting
- [ ] Database integration for session persistence

## License

MIT

## Support

For issues and questions:
- ElevenLabs Documentation: https://elevenlabs.io/docs
- FastAPI Documentation: https://fastapi.tiangolo.com

## Acknowledgments

Built with:
- [ElevenLabs Conversational AI](https://elevenlabs.io/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [N8N](https://n8n.io/)
