import httpx
import websockets
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsError(Exception):
    """Custom exception for ElevenLabs API errors."""
    pass


async def get_signed_url(agent_id: str) -> str:
    """
    Get a signed WebSocket URL for an ElevenLabs conversational AI agent.

    The signed URL is valid for 15 minutes. The conversation must be initiated
    within this window, though the session can last longer once started.

    Args:
        agent_id: ElevenLabs agent identifier

    Returns:
        str: Signed WebSocket URL for connecting to the agent

    Raises:
        ElevenLabsError: If the API request fails
    """
    url = f"{ELEVENLABS_API_BASE}/convai/conversation/get-signed-url"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key
    }
    params = {
        "agent_id": agent_id
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=10.0)
            response.raise_for_status()

            data = response.json()
            signed_url = data.get("signed_url")

            if not signed_url:
                raise ElevenLabsError("No signed URL in response")

            logger.info(f"Successfully obtained signed URL for agent {agent_id}")
            return signed_url

    except httpx.HTTPStatusError as e:
        error_msg = f"ElevenLabs API error: {e.response.status_code}"
        try:
            error_detail = e.response.json()
            error_msg += f" - {error_detail}"
        except Exception:
            error_msg += f" - {e.response.text}"

        logger.error(error_msg)
        raise ElevenLabsError(error_msg) from e

    except httpx.RequestError as e:
        error_msg = f"Failed to connect to ElevenLabs API: {str(e)}"
        logger.error(error_msg)
        raise ElevenLabsError(error_msg) from e

    except Exception as e:
        error_msg = f"Unexpected error getting signed URL: {str(e)}"
        logger.error(error_msg)
        raise ElevenLabsError(error_msg) from e


async def create_websocket_connection(signed_url: str):
    """
    Create a WebSocket connection to ElevenLabs agent.

    Args:
        signed_url: The signed WebSocket URL from get_signed_url()

    Returns:
        WebSocket connection object

    Raises:
        ElevenLabsError: If WebSocket connection fails
    """
    try:
        logger.info("Establishing WebSocket connection to ElevenLabs agent")
        websocket = await websockets.connect(signed_url)
        logger.info("WebSocket connection established successfully")
        return websocket

    except Exception as e:
        error_msg = f"Failed to establish WebSocket connection: {str(e)}"
        logger.error(error_msg)
        raise ElevenLabsError(error_msg) from e
