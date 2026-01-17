# ElevenLabs Agent Connector - Gemini Context

## Project Overview

**Name:** ElevenLabs Agent Connector
**Purpose:** A FastAPI middleware service that connects external dialers (specifically N8N) to ElevenLabs Conversational AI agents. It handles webhook requests to initiate calls, manages authentication, and establishes bidirectional audio streaming between the local microphone and ElevenLabs via WebSockets.

**Key Technologies:**
*   **Language:** Python 3.9+
*   **Framework:** FastAPI (Web), Uvicorn (Server)
*   **Networking:** `httpx` (HTTP Client), `websockets` (Real-time audio)
*   **Audio:** `sounddevice` (Microphone I/O), `numpy` (Audio processing)
*   **Validation:** Pydantic

## Architecture

1.  **Trigger:** External service (N8N) sends a POST request to `/webhook/initiate-call`.
2.  **Auth:** Service validates `X-API-Key`.
3.  **Setup:** Service requests a signed WebSocket URL from ElevenLabs API using the provided `agent_id`.
4.  **Streaming:** Service connects to the signed URL and pipes audio from the local machine's microphone to the agent, and (planned) agent audio back to speakers.

## Environment & Configuration

Configuration is managed via `app/config.py` using `pydantic-settings`.
Create a `.env` file based on `.env.example`:

```ini
# Core
ELEVENLABS_API_KEY=your_key_here
API_KEYS=client_secret_1,client_secret_2

# Server
ENVIRONMENT=development  # or production
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
```

## Development Workflow

### 1. Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Running

**Development (Hot Reload):**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Production:**
```bash
python -m app.main
# OR
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. API Usage

**Initiate Call:**
`POST /webhook/initiate-call`
Headers: `X-API-Key: <key>`
Body:
```json
{
  "agent_id": "<elevenlabs-agent-id>",
  "session_id": "optional-id",
  "metadata": { ... }
}
```

## Key Files & Directories

*   **`app/main.py`**: Application entry point, global exception handling, and startup/shutdown logic.
*   **`app/config.py`**: Environment variable parsing and validation.
*   **`app/routers/webhooks.py`**: Handles the incoming HTTP POST requests from dialers.
*   **`app/services/audio_service.py`**: Manages low-level audio I/O using `sounddevice` (likely non-blocking/threaded).
*   **`app/services/elevenlabs_service.py`**: Wrapper for ElevenLabs API interactions (getting signed URLs).

## Important Implementation Details

*   **Hardware Dependency:** This service requires a functional audio input device (microphone) on the host machine. It is not a pure cloud service; it acts as a local bridge.
*   **Concurrency:** Uses FastAPI's `BackgroundTasks` (implied by README) or async handlers to ensure the webhook returns quickly while the call session persists.
*   **Security:** Uses a custom header `X-API-Key` for client authentication, distinct from the `ELEVENLABS_API_KEY` used for upstream services.
