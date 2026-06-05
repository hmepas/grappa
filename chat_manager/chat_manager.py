"""Chat cache, sync and search service."""

from typing import List, Optional, Union

from pydantic import BaseModel

from client import TelegramClient
from data.models import ChatInfo
from storage.cache_storage import CacheStorage


class DeleteAndLeaveResult(BaseModel):
    """Result of delete/leave operation for one chat."""

    chat_ref: str
    resolved_chat_id: Optional[int] = None
    success: bool
    error: Optional[str] = None


class ChatManager:
    """High-level chat management API used by CLI/WebUI/TUI."""

    def __init__(
        self,
        storage: Optional[CacheStorage] = None,
        client: Optional[TelegramClient] = None,
    ) -> None:
        """Initialize manager with optional storage and Telegram client."""
        self.storage = storage or CacheStorage()
        self.client = client

    async def list_chats(
        self, limit: int = 50, cached: bool = True, force_refresh: bool = False
    ) -> List[ChatInfo]:
        """List chats from cache or Telegram API."""
        if cached and not force_refresh:
            chats = await self.storage.load_chats()
            if chats:
                return chats if limit <= 0 else chats[:limit]
        chats = await self.sync_chats(limit=limit)
        return chats if limit <= 0 else chats[:limit]

    async def sync_chats(self, limit: int = 0) -> List[ChatInfo]:
        """Download chats from Telegram and update local cache.

        Pyrogram uses 0 as unlimited for many iterators; if it changes, pass a
        large explicit limit from CLI.
        """
        async with self._client_context() as client:
            chats = await client.get_dialogs(limit=limit)
        await self.storage.save_chats(chats)
        return chats

    async def refresh_chat_statuses(self) -> List[ChatInfo]:
        """Refresh deactivated/migrated/inaccessible flags for cached suspect chats."""
        chats = await self.storage.load_chats()
        by_id = {chat.id: chat for chat in chats}
        suspect_chats = [
            chat for chat in chats if chat.type != "private" and chat.members_count == 0
        ]

        async with self._client_context() as client:
            for chat in suspect_chats:
                try:
                    by_id[chat.id] = await client.get_chat_info(chat.id)
                except Exception:
                    by_id[chat.id] = chat.model_copy(update={"is_inaccessible": True})

        updated = [by_id[chat.id] for chat in chats]
        await self.storage.save_chats(updated)
        return updated

    async def search_chats(self, query: str, limit: int = 20) -> List[ChatInfo]:
        """Search cached chats by id, username or title."""
        normalized = query.strip().lower()
        username = normalized[1:] if normalized.startswith("@") else normalized
        chats = await self.storage.load_chats()

        scored: List[tuple[int, ChatInfo]] = []
        for chat in chats:
            score = 0
            if normalized == str(chat.id):
                score += 100
            if chat.username and chat.username.lower() == username:
                score += 90
            if chat.username and username in chat.username.lower():
                score += 50
            if chat.title and normalized in chat.title.lower():
                score += 40
            if chat.display_name.lower().startswith(normalized):
                score += 20
            if score:
                scored.append((score, chat))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chat for _, chat in scored[:limit]]

    async def delete_and_leave_chats(
        self, chat_refs: List[Union[int, str]]
    ) -> List[DeleteAndLeaveResult]:
        """Delete/leave multiple chats and remove successful ones from cache."""
        results: List[DeleteAndLeaveResult] = []
        successful_ids: set[int] = set()

        async with self._client_context() as client:
            for chat_ref in chat_refs:
                resolved = await self.resolve_chat(chat_ref)
                try:
                    await client.delete_and_leave_chat(resolved)
                    resolved_id = resolved if isinstance(resolved, int) else None
                    if resolved_id is not None:
                        successful_ids.add(resolved_id)
                    results.append(
                        DeleteAndLeaveResult(
                            chat_ref=str(chat_ref),
                            resolved_chat_id=resolved_id,
                            success=True,
                        )
                    )
                except Exception as exc:
                    results.append(
                        DeleteAndLeaveResult(
                            chat_ref=str(chat_ref),
                            resolved_chat_id=resolved
                            if isinstance(resolved, int)
                            else None,
                            success=False,
                            error=str(exc),
                        )
                    )

        if successful_ids:
            chats = await self.storage.load_chats()
            await self.storage.save_chats(
                [chat for chat in chats if chat.id not in successful_ids]
            )
        return results

    async def resolve_chat(self, ref: Union[int, str]) -> Union[int, str]:
        """Resolve chat reference for Telegram API calls.

        Accepts numeric id, @username, username, or a title substring from cache.
        Returns original reference if cache cannot resolve it.
        """
        if isinstance(ref, int):
            return ref
        raw = ref.strip()
        if raw.lstrip("-").isdigit():
            return int(raw)
        if raw.startswith("@"):
            return raw

        chats = await self.search_chats(raw, limit=1)
        if chats:
            return chats[0].id
        return raw

    def _client_context(self) -> TelegramClient:
        return self.client or TelegramClient()
