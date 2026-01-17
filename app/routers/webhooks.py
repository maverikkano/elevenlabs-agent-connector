import logging
import uuid
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