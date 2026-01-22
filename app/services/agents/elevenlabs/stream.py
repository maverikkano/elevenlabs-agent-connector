"""
ElevenLabs Agent Stream
"""

import logging
import json
import asyncio
from typing import AsyncGenerator, Dict, Any
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from app.services.agents.base import AgentStream
from app.services.agents.types import AgentEvent, AgentEventTypes
from app.services.agents.elevenlabs.message_handler import ElevenLabsMessageHandler

logger = logging.getLogger(__name__)


class ElevenLabsAgentStream(AgentStream):
    """
    ElevenLabs implementation of AgentStream.
    Wraps a WebSocket connection to the ElevenLabs Conversational AI API.
    """
    
    def __init__(
        self, 
        websocket: WebSocketClientProtocol, 
        message_handler: ElevenLabsMessageHandler,
        dynamic_variables: Dict[str, Any]
    ):
        self.ws = websocket
        self.message_handler = message_handler
        self.dynamic_variables = dynamic_variables
        self.auto_ping_pong = True

    async def initialize(self) -> None:
        """
        Send the initial conversation configuration to ElevenLabs.
        """
        logger.info("Initializing ElevenLabs session...")
        init_msg = self.message_handler.build_initialization_message(self.dynamic_variables)
        await self.ws.send(init_msg)
        logger.info("ElevenLabs session initialized.")

    async def send_audio(self, audio_data: bytes) -> None:
        """
        Send audio chunk to ElevenLabs.
        """
        try:
            msg = self.message_handler.build_audio_message(audio_data)
            await self.ws.send(msg)
        except ConnectionClosed:
            logger.warning("ElevenLabs WebSocket closed while sending audio")
        except Exception as e:
            logger.error(f"Error sending audio to ElevenLabs: {e}")
            raise

    async def receive(self) -> AsyncGenerator[AgentEvent, None]:
        """
        Yield events from ElevenLabs.
        Handles auto-ping if enabled.
        """
        try:
            async for message in self.ws:
                event = self.message_handler.parse_message(message)

                # Auto-handle ping/pong
                if self.auto_ping_pong and event.type == AgentEventTypes.PONG:
                    # In ElevenLabs, we receive "ping" and send "pong" (handled in logic below)
                    # Actually, message_handler parses "ping" type as PONG event type for internal consistency
                    # But specific to ElevenLabs:
                    # Server sends: {"type": "ping", "event_id": ...}
                    # Client responds: {"type": "pong", "event_id": ...}
                    
                    event_id = event.data
                    pong_response = json.dumps({
                        "type": "pong",
                        "event_id": event_id
                    })
                    await self.ws.send(pong_response)
                    logger.debug(f"Responded to ping (event_id: {event_id})")
                    continue

                yield event

        except ConnectionClosed:
            logger.info("ElevenLabs WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error receiving from ElevenLabs: {e}")
            yield AgentEvent(type=AgentEventTypes.ERROR, data=str(e), error=e)

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self.ws:
            await self.ws.close()
            logger.info("ElevenLabs connection closed")
