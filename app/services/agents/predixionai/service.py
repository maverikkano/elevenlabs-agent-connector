"""
PredixionAI Agent Service

Factory for creating PredixionAI LiveKit-based agent connections.
"""

import logging
import httpx
import uuid
from typing import Dict, Any

from app.config import settings
from app.services.agents.base import AgentService, AgentStream, AgentMessageHandler
from app.services.agents.predixionai.message_handler import PredixionAIMessageHandler
from app.services.agents.predixionai.stream import PredixionAIAgentStream

logger = logging.getLogger(__name__)


class PredixionAIAgentService(AgentService):
    """
    Factory for PredixionAI agent connections.
    Handles HTTP POST to JobDispatch and LiveKit room creation.
    """

    def __init__(self):
        logger.debug("Initializing PredixionAIAgentService")
        self._message_handler = PredixionAIMessageHandler()
        logger.debug("PredixionAIAgentService initialized")

    def get_message_handler(self) -> AgentMessageHandler:
        """Return the message handler instance for this agent."""
        return self._message_handler

    def get_agent_name(self) -> str:
        """Return agent provider name."""
        return "predixionai"

    def validate_config(self) -> bool:
        """
        Check if PredixionAI API configuration is valid.

        Returns:
            True if API URL is configured, False otherwise
        """
        logger.debug("Validating PredixionAI configuration")

        is_valid = bool(settings.predixionai_api_url)

        if not is_valid:
            logger.error("❌ PredixionAI API URL is missing (PREDIXIONAI_API_URL)")
        else:
            logger.debug(f"✅ PredixionAI config valid: URL={settings.predixionai_api_url}")

        return is_valid

    async def _call_jobdispatch(
        self,
        agent_id: str,
        dynamic_variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call PredixionAI JobDispatch to create LiveKit room.

        Args:
            agent_id: Agent identifier (may be used in customer_data)
            dynamic_variables: Customer context and call metadata

        Returns:
            dict: Response containing room_token, websocket_url, room_name, etc.

        Raises:
            ValueError: If API call fails or response is invalid
        """
        # Generate unique call ID for gateway
        gateway_call_id = f"gw-{uuid.uuid4().hex[:12]}"

        # Build JobDispatch endpoint URL
        url = f"{settings.predixionai_api_url.rstrip('/')}/call-gateway"

        # Extract and clean phone number
        raw_phone = dynamic_variables.get("customer_phone") or dynamic_variables.get("to_number", "")

        # Strip country code prefix (+91 or 91) and any non-digit characters
        customer_phone = raw_phone.replace("+91", "").replace("91", "", 1).replace("+", "").strip()

        # Validate phone number
        if not customer_phone or len(customer_phone) != 10 or not customer_phone.isdigit():
            logger.error(f"[{gateway_call_id}] ❌ Invalid phone number: raw='{raw_phone}', cleaned='{customer_phone}'")
            raise ValueError(f"Invalid phone number format: {raw_phone}. Expected 10-digit Indian mobile number.")

        logger.debug(f"[{gateway_call_id}] Phone number cleaned: '{raw_phone}' → '{customer_phone}'")

        # Build customer data without phone fields (they're at top level)
        customer_data = {k: v for k, v in dynamic_variables.items() if k not in ["customer_phone", "to_number"]}

        # Build request payload
        payload = {
            "gateway_call_id": gateway_call_id,
            "customer_phone": customer_phone,  # Clean 10-digit phone
            "customer_data": customer_data      # All other fields
        }

        # Build headers
        headers = {
            "Content-Type": "application/json"
        }

        logger.info(f"[{gateway_call_id}] 📞 Calling PredixionAI JobDispatch")
        logger.debug(f"[{gateway_call_id}] POST {url}")
        logger.debug(f"[{gateway_call_id}] Payload: gateway_call_id={gateway_call_id}, customer_phone={customer_phone}")
        logger.debug(f"[{gateway_call_id}] Customer data keys: {list(payload['customer_data'].keys())}")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                logger.debug(f"[{gateway_call_id}] Sending HTTP POST request...")

                response = await client.post(url, json=payload, headers=headers)

                logger.debug(f"[{gateway_call_id}] Response status: {response.status_code}")

                response.raise_for_status()

                data = response.json()
                logger.info(f"[{gateway_call_id}] ✅ JobDispatch response received")
                logger.debug(f"[{gateway_call_id}] Response data keys: {list(data.keys())}")

                # Validate response contains required fields
                required_fields = ["room_token", "websocket_url"]
                missing_fields = [field for field in required_fields if field not in data]

                if missing_fields:
                    error_msg = f"JobDispatch response missing fields: {missing_fields}"
                    logger.error(f"[{gateway_call_id}] ❌ {error_msg}")
                    logger.debug(f"[{gateway_call_id}] Full response: {data}")
                    raise ValueError(error_msg)

                # Log success details
                room_name = data.get("room_name", "unknown")
                logger.info(f"[{gateway_call_id}] 🎉 LiveKit room created: {room_name}")
                logger.debug(f"[{gateway_call_id}] WebSocket URL: {data['websocket_url']}")

                # Add call_id to response for tracking
                data["gateway_call_id"] = gateway_call_id

                return data

        except httpx.HTTPStatusError as e:
            error_msg = f"JobDispatch API error: {e.response.status_code}"
            logger.error(f"[{gateway_call_id}] ❌ {error_msg}", exc_info=True)
            logger.error(f"[{gateway_call_id}] Response body: {e.response.text}")
            raise ValueError(f"{error_msg} - {e.response.text}") from e

        except httpx.TimeoutException as e:
            error_msg = "JobDispatch API timeout (15s)"
            logger.error(f"[{gateway_call_id}] ❌ {error_msg}", exc_info=True)
            raise ValueError(error_msg) from e

        except httpx.RequestError as e:
            error_msg = f"JobDispatch API request failed: {str(e)}"
            logger.error(f"[{gateway_call_id}] ❌ {error_msg}", exc_info=True)
            raise ValueError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error calling JobDispatch: {str(e)}"
            logger.error(f"[{gateway_call_id}] ❌ {error_msg}", exc_info=True)
            raise ValueError(error_msg) from e

    async def connect(
        self,
        agent_id: str,
        dynamic_variables: Dict[str, Any]
    ) -> AgentStream:
        """
        Establish connection to PredixionAI agent via LiveKit.

        Flow:
        1. Validate configuration
        2. Call JobDispatch to create LiveKit room
        3. Create AgentStream with room token
        4. Return stream (caller will call initialize())

        Args:
            agent_id: Identifier for the specific agent/persona
            dynamic_variables: Context variables for the session

        Returns:
            An initialized PredixionAIAgentStream instance

        Raises:
            ValueError: If configuration invalid or connection fails
        """
        logger.info(f"🤖 Connecting to PredixionAI agent: {agent_id}")
        logger.debug(f"Dynamic variables: {list(dynamic_variables.keys())}")

        # Step 1: Validate configuration
        if not self.validate_config():
            error_msg = "PredixionAI configuration invalid"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        try:
            # Step 2: Call JobDispatch to create room
            logger.info("📡 Calling JobDispatch to create LiveKit room...")
            response = await self._call_jobdispatch(agent_id, dynamic_variables)

            room_token = response["room_token"]
            websocket_url = response["websocket_url"]
            gateway_call_id = response["gateway_call_id"]

            logger.info(f"[{gateway_call_id}] ✅ Room details received")

            # Step 3: Create stream
            logger.debug(f"[{gateway_call_id}] Creating PredixionAIAgentStream")
            stream = PredixionAIAgentStream(
                room_token=room_token,
                websocket_url=websocket_url,
                message_handler=self._message_handler,
                call_id=gateway_call_id,
                dynamic_variables=dynamic_variables
            )

            logger.info(f"[{gateway_call_id}] ✅ PredixionAI stream created successfully")
            logger.debug(f"[{gateway_call_id}] Stream ready for initialization")

            return stream

        except Exception as e:
            logger.error(f"❌ Failed to connect to PredixionAI: {e}", exc_info=True)
            raise
