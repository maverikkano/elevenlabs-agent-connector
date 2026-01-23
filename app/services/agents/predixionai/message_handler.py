"""
PredixionAI Voice Message Handler
"""

import json
import base64
import logging
from typing import Any, Dict
from app.services.agents.base import AgentMessageHandler
from app.services.agents.types import AgentEvent, AgentEventTypes

logger = logging.getLogger(__name__)


class PredixionAIMessageHandler(AgentMessageHandler):
    """Handles PredixionAI Voice-specific message formatting"""

    def build_audio_message(self, audio_data: bytes) -> Any:
        """
        Build PredixionAI audio message.
        """
        # Encode PCM bytes to base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        return json.dumps({
            "type": "audio",
            "audio": audio_base64
        })

    def build_initialization_message(self, dynamic_variables: Dict[str, Any]) -> Any:
        """
        Build initialization message.
        PredixionAI receives init data via HTTP POST, so this is mostly a no-op 
        or minimal check.
        """
        return None

    def parse_message(self, message: Any) -> AgentEvent:
        """
        Parse incoming PredixionAI message to standardized AgentEvent.
        """
        # Handle binary audio data
        if isinstance(message, bytes):
            return AgentEvent(type=AgentEventTypes.AUDIO, data=message)

        # Handle string/JSON messages
        if not isinstance(message, str):
            logger.warning(f"Received unexpected message type: {type(message)}")
            return AgentEvent(
                type=AgentEventTypes.ERROR,
                data=f"Unexpected message type: {type(message)}"
            )

        try:
            data = json.loads(message)
            msg_type = data.get("type", "").lower()

            # Audio Event
            if msg_type == "audio":
                audio_data = data.get("audio") or data.get("audio_data")
                if audio_data:
                    if isinstance(audio_data, str):
                        # Base64 encoded
                        audio_bytes = base64.b64decode(audio_data)
                    else:
                        audio_bytes = audio_data
                    return AgentEvent(type=AgentEventTypes.AUDIO, data=audio_bytes)

            # Text/Response Event
            elif msg_type in ["text", "response", "agent_response"]:
                text = data.get("text") or data.get("response") or data.get("message")
                return AgentEvent(type=AgentEventTypes.TEXT, data=text)

            # Transcription Event
            elif msg_type in ["transcription", "user_transcription"]:
                transcription = data.get("transcription") or data.get("text")
                return AgentEvent(
                    type=AgentEventTypes.TRANSCRIPTION,
                    data=transcription,
                    metadata={"source": "user"}
                )

            # Interruption Event
            elif msg_type == "interruption":
                return AgentEvent(type=AgentEventTypes.INTERRUPTION, data=True)

            # Ping/Pong (keep-alive)
            elif msg_type == "ping":
                return AgentEvent(
                    type=AgentEventTypes.PONG,
                    data=data.get("id") or data.get("event_id"),
                    metadata={"ping_event": data}
                )

            # Error Event
            elif msg_type == "error":
                return AgentEvent(
                    type=AgentEventTypes.ERROR,
                    data=data.get("message") or data.get("error") or "Unknown error",
                    error=Exception(data.get("message", "Unknown error"))
                )

            # Default: treat as metadata
            return AgentEvent(
                type=AgentEventTypes.METADATA,
                data=data,
                metadata={"original_type": msg_type}
            )

        except json.JSONDecodeError:
            # May be raw audio or binary data if not valid JSON
            return AgentEvent(
                type=AgentEventTypes.ERROR,
                data="Failed to decode JSON message",
                error=Exception("JSON decode error")
            )
        except Exception as e:
            logger.error(f"Error parsing PredixionAI message: {e}")
            return AgentEvent(
                type=AgentEventTypes.ERROR,
                data=str(e),
                error=e
            )
