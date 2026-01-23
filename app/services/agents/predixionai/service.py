"""
PredixionAI Voice Agent Service
"""

import logging
import httpx
import websockets
from typing import Dict, Any

from app.config import settings
from app.services.agents.base import AgentService, AgentStream, AgentMessageHandler
from app.services.agents.predixionai.message_handler import PredixionAIMessageHandler
from app.services.agents.predixionai.stream import PredixionAIAgentStream

logger = logging.getLogger(__name__)


class PredixionAIAgentService(AgentService):
    """
    Factory for PredixionAI Voice agent connections.
    """

    def __init__(self):
        self._message_handler = PredixionAIMessageHandler()

    def get_message_handler(self) -> AgentMessageHandler:
        return self._message_handler

    def get_agent_name(self) -> str:
        return "predixionai-voice"

    def validate_config(self) -> bool:
        """
        Check if PredixionAI is properly configured.
        """
        # API URL must be set (defaults to localhost via settings if not overridden)
        return bool(settings.predixionai_api_url)

    async def _create_session(
        self,
        agent_id: str,
        dynamic_variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a PredixionAI session by posting customer data.
        """
        url = f"{settings.predixionai_api_url}/call-websocket"

        # Map dynamic_variables to PredixionAI's expected format
        payload = {
            "customer_phone": dynamic_variables.get("customer_phone", ""),
            "customer_data": {
                "first_name": dynamic_variables.get("first_name", ""),
                "last_name": dynamic_variables.get("last_name", ""),
                "outstanding_balance": dynamic_variables.get("outstanding_balance", 0),
                "next_payment_date": dynamic_variables.get("next_payment_date", ""),
                "days_overdue": dynamic_variables.get("days_overdue", 0),
                # Include any additional customer_data fields
                **dynamic_variables.get("customer_data", {})
            },
            "dialer_id": agent_id
        }

        # Auth headers if key is present
        headers = {"Content-Type": "application/json"}
        if settings.predixionai_api_key:
            headers["Authorization"] = f"Bearer {settings.predixionai_api_key}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()

                data = response.json()

                websocket_url = data.get("websocket_url")
                if not websocket_url:
                    raise ValueError("No websocket_url in response from PredixionAI")

                logger.info(f"PredixionAI session created: call_id={data.get('call_id')}")
                return data

        except httpx.HTTPStatusError as e:
            raise ValueError(
                f"PredixionAI API error: {e.response.status_code} - {e.response.text}"
            ) from e
        except Exception as e:
            raise ValueError(f"Failed to create PredixionAI session: {str(e)}") from e

    async def connect(
        self,
        agent_id: str,
        dynamic_variables: Dict[str, Any]
    ) -> AgentStream:
        """
        Connect to PredixionAI Voice agent.
        """
        if not self.validate_config():
            raise ValueError("PredixionAI configuration invalid")

        logger.info(f"Connecting to PredixionAI Voice agent (agent_id: {agent_id})...")

        try:
            # 1. Create session via HTTP POST
            session_data = await self._create_session(agent_id, dynamic_variables)

            websocket_url = session_data["websocket_url"]
            call_id = session_data["call_id"]

            logger.debug(f"Got WebSocket URL: {websocket_url}")

            # 2. Connect to WebSocket
            websocket = await websockets.connect(websocket_url)
            logger.info(f"PredixionAI WebSocket connected (call_id: {call_id})")

            # 3. Create Stream
            stream = PredixionAIAgentStream(
                websocket=websocket,
                message_handler=self._message_handler,
                call_id=call_id,
                dynamic_variables=dynamic_variables
            )

            return stream

        except Exception as e:
            logger.error(f"Failed to connect to PredixionAI: {e}")
            raise
