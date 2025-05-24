"""Application settings and configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramSettings(BaseSettings):
    """Telegram API configuration."""

    api_id: int = Field(description="Telegram API ID")
    api_hash: str = Field(description="Telegram API hash")
    phone_number: Optional[str] = Field(default=None, description="Phone number")
    session_name: str = Field(default="grappa_session", description="Session file name")

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )


class AppSettings(BaseSettings):
    """Application configuration."""

    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Log file path")

    # Session and data directories
    data_dir: Path = Field(default=Path.cwd() / "data", description="Data directory")
    session_dir: Path = Field(
        default=Path.cwd() / "sessions", description="Session directory"
    )

    # Message processing settings
    max_messages_per_chat: int = Field(
        default=1000, description="Max messages to process per chat"
    )
    context_length: int = Field(default=100, description="Context length for mentions")

    model_config = SettingsConfigDict(
        env_prefix="GRAPPA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )


class Settings(BaseSettings):
    """Combined application settings."""

    telegram: TelegramSettings = Field(default_factory=lambda: TelegramSettings())
    app: AppSettings = Field(default_factory=lambda: AppSettings())

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )

    def __init__(self, **kwargs: object) -> None:
        """Initialize settings and create necessary directories."""
        super().__init__(**kwargs)
        # Ensure directories exist
        self.app.data_dir.mkdir(exist_ok=True)
        self.app.session_dir.mkdir(exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
