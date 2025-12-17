from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ElevenLabs Configuration
    elevenlabs_api_key: str

    # Webhook Authentication
    api_keys: str  # Comma-separated list of allowed API keys

    # Application Settings
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @property
    def allowed_api_keys(self) -> List[str]:
        """Parse comma-separated API keys into a list."""
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()
