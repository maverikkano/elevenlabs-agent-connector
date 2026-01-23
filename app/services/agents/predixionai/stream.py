"""
PredixionAI Voice Agent Stream
"""

import logging
import json
import asyncio
from typing import AsyncGenerator, Dict, Any
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed

from app.services.agents.base import AgentStream
from app.services.agents.types import AgentEvent, AgentEventTypes
from app.services.agents.predixionai.message_handler import PredixionAIMessageHandler

logger = logging.getLogger(__name__)


class PredixionAIAgentStream(AgentStream):
    """
    PredixionAI implementation of AgentStream.
    Wraps a WebSocket connection to the PredixionAI Voice API.
    """

    def __init__(
        self,
        websocket: WebSocketClientProtocol,
        message_handler: PredixionAIMessageHandler,
        call_id: str,
        dynamic_variables: Dict[str, Any]
    ):
        self.ws = websocket
        self.message_handler = message_handler
        self.call_id = call_id
        self.dynamic_variables = dynamic_variables
        self.auto_ping_pong = True

    async def initialize(self) -> None:
        """
        Initialize the PredixionAI session.
        """
        logger.info(f"Initializing PredixionAI session (call_id: {self.call_id})...")

        init_msg = self.message_handler.build_initialization_message(self.dynamic_variables)

        if init_msg is not None:
            await self.ws.send(init_msg)
            logger.info("PredixionAI session initialization message sent.")
        else:
            logger.info("PredixionAI session ready (no init message required).")

    async def send_audio(self, audio_data: bytes) -> None:
        """
        Send audio chunk to PredixionAI.
        """
        try:
            msg = self.message_handler.build_audio_message(audio_data)
            await self.ws.send(msg)
        except ConnectionClosed:
            logger.warning("PredixionAI WebSocket closed while sending audio")
        except Exception as e:
            logger.error(f"Error sending audio to PredixionAI: {e}")
            raise

    async def receive(self) -> AsyncGenerator[AgentEvent, None]:
        """
        Yield events from PredixionAI.
        """
        try:
            async for message in self.ws:
                event = self.message_handler.parse_message(message)

                # Auto-handle ping/pong
                if self.auto_ping_pong and event.type == AgentEventTypes.PONG:
                    # Respond to ping with pong
                    event_id = event.data
                    pong_response = json.dumps({
                        "type": "pong",
                        "id": event_id
                    })
                    await self.ws.send(pong_response)
                    logger.debug(f"Responded to ping (id: {event_id})")
                    continue

                yield event

        except ConnectionClosed:
            logger.info("PredixionAI WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error receiving from PredixionAI: {e}")
            yield AgentEvent(type=AgentEventTypes.ERROR, data=str(e), error=e)

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self.ws:
            await self.ws.close()
            logger.info(f"PredixionAI connection closed (call_id: {self.call_id})")
