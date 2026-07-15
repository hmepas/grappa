"""Application settings and configuration."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "grappa"
)
GLOBAL_ENV_FILE = CONFIG_DIR / "config.env"

# Default home for all working data; grappa is an installed app, so data must
# not depend on the current working directory unless overridden via GRAPPA_*.
GRAPPA_HOME = Path.home() / ".grappa"

# Local ./.env takes priority over the global config file (later files win)
_ENV_FILES = (str(GLOBAL_ENV_FILE), ".env")


class TelegramSettings(BaseSettings):
    """Telegram API configuration."""

    api_id: int = Field(description="Telegram API ID")
    api_hash: str = Field(description="Telegram API hash")
    phone_number: Optional[str] = Field(default=None, description="Phone number")
    session_name: str = Field(default="grappa_session", description="Session file name")

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )


class AppSettings(BaseSettings):
    """Application configuration."""

    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Log file path")

    # Session and data directories
    data_dir: Path = Field(default=GRAPPA_HOME / "data", description="Data directory")
    session_dir: Path = Field(
        default=GRAPPA_HOME / "data" / "sessions", description="Session directory"
    )
    downloads_dir: Path = Field(
        default=GRAPPA_HOME / "data" / "downloads",
        description="Downloaded media directory",
    )

    @field_validator("data_dir", "session_dir", "downloads_dir", mode="before")
    @classmethod
    def _expand_user(cls, value: object) -> object:
        """Expand ~ in directory paths coming from env/config files."""
        if isinstance(value, str):
            return Path(value).expanduser()
        return value

    # Message processing settings
    max_messages_per_chat: int = Field(
        default=1000, description="Max messages to process per chat"
    )
    context_length: int = Field(default=100, description="Context length for mentions")

    model_config = SettingsConfigDict(
        env_prefix="GRAPPA_",
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )


class Settings(BaseSettings):
    """Combined application settings."""

    telegram: TelegramSettings = Field(
        default_factory=lambda: TelegramSettings()  # type: ignore[call-arg]
    )
    app: AppSettings = Field(default_factory=lambda: AppSettings())

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
    )

    def __init__(self, **kwargs: object) -> None:
        """Initialize settings and create necessary directories."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        # Ensure directories exist
        self.app.data_dir.mkdir(parents=True, exist_ok=True)
        self.app.session_dir.mkdir(parents=True, exist_ok=True)
        self.app.downloads_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
