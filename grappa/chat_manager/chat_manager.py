"""Chat cache, sync and search service."""

import asyncio
from typing import Callable, List, Optional, Union

from pydantic import BaseModel
from pyrogram.errors import FloodWait

from grappa.client import TelegramClient
from grappa.data.models import ChatInfo, FolderInfo
from grappa.storage.cache_storage import CacheStorage


class ArchiveResult(BaseModel):
    """Result of archive/unarchive operation for one chat."""

    chat_ref: str
    resolved_chat_id: Optional[int] = None
    success: bool
    error: Optional[str] = None


class DeleteAndLeaveResult(BaseModel):
    """Result of delete/leave operation for one chat."""

    chat_ref: str
    resolved_chat_id: Optional[int] = None
    success: bool
    error: Optional[str] = None
    flood_wait_seconds: Optional[int] = None


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
                folders = await self.storage.load_folders()
                chats = self._annotate_chats_with_folders(chats, folders)
                return chats if limit <= 0 else chats[:limit]
        chats = await self.sync_chats(limit=limit)
        return chats if limit <= 0 else chats[:limit]

    async def sync_chats(self, limit: int = 0) -> List[ChatInfo]:
        """Download chats from Telegram and update local cache.

        Pyrogram uses 0 as unlimited for many iterators; if it changes, pass a
        large explicit limit from CLI.
        """
        async with self._client_context() as client:
            me = await client.get_me()
            folders = await client.get_folders()
            archived_ids = await client.get_archived_chat_ids()
            chats = await client.get_dialogs(limit=limit)
        chats = self._annotate_chats_with_folders(chats, folders)
        chats = self._annotate_chats_with_archived(chats, set(archived_ids))
        await self.storage.save_folders(folders)
        await self.storage.save_chats(chats, me_id=me.id)
        return chats

    async def refresh_archived_status(self) -> List[ChatInfo]:
        """Refresh archived flag for cached chats."""
        chats = await self.storage.load_chats()
        async with self._client_context() as client:
            archived_ids = set(await client.get_archived_chat_ids())
        updated = self._annotate_chats_with_archived(chats, archived_ids)
        await self.storage.save_chats(updated)
        return updated

    async def sync_folders(self) -> List[FolderInfo]:
        """Download Telegram folders and update local cache."""
        async with self._client_context() as client:
            folders = await client.get_folders()
        await self.storage.save_folders(folders)
        chats = await self.storage.load_chats()
        if chats:
            await self.storage.save_chats(
                self._annotate_chats_with_folders(chats, folders)
            )
        return folders

    async def list_folders(self, cached: bool = True) -> List[FolderInfo]:
        """List Telegram folders from cache or API."""
        if cached:
            folders = await self.storage.load_folders()
            if folders:
                return folders
        return await self.sync_folders()

    async def list_chats_by_folder(
        self, folder_ref: Union[int, str], limit: int = 50
    ) -> List[ChatInfo]:
        """List cached chats belonging to a selected folder."""
        folders = await self.list_folders(cached=True)
        folder = self._resolve_folder(folder_ref, folders)
        if folder is None:
            return []
        chats = await self.list_chats(limit=0, cached=True)
        selected = [chat for chat in chats if folder.id in chat.folder_ids]
        return selected if limit <= 0 else selected[:limit]

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

    async def set_chats_archived(
        self, chat_refs: List[Union[int, str]], archived: bool
    ) -> List[ArchiveResult]:
        """Archive or unarchive multiple chats and update local cache."""
        resolved_refs = [await self.resolve_chat(chat_ref) for chat_ref in chat_refs]
        results: List[ArchiveResult] = []
        successful_ids: set[int] = set()

        async with self._client_context() as client:
            for chat_ref, resolved in zip(chat_refs, resolved_refs):
                try:
                    await client.set_chats_archived([resolved], archived=archived)
                    resolved_id = resolved if isinstance(resolved, int) else None
                    if resolved_id is not None:
                        successful_ids.add(resolved_id)
                    results.append(
                        ArchiveResult(
                            chat_ref=str(chat_ref),
                            resolved_chat_id=resolved_id,
                            success=True,
                        )
                    )
                except Exception as exc:
                    results.append(
                        ArchiveResult(
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
                [
                    chat.model_copy(update={"is_archived": archived})
                    if chat.id in successful_ids
                    else chat
                    for chat in chats
                ]
            )
        return results

    async def delete_and_leave_chats(
        self,
        chat_refs: List[Union[int, str]],
        delay_seconds: float = 15.0,
        wait_on_flood: bool = True,
        max_flood_wait_seconds: int = 900,
        stop_on_flood: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[DeleteAndLeaveResult]:
        """Delete/leave multiple chats with rate limiting and flood-wait handling."""
        results: List[DeleteAndLeaveResult] = []
        successful_ids: set[int] = set()

        async with self._client_context() as client:
            for index, chat_ref in enumerate(chat_refs):
                if index > 0 and delay_seconds > 0:
                    self._report_progress(
                        progress_callback,
                        f"Waiting {delay_seconds:.1f}s before next delete/leave...",
                    )
                    await asyncio.sleep(delay_seconds)

                resolved = await self.resolve_chat(chat_ref)
                while True:
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
                        break
                    except FloodWait as exc:
                        wait_seconds = int(exc.value)
                        if (
                            not wait_on_flood
                            or wait_seconds > max_flood_wait_seconds
                            or stop_on_flood
                        ):
                            results.append(
                                DeleteAndLeaveResult(
                                    chat_ref=str(chat_ref),
                                    resolved_chat_id=resolved
                                    if isinstance(resolved, int)
                                    else None,
                                    success=False,
                                    error=str(exc),
                                    flood_wait_seconds=wait_seconds,
                                )
                            )
                            if stop_on_flood:
                                return await self._finalize_delete_results(
                                    results, successful_ids
                                )
                            break

                        self._report_progress(
                            progress_callback,
                            f"Telegram requested FLOOD_WAIT {wait_seconds}s; sleeping and retrying {chat_ref}...",
                        )
                        await asyncio.sleep(wait_seconds + 1)
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
                        break

        return await self._finalize_delete_results(results, successful_ids)

    async def _finalize_delete_results(
        self, results: List[DeleteAndLeaveResult], successful_ids: set[int]
    ) -> List[DeleteAndLeaveResult]:
        """Remove successfully processed chats from cache and return results."""
        if successful_ids:
            chats = await self.storage.load_chats()
            await self.storage.save_chats(
                [chat for chat in chats if chat.id not in successful_ids]
            )
        return results

    def _report_progress(
        self, progress_callback: Optional[Callable[[str], None]], message: str
    ) -> None:
        """Report progress if callback is provided."""
        if progress_callback:
            progress_callback(message)

    def _annotate_chats_with_archived(
        self, chats: List[ChatInfo], archived_ids: set[int]
    ) -> List[ChatInfo]:
        """Add archive flag to chats."""
        return [
            chat.model_copy(update={"is_archived": chat.id in archived_ids})
            for chat in chats
        ]

    def _annotate_chats_with_folders(
        self, chats: List[ChatInfo], folders: List[FolderInfo]
    ) -> List[ChatInfo]:
        """Add folder ids/names to chats according to cached folder definitions."""
        annotated: List[ChatInfo] = []
        for chat in chats:
            folder_ids = []
            folder_names = []
            for folder in folders:
                if self._chat_matches_folder(chat, folder):
                    folder_ids.append(folder.id)
                    folder_names.append(folder.title)
            annotated.append(
                chat.model_copy(
                    update={"folder_ids": folder_ids, "folder_names": folder_names}
                )
            )
        return annotated

    def _chat_matches_folder(self, chat: ChatInfo, folder: FolderInfo) -> bool:
        """Return whether chat matches folder definition known from API."""
        if chat.id in folder.excluded_chat_ids:
            return False
        if chat.id in folder.explicit_chat_ids:
            return True
        if folder.exclude_muted or folder.exclude_read or folder.exclude_archived:
            # Dynamic read/mute/archive state is not currently stored in ChatInfo,
            # so avoid over-matching folders like "Unread".
            return False
        if folder.include_groups and chat.type in ("group", "supergroup"):
            return True
        if folder.include_channels and chat.type == "channel":
            return True
        if folder.include_bots and chat.type == "bot":
            return True
        # Contact/non-contact dynamic filters require user metadata that is not
        # currently stored in ChatInfo; explicit peers are still handled.
        return False

    def _resolve_folder(
        self, folder_ref: Union[int, str], folders: List[FolderInfo]
    ) -> Optional[FolderInfo]:
        """Resolve folder by id or case-insensitive title."""
        raw = str(folder_ref).strip().lower()
        for folder in folders:
            if raw == str(folder.id) or raw == folder.title.lower():
                return folder
        return None

    async def resolve_chat(self, ref: Union[int, str]) -> Union[int, str]:
        """Resolve chat reference for Telegram API calls.

        Accepts numeric id, @username, username, or a title substring from cache.
        "me" means Saved Messages: it resolves to the cached own id, or goes to
        Telegram as-is (InputPeerSelf) when the cache does not know it yet.
        @username resolves through the cache first so offline commands work too.
        Returns original reference if cache cannot resolve it.
        """
        if isinstance(ref, int):
            return ref
        raw = ref.strip()
        if raw.lower() in ("me", "@me"):
            me_id = (await self.storage.load_metadata()).me_id
            return me_id if me_id is not None else "me"
        if raw.lstrip("-").isdigit():
            return int(raw)
        if raw.startswith("@"):
            username = raw[1:].lower()
            for chat in await self.storage.load_chats():
                if chat.username and chat.username.lower() == username:
                    return chat.id
            return raw

        chats = await self.search_chats(raw, limit=1)
        if chats:
            return chats[0].id
        return raw

    def _client_context(self) -> TelegramClient:
        return self.client or TelegramClient()
