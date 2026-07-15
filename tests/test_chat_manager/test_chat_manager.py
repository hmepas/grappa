"""Tests for ChatManager chat resolution and search."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from grappa.chat_manager import ChatManager
from grappa.data.models import ChatInfo
from grappa.storage.cache_storage import CacheStorage


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
