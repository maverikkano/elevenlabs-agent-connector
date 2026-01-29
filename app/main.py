import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import webhooks, dialer
from app.models import ErrorResponse
from app.services.dialers.registry import DialerRegistry
from app.services.dialers.twilio.service import TwilioDialerService
from app.services.agents.registry import AgentRegistry
from app.services.agents.elevenlabs.service import ElevenLabsAgentService
from app.services.agents.predixionai.service import PredixionAIAgentService

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ElevenLabs Agent Connector",
    description="FastAPI service for connecting external dialers to ElevenLabs conversational AI agents",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

if settings.is_development:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS enabled for development")

# Register dialer plugins
DialerRegistry.register("twilio", TwilioDialerService)
logger.info("Registered dialer plugins")

# Register agent plugins
AgentRegistry.register("elevenlabs", ElevenLabsAgentService)
AgentRegistry.register("predixionai", PredixionAIAgentService)
logger.info("Registered agent plugins")

# Include routers
# NOTE: dialer router must come FIRST to take precedence over deprecated webhooks endpoints
app.include_router(dialer.router, tags=["dialer"])
app.include_router(webhooks.router, tags=["webhooks"])


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("ElevenLabs Agent Connector Starting")
    logger.info("=" * 60)
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Log Level: {settings.log_level}")
    logger.info(f"Host: {settings.host}")
    logger.info(f"Port: {settings.port}")
    logger.info(f"API Keys Configured: {len(settings.allowed_api_keys)}")
    logger.info(f"Default Dialer: {settings.default_dialer}")
    logger.info(f"Registered Dialers: {', '.join(DialerRegistry.list_dialers())}")
    logger.info(f"Default Agent: {settings.default_agent}")
    logger.info(f"Registered Agents: {', '.join(AgentRegistry.list_agents())}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("ElevenLabs Agent Connector Shutting Down")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

    error_response = ErrorResponse(
        error="Internal server error",
        detail=str(exc) if settings.is_development else "An unexpected error occurred"
    )

    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )


@app.get("/")
async def root():
    return {
        "service": "ElevenLabs Agent Connector",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower()
    )
