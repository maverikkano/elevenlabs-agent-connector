import logging
import uuid
import json
import asyncio
import base64
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Form, WebSocket, WebSocketDisconnect, Response
from twilio.rest import Client
from app.models import (
    InitiateCallRequest,
    InitiateCallResponse,
    ErrorResponse,
    HealthResponse
)
from app.auth import verify_api_key
from app.services import elevenlabs_service, audio_service
from app.services.twilio_service import (
    TwilioAudioConverter,
    TwilioMessageBuilder,
    generate_twiml_response,
    store_call_context,
    get_call_context,
    cleanup_call_context
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy")


@router.post(
    "/webhook/initiate-call",
    response_model=InitiateCallResponse,
    responses={
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }
)
async def initiate_call(
    request: InitiateCallRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    session_id = request.session_id or str(uuid.uuid4())

    logger.info(
        f"Initiating call - Session: {session_id}, Agent: {request.agent_id}, "
        f"Metadata: {request.metadata}"
    )

    try:
        logger.info(f"Requesting signed URL for agent {request.agent_id}")
        signed_url = await elevenlabs_service.get_signed_url(request.agent_id)

        logger.info("Establishing WebSocket connection")
        websocket = await elevenlabs_service.create_websocket_connection(signed_url)

        logger.info("Starting audio stream in background")

        async def run_audio_stream():
            try:
                dynamic_variables = request.metadata.get("dynamic_variables") if request.metadata else None
                await audio_service.start_conversation_stream(
                    websocket,
                    duration=None,
                    dynamic_variables=dynamic_variables
                )
            except Exception as e:
                logger.error(f"Error in background audio stream: {str(e)}")

        background_tasks.add_task(run_audio_stream)

        logger.info(f"Call initiated successfully - Session: {session_id}")

        return InitiateCallResponse(
            success=True,
            session_id=session_id,
            websocket_url=signed_url,
            message="Call initiated successfully. Audio streaming started."
        )

    except elevenlabs_service.ElevenLabsError as e:
        logger.error(f"ElevenLabs error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect to ElevenLabs: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Unexpected error initiating call: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate call: {str(e)}"
        )


# Twilio Integration Endpoints (DEPRECATED)
# Use /{dialer_name}/outbound-call instead for dialer-agnostic approach

@router.post("/twilio/outbound-call", deprecated=True)
async def initiate_outbound_call(
    request: InitiateCallRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    [DEPRECATED] Initiate an outbound call via Twilio to a customer

    **This endpoint is deprecated. Use `/twilio/outbound-call` (without the prefix)
    via the generic dialer router instead.**

    New endpoint: `POST /{dialer_name}/outbound-call`
    Example: `POST /twilio/outbound-call` (same path, different router)

    Args:
        request: Contains agent_id, session_id, and metadata with customer info

    Returns:
        Response with call SID and status
    """
    logger.warning("⚠️ DEPRECATED: /twilio/outbound-call endpoint is deprecated. Use /{dialer_name}/outbound-call instead")
    try:
        # Extract customer data from request
        metadata = request.metadata or {}
        dynamic_variables = metadata.get("dynamic_variables", {})
        to_number = metadata.get("to_number")

        if not to_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="to_number is required in metadata"
            )

        # Validate Twilio credentials
        if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.twilio_phone_number:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Twilio credentials not configured"
            )

        # Initialize Twilio client
        twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

        # Determine WebSocket URL
        protocol = "wss" if settings.environment == "production" else "ws"
        host = settings.host if settings.host != "0.0.0.0" else "localhost"
        websocket_url = f"{protocol}://{host}:{settings.port}/twilio/media-stream"

        logger.info(f"📡 WebSocket URL for Twilio: {websocket_url}")
        logger.info(f"🔧 Environment: {settings.environment}, Host: {settings.host}, Port: {settings.port}")

        # Build TwiML with customer data as Stream parameters
        parameters_xml = ""
        for key, value in dynamic_variables.items():
            # Convert boolean to string
            if isinstance(value, bool):
                value = "true" if value else "false"
            parameters_xml += f'<Parameter name="{key}" value="{value}" />\n            '

        # Add agent_id as parameter
        parameters_xml += f'<Parameter name="agent_id" value="{request.agent_id}" />\n            '
        parameters_xml += f'<Parameter name="to_number" value="{to_number}" />'

        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{websocket_url}">
            {parameters_xml}
        </Stream>
    </Connect>
</Response>'''

        logger.info(f"📄 Generated TwiML:\n{twiml}")

        # Make outbound call
        call = twilio_client.calls.create(
            from_=settings.twilio_phone_number,
            to=to_number,
            twiml=twiml
        )

        logger.info(f"✅ Outbound call initiated - CallSid: {call.sid}, To: {to_number}")

        return {
            "success": True,
            "call_sid": call.sid,
            "to": to_number,
            "status": call.status,
            "message": "Outbound call initiated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating outbound call: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate outbound call: {str(e)}"
        )


@router.post("/twilio/incoming-call", deprecated=True)
async def twilio_incoming_call(
    From: str = Form(...),
    To: str = Form(...),
    CallSid: str = Form(...)
):
    """
    [DEPRECATED] Twilio webhook endpoint - called when a call arrives

    **This endpoint is deprecated. Use `/twilio/incoming-call` (without the prefix)
    via the generic dialer router instead.**

    New endpoint: `POST /{dialer_name}/incoming-call`
    Example: `POST /twilio/incoming-call` (same path, different router)

    Args:
        From: Caller's phone number
        To: Dialed number (your Twilio number)
        CallSid: Unique call identifier from Twilio

    Returns:
        TwiML XML instructing Twilio to start media streaming
    """
    logger.warning("⚠️ DEPRECATED: /twilio/incoming-call endpoint is deprecated. Use /{dialer_name}/incoming-call instead")
    logger.info(f"Incoming Twilio call - From: {From}, To: {To}, CallSid: {CallSid}")

    try:
        # Hardcoded customer context (replace with database lookup in production)
        customer_context = {
            "caller_number": From,
            "agent_id": "agent_7201keyx3brmfk68gdwytc6a4tna",
            "dynamic_variables": {
                "name": "Sumit Sharma",
                "caller_number": From,
                "due_date": "30th January 2026",
                "total_enr_amount": "25000",
                "emi_eligibility": True,
                "waiver_eligible": False,
                "emi_eligible": True
            }
        }

        # Store context for when WebSocket connects
        store_call_context(CallSid, customer_context)

        # Determine WebSocket URL (use your public domain in production)
        protocol = "wss" if settings.environment == "production" else "ws"
        host = settings.host if settings.host != "0.0.0.0" else "localhost"
        websocket_url = f"{protocol}://{host}:{settings.port}/twilio/media-stream"

        # Generate TwiML response
        twiml = generate_twiml_response(websocket_url)

        logger.info(f"Responding with TwiML for call {CallSid}")
        return Response(content=twiml, media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling Twilio incoming call: {e}", exc_info=True)
        # Return error TwiML
        error_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>We're sorry, but we're experiencing technical difficulties. Please try again later.</Say>
    <Hangup/>
</Response>'''
        return Response(content=error_twiml, media_type="application/xml")


@router.websocket("/twilio/media-stream", name="twilio_media_stream_deprecated")
async def twilio_media_stream(websocket: WebSocket):
    """
    [DEPRECATED] Twilio Media Streams WebSocket endpoint

    **This endpoint is deprecated. Use `/{dialer_name}/media-stream` instead
    via the generic dialer router.**

    New endpoint: `WS /{dialer_name}/media-stream`
    Example: `WS /twilio/media-stream` (same path, different router)

    Handles bidirectional audio streaming between Twilio and ElevenLabs
    """
    await websocket.accept()
    logger.warning("⚠️ DEPRECATED: /twilio/media-stream WebSocket is deprecated. Use /{dialer_name}/media-stream instead")
    logger.info("🔌 Twilio WebSocket connection established")
    logger.info(f"📍 WebSocket client: {websocket.client}")

    call_sid = None
    stream_sid = None
    elevenlabs_ws = None
    audio_converter = TwilioAudioConverter()
    msg_builder = TwilioMessageBuilder()

    try:
        while True:
            # Receive message from Twilio
            message = await websocket.receive_text()
            data = json.loads(message)

            event_type = data.get("event")

            if event_type == "start":
                # First message with call metadata
                start_data = data.get("start", {})
                call_sid = start_data.get("callSid")
                stream_sid = start_data.get("streamSid")

                # Extract custom parameters from Stream (for outbound calls)
                custom_parameters = start_data.get("customParameters", {})

                logger.info(f"🎬 Media stream started - CallSid: {call_sid}, StreamSid: {stream_sid}")
                logger.info(f"📦 Start data received: {start_data}")

                # Try to get stored context (for inbound calls)
                context = get_call_context(call_sid)

                # If no stored context, check custom parameters (for outbound calls)
                if not context and custom_parameters:
                    logger.info(f"Using custom parameters from outbound call: {custom_parameters}")

                    # Extract agent_id from parameters
                    agent_id = custom_parameters.get("agent_id", "agent_7201keyx3brmfk68gdwytc6a4tna")

                    # Build dynamic variables from custom parameters
                    dynamic_variables = {}
                    for key, value in custom_parameters.items():
                        if key != "agent_id":
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
                    logger.error(f"No context found for call {call_sid}")
                    await websocket.close()
                    return

                # Get agent ID and dynamic variables
                agent_id = context.get("agent_id")
                dynamic_variables = context.get("dynamic_variables")

                # Connect to ElevenLabs
                logger.info(f"🤖 Connecting to ElevenLabs agent {agent_id}")
                signed_url = await elevenlabs_service.get_signed_url(agent_id)
                logger.info(f"🔗 ElevenLabs WebSocket URL: {signed_url}")

                elevenlabs_ws = await elevenlabs_service.create_websocket_connection(signed_url)
                logger.info(f"✅ Connected to ElevenLabs WebSocket")

                # Send initialization message to ElevenLabs
                init_message = {
                    "type": "conversation_initiation_client_data",
                    "dynamic_variables": dynamic_variables or {}
                }
                logger.info(f"📤 Sending initialization with dynamic variables: {dynamic_variables}")
                await elevenlabs_ws.send(json.dumps(init_message))
                logger.info("✅ Sent initialization to ElevenLabs")

                # Start background task to receive from ElevenLabs
                asyncio.create_task(
                    receive_from_elevenlabs(elevenlabs_ws, websocket, stream_sid, audio_converter, msg_builder)
                )

            elif event_type == "media":
                # Audio from caller (Twilio → ElevenLabs)
                media_data = data.get("media", {})
                mulaw_payload = media_data.get("payload")

                if mulaw_payload and elevenlabs_ws:
                    # Convert mu-law 8kHz → PCM 16kHz
                    pcm_audio = audio_converter.mulaw_to_pcm(mulaw_payload)

                    # Encode to base64 for ElevenLabs
                    pcm_base64 = base64.b64encode(pcm_audio).decode('utf-8')

                    # Send to ElevenLabs
                    elevenlabs_message = {
                        "user_audio_chunk": pcm_base64
                    }
                    await elevenlabs_ws.send(json.dumps(elevenlabs_message))

            elif event_type == "stop":
                # Call ended
                logger.info(f"Media stream stopped for call {call_sid}")
                break

            elif event_type == "mark":
                # Mark event (for synchronization)
                mark_data = data.get("mark", {})
                logger.debug(f"Received mark: {mark_data.get('name')}")

    except WebSocketDisconnect:
        logger.info(f"Twilio WebSocket disconnected for call {call_sid}")
    except Exception as e:
        logger.error(f"Error in Twilio media stream: {e}", exc_info=True)
    finally:
        # Cleanup
        if elevenlabs_ws:
            try:
                await elevenlabs_ws.close()
            except:
                pass

        if call_sid:
            cleanup_call_context(call_sid)

        try:
            await websocket.close()
        except:
            pass

        logger.info(f"Cleaned up resources for call {call_sid}")


async def receive_from_elevenlabs(elevenlabs_ws, twilio_ws, stream_sid, audio_converter, msg_builder):
    """
    Background task to receive audio from ElevenLabs and send to Twilio

    Args:
        elevenlabs_ws: ElevenLabs WebSocket connection
        twilio_ws: Twilio WebSocket connection
        stream_sid: Twilio stream identifier
        audio_converter: Audio converter instance
        msg_builder: Twilio message builder instance
    """
    try:
        while True:
            message = await elevenlabs_ws.recv()

            if isinstance(message, str):
                data = json.loads(message)

                # Handle audio from agent
                if data.get("type") == "audio" and "audio_event" in data:
                    audio_event = data["audio_event"]
                    pcm_base64 = audio_event.get("audio_base_64")

                    if pcm_base64:
                        # Decode PCM audio
                        pcm_bytes = base64.b64decode(pcm_base64)

                        # Convert PCM 16kHz → mu-law 8kHz
                        mulaw_payload = audio_converter.pcm_to_mulaw(pcm_bytes)

                        # Send to Twilio
                        twilio_message = msg_builder.build_media_message(stream_sid, mulaw_payload)
                        await twilio_ws.send_text(json.dumps(twilio_message))

                # Handle other ElevenLabs events
                elif data.get("type") == "interruption_event":
                    logger.info("User interrupted agent")

                elif data.get("type") == "agent_response_event":
                    logger.info(f"Agent response: {data.get('agent_response_event', {}).get('response')}")

                elif data.get("type") == "user_transcription_event":
                    logger.info(f"User said: {data.get('user_transcription_event', {}).get('user_transcription')}")

                elif data.get("type") == "ping_event":
                    # Respond to ping
                    pong = {"type": "pong_event"}
                    await elevenlabs_ws.send(json.dumps(pong))

    except Exception as e:
        logger.error(f"Error receiving from ElevenLabs: {e}", exc_info=True)