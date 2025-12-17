from fastapi import Header, HTTPException, status
from app.config import settings


async def verify_api_key(x_api_key: str = Header(..., description="API key for authentication")):
    """
    Dependency to verify API key from request header.

    Args:
        x_api_key: API key from X-API-Key header

    Raises:
        HTTPException: 401 if API key is invalid or missing

    Returns:
        str: The validated API key
    """
    allowed_keys = settings.allowed_api_keys

    if not x_api_key or x_api_key not in allowed_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key
