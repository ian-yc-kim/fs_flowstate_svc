from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings using Pydantic BaseSettings for robust configuration management."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Allow extra fields in environment without validation errors
    )

    DATABASE_URL: str = "sqlite:///:memory:"
    SERVICE_PORT: int = 8000
    OPENAI_API_KEY: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    SECRET_KEY: str = Field(..., validation_alias="SECRET_KEY", min_length=32)
    JWT_SECRET_KEY: SecretStr = Field(default="jwt_development_secret_key_32_chars", validation_alias="JWT_SECRET_KEY", min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DEFAULT_PREPARATION_TIMES: dict[str, int] = Field(
        default_factory=lambda: {
            "meeting": 10,
            "deep work": 15,
            "travel": 30,
            "general": 5
        }
    )

    # WebSocket heartbeat settings (seconds)
    WS_PING_INTERVAL_SECONDS: int = 15
    WS_PONG_TIMEOUT_SECONDS: int = 45


# Module-level settings instance
settings = Settings()
