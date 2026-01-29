from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    elevenlabs_api_key: str
    api_keys: str  # Comma-separated

    # Dialer configuration
    default_dialer: str = "twilio"  # Default dialer to use

    # Agent configuration
    default_agent: str = "predixionai"  # Default agent to use

    # PredixionAI Voice settings
    predixionai_api_url: str = "http://localhost:8001"
    predixionai_api_key: str = ""

    # Twilio settings (optional)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Plivo settings (optional) - for future dialers
    plivo_auth_id: str = ""
    plivo_auth_token: str = ""
    plivo_phone_number: str = ""

    environment: str = "production"
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
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


settings = Settings()
