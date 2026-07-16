"""Tests for ChatManager chat resolution, search and archiving."""

from pathlib import Path
from typing import List, Union
from unittest.mock import Mock, patch

import pytest
from pyrogram.errors import FloodWait

from grappa.chat_manager import ChatManager
from grappa.data.models import ChatInfo
from grappa.storage.cache_storage import CacheStorage


class FakeArchiveClient:
    """Fake TelegramClient recording set_chats_archived calls."""

    def __init__(self, errors: List[Exception | None] | None = None) -> None:
        """Initialize with an optional per-call error script (None = success)."""
        self.calls: List[List[Union[int, str]]] = []
        self.errors = list(errors or [])

    async def __aenter__(self) -> "FakeArchiveClient":
        """Enter async context."""
        return self

    async def __aexit__(
        self, exc_type: object, exc_val: object, exc_tb: object
    ) -> None:
        """Exit async context."""
        return None

    async def set_chats_archived(
        self, chat_ids: List[Union[int, str]], archived: bool
    ) -> None:
        """Record the call and raise the next scripted error, if any."""
        self.calls.append(list(chat_ids))
        error = self.errors.pop(0) if self.errors else None
        if error is not None:
            raise error


@pytest.fixture
def storage(tmp_path: Path) -> CacheStorage:
    """Provide CacheStorage over a temporary directory."""
    with patch(
        "grappa.storage.cache_storage.get_settings",
        return_value=Mock(app=Mock(data_dir=tmp_path)),
    ):
        return CacheStorage(data_dir=tmp_path)


class TestResolveChat:
    """Tests for resolve_chat special references."""

    @pytest.mark.asyncio
    async def test_me_bypasses_cache_search(self, storage: CacheStorage) -> None:
        """The "me" reference never falls into substring cache search."""
        await storage.save_chats(
            [ChatInfo(id=-100200, title="Home media", type="supergroup")]
        )
        manager = ChatManager(storage=storage)

        assert await manager.resolve_chat("me") == "me"
        assert await manager.resolve_chat("Me") == "me"
        assert await manager.resolve_chat("@me") == "me"

    @pytest.mark.asyncio
    async def test_me_resolves_to_cached_own_id(self, storage: CacheStorage) -> None:
        """After chats sync stored me_id, "me" resolves to the numeric id."""
        await storage.save_chats(
            [ChatInfo(id=69144218, title="Saved Messages", type="private")],
            me_id=69144218,
        )
        manager = ChatManager(storage=storage)

        assert await manager.resolve_chat("me") == 69144218
        assert await manager.resolve_chat("@me") == 69144218

    @pytest.mark.asyncio
    async def test_username_ref_resolves_through_cache(
        self, storage: CacheStorage
    ) -> None:
        """@username resolves to the cached chat id for offline commands."""
        await storage.save_chats(
            [
                ChatInfo(id=69144218, title="Pavel", username="hmepas", type="private"),
                ChatInfo(id=-100200, title="Other", username="other", type="channel"),
            ]
        )
        manager = ChatManager(storage=storage)

        assert await manager.resolve_chat("@hmepas") == 69144218
        assert await manager.resolve_chat("@HMEPAS") == 69144218

    @pytest.mark.asyncio
    async def test_numeric_and_unknown_username_refs_still_work(
        self, storage: CacheStorage
    ) -> None:
        """Numeric ids resolve; unknown @usernames pass through to Telegram."""
        manager = ChatManager(storage=storage)

        assert await manager.resolve_chat("69144218") == 69144218
        assert await manager.resolve_chat("@hmepas") == "@hmepas"


class TestSetChatsArchived:
    """Tests for batched archive/unarchive."""

    @pytest.mark.asyncio
    async def test_chats_archived_in_batches(self, storage: CacheStorage) -> None:
        """Chats go to the client in batches of up to ARCHIVE_BATCH_SIZE."""
        client = FakeArchiveClient()
        manager = ChatManager(storage=storage, client=client)
        chat_ids = list(range(1, 251))

        results = await manager.set_chats_archived(chat_ids, archived=True)

        assert [len(call) for call in client.calls] == [100, 100, 50]
        assert all(result.success for result in results)
        assert [result.resolved_chat_id for result in results] == chat_ids

    @pytest.mark.asyncio
    async def test_failed_batch_falls_back_to_per_chat(
        self, storage: CacheStorage
    ) -> None:
        """A failed batch is retried per chat to keep per-chat error reporting."""
        client = FakeArchiveClient(
            errors=[ValueError("PEER_ID_INVALID"), None, ValueError("PEER_ID_INVALID")]
        )
        manager = ChatManager(storage=storage, client=client)

        results = await manager.set_chats_archived([11, 22, 33], archived=True)

        assert client.calls == [[11, 22, 33], [11], [22], [33]]
        assert [result.success for result in results] == [True, False, True]
        assert results[1].error == "PEER_ID_INVALID"

    @pytest.mark.asyncio
    async def test_flood_wait_sleeps_and_retries_batch(
        self, storage: CacheStorage
    ) -> None:
        """Waitable FloodWait sleeps and retries the same batch."""
        client = FakeArchiveClient(errors=[FloodWait(value=5)])
        manager = ChatManager(storage=storage, client=client)

        with patch("grappa.chat_manager.chat_manager.asyncio.sleep") as sleep_mock:
            results = await manager.set_chats_archived([11, 22], archived=True)

        assert client.calls == [[11, 22], [11, 22]]
        assert all(result.success for result in results)
        sleep_mock.assert_awaited_once_with(6)

    @pytest.mark.asyncio
    async def test_unwaitable_flood_fails_whole_batch(
        self, storage: CacheStorage
    ) -> None:
        """Flood ban with waiting disabled fails the batch without per-chat retries."""
        client = FakeArchiveClient(errors=[FloodWait(value=5)])
        manager = ChatManager(storage=storage, client=client)

        results = await manager.set_chats_archived(
            [11, 22], archived=True, wait_on_flood=False
        )

        assert client.calls == [[11, 22]]
        assert all(not result.success for result in results)


class TestSearchChats:
    """Tests for cached chat search."""

    @pytest.mark.asyncio
    async def test_saved_messages_found_by_title_and_username(
        self, storage: CacheStorage
    ) -> None:
        """Saved Messages chat matches both by title and by @username."""
        await storage.save_chats(
            [
                ChatInfo(
                    id=69144218,
                    title="Saved Messages",
                    username="hmepas",
                    type="private",
                ),
                ChatInfo(id=-100300, title="Unsaved drafts chat", type="supergroup"),
            ]
        )
        manager = ChatManager(storage=storage)

        by_title = await manager.search_chats("saved messages")
        assert by_title and by_title[0].id == 69144218

        by_username = await manager.search_chats("@hmepas")
        assert by_username and by_username[0].id == 69144218
