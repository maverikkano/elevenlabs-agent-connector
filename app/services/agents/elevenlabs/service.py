"""
ElevenLabs Agent Service
"""

import logging
import httpx
import websockets
from typing import Dict, Any, Optional

from app.config import settings
from app.services.agents.base import AgentService, AgentStream, AgentMessageHandler
from app.services.agents.elevenlabs.message_handler import ElevenLabsMessageHandler
from app.services.agents.elevenlabs.stream import ElevenLabsAgentStream

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsAgentService(AgentService):
    """
    Factory for ElevenLabs agent connections.
    """
    
    def __init__(self):
        self._message_handler = ElevenLabsMessageHandler()

    def get_message_handler(self) -> AgentMessageHandler:
        return self._message_handler

    def get_agent_name(self) -> str:
        return "elevenlabs"

    def validate_config(self) -> bool:
        """Check if API key is configured"""
        is_valid = bool(settings.elevenlabs_api_key)
        if not is_valid:
            logger.error("ElevenLabs API key is missing")
        return is_valid

    async def _get_signed_url(self, agent_id: str) -> str:
        """
        Get signed WebSocket URL from ElevenLabs API.
        """
        url = f"{ELEVENLABS_API_BASE}/convai/conversation/get-signed-url"
        headers = {"xi-api-key": settings.elevenlabs_api_key}
        params = {"agent_id": agent_id}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params, timeout=10.0)
                response.raise_for_status()

                data = response.json()
                signed_url = data.get("signed_url")

                if not signed_url:
                    raise ValueError("No signed URL in response from ElevenLabs")

                return signed_url

        except httpx.HTTPStatusError as e:
            raise ValueError(f"ElevenLabs API error: {e.response.status_code} - {e.response.text}") from e
        except Exception as e:
            raise ValueError(f"Failed to get signed URL: {str(e)}") from e

    async def connect(
        self, 
        agent_id: str, 
        dynamic_variables: Dict[str, Any]
    ) -> AgentStream:
        """
        Connect to ElevenLabs agent.
        1. Get signed URL
        2. Open WebSocket
        3. Return initialized stream
        """
        if not self.validate_config():
            raise ValueError("ElevenLabs configuration invalid")

        logger.info(f"Connecting to ElevenLabs agent {agent_id}...")
        
        try:
            # 1. Get signed URL
            signed_url = await self._get_signed_url(agent_id)
            logger.debug(f"Got signed URL: {signed_url[:30]}...")

            # 2. Connect
            websocket = await websockets.connect(signed_url)
            logger.info("ElevenLabs WebSocket connected")

            # 3. Create Stream
            stream = ElevenLabsAgentStream(
                websocket=websocket,
                message_handler=self._message_handler,
                dynamic_variables=dynamic_variables
            )
            
            return stream

        except Exception as e:
            logger.error(f"Failed to connect to ElevenLabs: {e}")
            raise
