import logging
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from app.models import (
    InitiateCallRequest,
    InitiateCallResponse,
    ErrorResponse,
    HealthResponse
)
from app.auth import verify_api_key
from app.services import elevenlabs_service, audio_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint to verify service is running.

    Returns:
        HealthResponse: Service status
    """
    return HealthResponse(status="healthy")


@router.post(
    "/webhook/initiate-call",
    response_model=InitiateCallResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized - Invalid API key"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def initiate_call(
    request: InitiateCallRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Initiate a call to an ElevenLabs conversational AI agent.

    This endpoint:
    1. Receives webhook data from N8N/external dialer
    2. Gets a signed URL from ElevenLabs for the specified agent
    3. Establishes WebSocket connection
    4. Starts streaming audio from local microphone
    5. Returns session information

    Args:
        request: Call initiation request with agent_id and metadata
        background_tasks: FastAPI background tasks for async processing
        api_key: Validated API key from header

    Returns:
        InitiateCallResponse: Success response with session info

    Raises:
        HTTPException: If call initiation fails
    """
    # Generate session ID if not provided
    session_id = request.session_id or str(uuid.uuid4())

    logger.info(
        f"Initiating call - Session: {session_id}, Agent: {request.agent_id}, "
        f"Metadata: {request.metadata}"
    )

    try:
        # Step 1: Get signed URL from ElevenLabs
        logger.info(f"Requesting signed URL for agent {request.agent_id}")
        signed_url = await elevenlabs_service.get_signed_url(request.agent_id)

        # Step 2: Establish WebSocket connection
        logger.info("Establishing WebSocket connection")
        websocket = await elevenlabs_service.create_websocket_connection(signed_url)


        # Step 3: Start audio streaming in background
        # Note: Running in background so we can return response immediately
        logger.info("Starting audio stream in background")

        async def run_audio_stream():
            """Background task to handle audio streaming."""
            try:
                # Extract dynamic variables from metadata if provided
                dynamic_variables = request.metadata.get("dynamic_variables") if request.metadata else None

                await audio_service.start_conversation_stream(
                    websocket,
                    duration=None,  # Stream indefinitely
                    dynamic_variables=dynamic_variables
                )
            except Exception as e:
                logger.error(f"Error in background audio stream: {str(e)}")

        background_tasks.add_task(run_audio_stream)

        # Step 4: Return success response
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
