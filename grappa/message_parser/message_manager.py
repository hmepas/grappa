"""Message download and search service."""

from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import List, Optional, Union

from grappa.chat_manager import ChatManager
from grappa.client import TelegramClient
from grappa.config import get_settings
from grappa.data.models import MessageInfo
from grappa.storage.cache_storage import CacheStorage


class MessageManager:
    """High-level API for chat messages."""

    def __init__(
        self,
        storage: Optional[CacheStorage] = None,
        chat_manager: Optional[ChatManager] = None,
        client: Optional[TelegramClient] = None,
    ) -> None:
        """Initialize manager with optional dependencies."""
        self.storage = storage or CacheStorage()
        self.chat_manager = chat_manager or ChatManager(storage=self.storage)
        self.client = client
        self.settings = get_settings()

    async def download_chat(
        self,
        chat_ref: Union[int, str],
        limit: int = 100,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        include_media: bool = False,
        media_dir: Optional[Path] = None,
    ) -> List[MessageInfo]:
        """Download chat messages, cache them and optionally download media."""
        resolved = await self.chat_manager.resolve_chat(chat_ref)
        async with self._client_context() as client:
            messages = await client.get_chat_messages(
                chat_id=resolved,
                limit=limit,
                offset_date=to_date,
            )
            messages = self._filter_by_date(messages, from_date, to_date)
            if include_media:
                messages = await self._download_media(client, messages, media_dir)

        if messages:
            await self.storage.save_messages(messages[0].chat_id, messages)
        return messages

    async def sync_chat(
        self,
        chat_ref: Union[int, str],
        include_media: bool = True,
        media_dir: Optional[Path] = None,
        limit: int = 0,
    ) -> List[MessageInfo]:
        """Fetch only messages newer than the local cache and merge them in.

        On first run (empty cache) this downloads the whole chat history.
        Edited/deleted messages older than the last cached one are not
        refreshed - the sync only moves forward.
        """
        resolved = await self.chat_manager.resolve_chat(chat_ref)
        async with self._client_context() as client:
            if not isinstance(resolved, int):
                chat_info = await client.get_chat_info(resolved)
                resolved = chat_info.id

            cached = await self.storage.load_messages(resolved)
            last_cached_id = max((m.id for m in cached), default=None)
            messages = await client.get_chat_messages(
                chat_id=resolved,
                limit=limit,
                stop_before_id=last_cached_id,
            )
            if include_media:
                messages = await self._download_media(client, messages, media_dir)

        if messages:
            await self.storage.save_messages(resolved, messages)
        return messages

    async def search_cached_messages(
        self,
        query: str,
        chat_ref: Optional[Union[int, str]] = None,
        limit: int = 50,
    ) -> List[MessageInfo]:
        """Search locally cached messages."""
        normalized = query.lower()
        if chat_ref is not None:
            resolved = await self.chat_manager.resolve_chat(chat_ref)
            chat_ids = [int(resolved)] if isinstance(resolved, int) else []
        else:
            chat_ids = [
                int(path.stem) for path in self.storage.messages_dir.glob("*.json")
            ]

        found: List[MessageInfo] = []
        for chat_id in chat_ids:
            messages = await self.storage.load_messages(chat_id)
            for message in messages:
                if message.text and normalized in message.text.lower():
                    found.append(message)
                    if len(found) >= limit:
                        return found
        return found

    async def search_telegram_messages(
        self,
        query: str,
        chat_ref: Optional[Union[int, str]] = None,
        limit: int = 50,
        cache_results: bool = True,
    ) -> List[MessageInfo]:
        """Search messages via Telegram API globally or inside one chat."""
        resolved: Optional[Union[int, str]] = None
        if chat_ref is not None:
            resolved = await self.chat_manager.resolve_chat(chat_ref)

        async with self._client_context() as client:
            messages = await client.search_messages(
                query=query, chat_id=resolved, limit=limit
            )

        if cache_results:
            by_chat: dict[int, List[MessageInfo]] = {}
            for message in messages:
                by_chat.setdefault(message.chat_id, []).append(message)
            for chat_id, chat_messages in by_chat.items():
                await self.storage.save_messages(chat_id, chat_messages)
        return messages

    async def _download_media(
        self,
        client: TelegramClient,
        messages: List[MessageInfo],
        media_dir: Optional[Path] = None,
    ) -> List[MessageInfo]:
        updated: List[MessageInfo] = []
        for message in messages:
            if not message.media_type:
                updated.append(message)
                continue
            if message.downloaded_media_path and message.downloaded_media_path.exists():
                updated.append(message)
                continue
            output_dir = media_dir or (
                self.settings.app.downloads_dir / str(message.chat_id)
            )
            path = await client.download_message_media(message, output_dir)
            if path:
                message = message.model_copy(update={"downloaded_media_path": path})
            updated.append(message)
        return updated

    def _filter_by_date(
        self,
        messages: List[MessageInfo],
        from_date: Optional[datetime],
        to_date: Optional[datetime],
    ) -> List[MessageInfo]:
        filtered = []
        for message in messages:
            message_date = self._ensure_tz(message.date)
            if from_date and message_date < self._ensure_tz(from_date):
                continue
            if to_date and message_date > self._ensure_tz(to_date):
                continue
            filtered.append(message)
        return filtered

    def _ensure_tz(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _client_context(self) -> TelegramClient:
        return self.client or TelegramClient()


def parse_cli_date(
    value: Optional[str], end_of_day: bool = False
) -> Optional[datetime]:
    """Parse CLI date/datetime value.

    Supports YYYY-MM-DD and ISO datetime strings.
    """
    if not value:
        return None
    if len(value) == 10:
        parsed_date = date.fromisoformat(value)
        parsed_time = time.max if end_of_day else time.min
        return datetime.combine(parsed_date, parsed_time, tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
