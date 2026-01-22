"""
ElevenLabs Message Handler
"""

import json
import base64
import logging
from typing import Any, Dict
from app.services.agents.base import AgentMessageHandler
from app.services.agents.types import AgentEvent, AgentEventTypes

logger = logging.getLogger(__name__)


class ElevenLabsMessageHandler(AgentMessageHandler):
    """Handles ElevenLabs-specific message formatting"""

    def build_audio_message(self, audio_data: bytes) -> str:
        """
        Build ElevenLabs audio message.
        Expected format: JSON with "user_audio_chunk" containing base64 audio.
        """
        # Encode PCM bytes to base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return json.dumps({
            "user_audio_chunk": audio_base64
        })

    def build_initialization_message(self, dynamic_variables: Dict[str, Any]) -> str:
        """
        Build ElevenLabs initialization message.
        Expected format: JSON with "conversation_initiation_client_data".
        """
        return json.dumps({
            "type": "conversation_initiation_client_data",
            "conversation_config_override": {
                "agent": {
                    "prompt": {
                        "prompt": dynamic_variables.get("prompt")
                    },
                    "first_message": dynamic_variables.get("first_message"),
                    "language": dynamic_variables.get("language")
                }
            } if dynamic_variables.get("prompt") or dynamic_variables.get("first_message") else None,
            "dynamic_variables": dynamic_variables
        })

    def parse_message(self, message: Any) -> AgentEvent:
        """
        Parse incoming ElevenLabs message to standardized AgentEvent.
        """
        if not isinstance(message, str):
            logger.warning(f"Received non-string message from ElevenLabs: {type(message)}")
            return AgentEvent(type=AgentEventTypes.ERROR, data="Invalid message format")

        try:
            data = json.loads(message)
            msg_type = data.get("type")

            # 1. Audio Event
            if msg_type == "audio":
                audio_event = data.get("audio_event", {})
                audio_base64 = audio_event.get("audio_base_64")
                
                if audio_base64:
                    audio_bytes = base64.b64decode(audio_base64)
                    return AgentEvent(type=AgentEventTypes.AUDIO, data=audio_bytes)
                
            # 2. Agent Response (Text)
            elif msg_type == "agent_response_event":
                response = data.get("agent_response_event", {}).get("response", "")
                return AgentEvent(type=AgentEventTypes.TEXT, data=response)

            # 3. User Transcription
            elif msg_type == "user_transcription_event":
                transcription = data.get("user_transcription_event", {}).get("user_transcription", "")
                return AgentEvent(
                    type=AgentEventTypes.TRANSCRIPTION, 
                    data=transcription,
                    metadata={"source": "user"}
                )

            # 4. Interruption
            elif msg_type == "interruption_event":
                return AgentEvent(type=AgentEventTypes.INTERRUPTION, data=True)

            # 5. Ping/Pong
            elif msg_type == "ping":
                return AgentEvent(
                    type=AgentEventTypes.PONG, 
                    data=data.get("event_id"),
                    metadata={"ping_event": data}
                )

            # 6. Error (Custom handling if needed, though ElevenLabs sends errors differently sometimes)
            elif msg_type == "error":
                return AgentEvent(
                    type=AgentEventTypes.ERROR, 
                    data=data.get("message", "Unknown error"),
                    error=Exception(data.get("message"))
                )

            # Default / Ignored events
            return AgentEvent(
                type=AgentEventTypes.METADATA, 
                data=data,
                metadata={"original_type": msg_type}
            )

        except json.JSONDecodeError:
            return AgentEvent(
                type=AgentEventTypes.ERROR, 
                data="Failed to decode JSON",
                error=Exception("JSON decode error")
            )
        except Exception as e:
            logger.error(f"Error parsing ElevenLabs message: {e}")
            return AgentEvent(
                type=AgentEventTypes.ERROR, 
                data=str(e),
                error=e
            )
