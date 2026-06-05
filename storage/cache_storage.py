"""JSON cache storage for chats and messages."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, Field, ValidationError

from config import get_settings
from data.models import ChatInfo, MessageInfo

CACHE_VERSION = "1"


class CacheMetadata(BaseModel):
    """Metadata for local cache."""

    version: str = Field(default=CACHE_VERSION)
    last_chats_sync: Optional[datetime] = None
    total_chats: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CacheStorage:
    """Simple JSON-file based cache storage.

    Keeps cache human-readable and portable. Corrupted files gracefully degrade to
    empty data instead of breaking the application.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        """Initialize storage under configured or provided data directory."""
        settings = get_settings()
        self.data_dir = data_dir or settings.app.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.messages_dir.mkdir(parents=True, exist_ok=True)

    @property
    def chats_file(self) -> Path:
        """Return path to chats cache file."""
        return self.data_dir / "chats_cache.json"

    @property
    def metadata_file(self) -> Path:
        """Return path to cache metadata file."""
        return self.data_dir / "cache_metadata.json"

    @property
    def messages_dir(self) -> Path:
        """Return directory containing per-chat message caches."""
        return self.data_dir / "messages"

    def messages_file(self, chat_id: int) -> Path:
        """Return path to one chat message cache file."""
        return self.messages_dir / f"{chat_id}.json"

    async def save_chats(self, chats: List[ChatInfo]) -> None:
        """Persist chats cache."""
        payload = [chat.model_dump(mode="json") for chat in chats]
        self._write_json(self.chats_file, payload)
        await self.save_metadata(
            CacheMetadata(
                last_chats_sync=datetime.now(timezone.utc),
                total_chats=len(chats),
            )
        )

    async def load_chats(self) -> List[ChatInfo]:
        """Load cached chats."""
        raw = self._read_json(self.chats_file, default=[])
        chats: List[ChatInfo] = []
        if not isinstance(raw, list):
            return chats
        for item in raw:
            try:
                chats.append(ChatInfo.model_validate(item))
            except ValidationError:
                continue
        return chats

    async def save_messages(self, chat_id: int, messages: List[MessageInfo]) -> None:
        """Merge and persist messages for a chat."""
        existing = {m.id: m for m in await self.load_messages(chat_id)}
        for message in messages:
            existing[message.id] = message
        ordered = sorted(existing.values(), key=lambda m: (m.date, m.id))
        payload = [message.model_dump(mode="json") for message in ordered]
        self._write_json(self.messages_file(chat_id), payload)

    async def load_messages(self, chat_id: int) -> List[MessageInfo]:
        """Load cached messages for a chat."""
        raw = self._read_json(self.messages_file(chat_id), default=[])
        messages: List[MessageInfo] = []
        if not isinstance(raw, list):
            return messages
        for item in raw:
            try:
                messages.append(MessageInfo.model_validate(item))
            except ValidationError:
                continue
        return messages

    async def save_metadata(self, metadata: CacheMetadata) -> None:
        """Persist cache metadata."""
        self._write_json(self.metadata_file, metadata.model_dump(mode="json"))

    async def load_metadata(self) -> CacheMetadata:
        """Load cache metadata."""
        raw = self._read_json(self.metadata_file, default={})
        if not isinstance(raw, dict):
            return CacheMetadata()
        try:
            return CacheMetadata.model_validate(raw)
        except ValidationError:
            return CacheMetadata()

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp_path.replace(path)
