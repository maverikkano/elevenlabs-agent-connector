"""
Generic dialer router

Provides dialer-agnostic endpoints that work with any registered dialer plugin.
"""

import logging
import json
import asyncio
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Response
from fastapi.responses import PlainTextResponse

from app.models import InitiateCallRequest
from app.auth import verify_api_key
from app.config import settings
from app.services.dialers.registry import DialerRegistry
from app.services.dialers.context import store_call_context, get_call_context, cleanup_call_context
from app.services.agents.registry import AgentRegistry
from app.services.agents.types import AgentEventTypes

logger = logging.getLogger(__name__)

router = APIRouter()


def build_websocket_url(dialer_name: str) -> str:
    """
    Build WebSocket URL for the specified dialer

    Args:
        dialer_name: Name of the dialer

    Returns:
        WebSocket URL
    """
    protocol = "wss" # if settings.environment == "production" else "ws"
    host = settings.host if settings.host != "0.0.0.0" else "localhost"
    port = settings.port

    # In production, use standard ports
    if settings.environment == "production" and port in [80, 443]:
        return f"{protocol}://{host}/{dialer_name}/media-stream"
    else:
        return f"{protocol}://{host}:{port}/{dialer_name}/media-stream"


@router.post("/{dialer_name}/outbound-call")
async def initiate_outbound_call(
    dialer_name: str,
    request: InitiateCallRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Generic outbound call endpoint for any dialer

    Args:
        dialer_name: Name of the dialer (e.g., "twilio", "plivo")
        request: Call initiation request
        api_key: Validated API key

    Returns:
        Call initiation response with call details
    """
    try:
        # Get dialer service
        dialer_class = DialerRegistry.get(dialer_name)
        dialer = dialer_class()

        # Validate dialer configuration
        if not dialer.validate_config():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{dialer_name.capitalize()} credentials not configured"
            )

        # Extract data from request
        metadata = request.metadata or {}
        to_number = metadata.get("to_number")
        dynamic_variables = metadata.get("dynamic_variables", {})

        if not to_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="to_number is required in metadata"
            )

        # Build WebSocket URL
        websocket_url = build_websocket_url(dialer_name)

        logger.info(f"WebSocket URL for {dialer_name}: {websocket_url}")
        logger.info(f"Initiating outbound call via {dialer_name} to {to_number}")

        # Initiate call using dialer
        result = await dialer.initiate_outbound_call(
            to_number=to_number,
            agent_id=request.agent_id,
            dynamic_variables=dynamic_variables,
            websocket_url=websocket_url
        )

        return result

    except ValueError as e:
        # Dialer not registered
        logger.error(f"Dialer error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error initiating outbound call: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate outbound call: {str(e)}"
        )


@router.post("/{dialer_name}/incoming-call")
async def handle_incoming_call(
    dialer_name: str,
    agent_id: str = None
):
    """
    Generic incoming call webhook for any dialer

    This endpoint handles incoming calls and returns a connection response
    in the dialer's format (TwiML, XML, JSON, etc.)

    Args:
        dialer_name: Name of the dialer (e.g., "twilio", "plivo")
        agent_id: Optional agent ID (can also be passed in request body)

    Returns:
        Connection response in dialer format
    """
    try:
        # Get dialer service
        dialer_class = DialerRegistry.get(dialer_name)
        dialer = dialer_class()

        # Use default agent ID if not provided
        if not agent_id:
            agent_id = "agent_7201keyx3brmfk68gdwytc6a4tna"  # Default from context

        # Hardcoded context for testing (replace with database lookup in production)
        context = {
            "agent_id": agent_id,
            "dynamic_variables": {
                "name": "Test Customer",
                "due_date": "30th January 2026",
                "total_enr_amount": "25000",
                "emi_eligibility": True,
                "waiver_eligible": False,
                "emi_eligible": True
            }
        }

        # Generate a temporary call ID (will be replaced when WebSocket connects)
        # For now, we store with a placeholder
        logger.info(f" Incoming call via {dialer_name}, agent: {agent_id}")

        # Build WebSocket URL
        websocket_url = build_websocket_url(dialer_name)

        # Build connection response using dialer's message builder
        response_content = dialer.message_builder.build_connection_response(
            websocket_url=websocket_url,
            custom_params=None
        )

        logger.info(f" Returning connection response for {dialer_name}")

        # Return appropriate content type based on dialer
        return Response(content=response_content, media_type="application/xml")

    except ValueError as e:
        logger.error(f"Dialer error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Error handling incoming call: {e}", exc_info=True)
        # Return error response in dialer format
        error_response = '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Service temporarily unavailable</Say><Hangup/></Response>'
        return Response(content=error_response, media_type="application/xml")


@router.websocket("/{dialer_name}/media-stream")
async def media_stream(websocket: WebSocket, dialer_name: str):
    """
    Generic WebSocket handler for media streaming with any dialer

    Args:
        websocket: WebSocket connection
        dialer_name: Name of the dialer (e.g., "twilio", "plivo")
    """
    await websocket.accept()
    logger.info(f" {dialer_name.capitalize()} WebSocket connection established")
    logger.info(f" WebSocket client: {websocket.client}")

    call_id = None
    stream_id = None
    agent_stream = None

    try:
        # Get dialer service
        dialer_class = DialerRegistry.get(dialer_name)
        dialer = dialer_class()

        while True:
            # Receive message from dialer
            message = await websocket.receive_text()
            data = json.loads(message)

            # Parse using dialer's connection handler
            parsed = await dialer.connection_handler.handle_incoming_message(data)
            event_type = parsed.get("event_type")

            if event_type == "start":
                # Connection initiated
                call_id = parsed.get("call_id")
                stream_id = parsed.get("stream_id")

                logger.info(f" Media stream started - CallID: {call_id}, StreamID: {stream_id}")
                logger.info(f" Parsed start data: {parsed}")

                # Try to get stored context (for incoming calls)
                context = get_call_context(call_id)

                # If no stored context, check custom parameters (for outbound calls)
                if not context:
                    custom_params = parsed.get("custom_parameters", {})
                    if custom_params:
                        logger.info(f"Using custom parameters: {custom_params}")

                        # Extract agent_id
                        agent_id = custom_params.get("agent_id", "agent_7201keyx3brmfk68gdwytc6a4tna")

                        # Build dynamic variables from custom parameters
                        dynamic_variables = {}
                        for key, value in custom_params.items():
                            if key != "agent_id":  # Only exclude agent_id (it's passed separately)
                                # Convert string booleans back to actual booleans
                                if value == "true":
                                    dynamic_variables[key] = True
                                elif value == "false":
                                    dynamic_variables[key] = False
                                else:
                                    dynamic_variables[key] = value

                        context = {
                            "agent_id": agent_id,
                            "dynamic_variables": dynamic_variables
                        }

                if not context:
                    logger.error(f"No context found for call {call_id}")
                    await websocket.close()
                    return

                # Get agent ID and dynamic variables
                agent_id = context.get("agent_id")
                dynamic_variables = context.get("dynamic_variables", {})

                # Connect to Agent (Generic)
                # Get agent provider from settings or context
                agent_provider = settings.default_agent
                
                logger.info(f" Selecting agent provider: {agent_provider}")
                logger.info(f" Connecting to {agent_provider} agent {agent_id}")
                
                try:
                    agent_service_class = AgentRegistry.get(agent_provider)
                    agent_service = agent_service_class()
                    
                    # Connect and get stream
                    logger.info(f" Initiating connection to {agent_provider}...")
                    agent_stream = await agent_service.connect(agent_id, dynamic_variables)
                    logger.info(f"✅ Connected to Agent Stream for {agent_provider}")
                    
                    # Initialize agent (send config)
                    logger.info(" Sending initialization to agent...")
                    await agent_stream.initialize()
                    logger.info("✅ Agent initialized successfully")

                    # Start background task to receive from Agent
                    asyncio.create_task(
                        receive_from_agent(agent_stream, websocket, stream_id, dialer)
                    )
                except Exception as e:
                    logger.error(f" Failed to connect/initialize agent: {e}", exc_info=True)
                    await websocket.close()
                    return

            elif event_type == "media":
                # Audio from caller
                audio_payload = parsed.get("audio_payload")

                if audio_payload and agent_stream:
                    # Convert dialer audio to PCM using dialer's converter
                    pcm_audio = dialer.audio_converter.dialer_to_pcm(audio_payload)

                    # Send PCM audio to Agent
                    await agent_stream.send_audio(pcm_audio)

            elif event_type == "stop":
                # Call ended
                logger.info(f"Media stream stopped for call {call_id}")
                break

            elif event_type == "mark":
                # Mark event (for synchronization)
                mark_name = parsed.get("mark_name")
                logger.debug(f"Received mark: {mark_name}")

            elif event_type == "dtmf":
                # DTMF event (key press)
                digit = parsed.get("digit")
                logger.info(f"Received DTMF digit: {digit}")
                # Optional: You could pass this to the agent if supported
                # if agent_stream:
                #     await agent_stream.send_dtmf(digit)

            else:
                # Unknown event
                logger.warning(f"Received unknown event from dialer: {parsed}")

    except WebSocketDisconnect:
        logger.info(f"{dialer_name.capitalize()} WebSocket disconnected for call {call_id}")
    except ValueError as e:
        logger.error(f"Dialer error: {e}")
    except Exception as e:
        logger.error(f"Error in {dialer_name} media stream: {e}", exc_info=True)
    finally:
        # Cleanup
        if agent_stream:
            try:
                await agent_stream.close()
            except:
                pass

        if call_id:
            cleanup_call_context(call_id)

        try:
            await websocket.close()
        except:
            pass

        logger.info(f"Cleaned up resources for call {call_id}")


async def receive_from_agent(agent_stream, dialer_ws, stream_id, dialer):
    """
    Background task to receive audio from Agent and send to dialer

    Args:
        agent_stream: AgentStream instance
        dialer_ws: Dialer WebSocket connection
        stream_id: Stream identifier
        dialer: Dialer service instance
    """
    try:
        async for event in agent_stream.receive():
            
            # Handle audio event
            if event.type == AgentEventTypes.AUDIO:
                pcm_bytes = event.data
                
                # Convert PCM to dialer format using dialer's converter
                dialer_audio = dialer.audio_converter.pcm_to_dialer(pcm_bytes)

                # Build dialer message
                dialer_message = dialer.message_builder.build_audio_message(
                    stream_id, dialer_audio
                )

                # Send to dialer
                await dialer_ws.send_text(json.dumps(dialer_message))

            # Handle text/transcription events
            elif event.type == AgentEventTypes.TEXT:
                logger.info(f"Agent response: {event.data}")
            
            elif event.type == AgentEventTypes.TRANSCRIPTION:
                logger.info(f"Transcription ({event.metadata.get('source', 'unknown')}): {event.data}")
                
            elif event.type == AgentEventTypes.INTERRUPTION:
                logger.info("User interrupted agent")
                
            elif event.type == AgentEventTypes.ERROR:
                logger.error(f"Agent error: {event.data}")

    except Exception as e:
        logger.error(f"Error receiving from Agent: {e}", exc_info=True)
