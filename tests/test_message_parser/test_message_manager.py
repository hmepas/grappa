"""Tests for MessageManager sync and media caching."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import Mock, patch

import pytest

from grappa.chat_manager import ChatManager
from grappa.data.models import MessageInfo
from grappa.message_parser import MessageManager
from grappa.storage.cache_storage import CacheStorage

CHAT_ID = -100123


def make_message(message_id: int, **kwargs: Any) -> MessageInfo:
    """Build a MessageInfo with sane defaults."""
    defaults: dict[str, Any] = {
        "id": message_id,
        "chat_id": CHAT_ID,
        "text": f"message {message_id}",
        "date": datetime(2026, 7, 1, 12, 0, message_id % 60, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    return MessageInfo(**defaults)


class FakeClient:
    """Fake TelegramClient exposing only what MessageManager needs."""

    def __init__(self, messages: List[MessageInfo]) -> None:
        """Initialize with messages to serve."""
        self.messages = messages
        self.calls: List[dict[str, Any]] = []

    async def __aenter__(self) -> "FakeClient":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Exit async context."""
        return None

    async def get_chat_messages(
        self,
        chat_id: Any,
        limit: int = 100,
        offset_date: Optional[datetime] = None,
        stop_before_id: Optional[int] = None,
    ) -> List[MessageInfo]:
        """Return served messages newer than stop_before_id."""
        self.calls.append(
            {"chat_id": chat_id, "limit": limit, "stop_before_id": stop_before_id}
        )
        if stop_before_id is None:
            return list(self.messages)
        return [m for m in self.messages if m.id > stop_before_id]

    async def download_message_media(
        self, message: MessageInfo, output_dir: Path
    ) -> Optional[Path]:
        """Write a stub media file and return its path."""
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{message.id}_media.bin"
        path.write_bytes(b"data")
        return path

    async def send_message(self, **kwargs: Any) -> MessageInfo:
        """Record a send_message call and return a stub sent message."""
        self.calls.append({"method": "send_message", **kwargs})
        return make_message(100, text=kwargs.get("text"))

    async def send_file(self, **kwargs: Any) -> MessageInfo:
        """Record a send_file call and return a stub sent message."""
        self.calls.append({"method": "send_file", **kwargs})
        return make_message(101, text=kwargs.get("caption"))


@pytest.fixture
def storage(tmp_path: Path) -> CacheStorage:
    """Provide CacheStorage over a temporary directory."""
    with patch(
        "grappa.storage.cache_storage.get_settings",
        return_value=Mock(app=Mock(data_dir=tmp_path)),
    ):
        return CacheStorage(data_dir=tmp_path)


def make_manager(
    storage: CacheStorage, client: FakeClient, tmp_path: Path
) -> MessageManager:
    """Build MessageManager with mocked settings and fake client."""
    settings = Mock()
    settings.app.downloads_dir = tmp_path / "downloads"
    with patch(
        "grappa.message_parser.message_manager.get_settings", return_value=settings
    ):
        return MessageManager(
            storage=storage,
            chat_manager=ChatManager(storage=storage),
            client=client,  # type: ignore[arg-type]
        )


class TestSyncChat:
    """Tests for delta sync."""

    @pytest.mark.asyncio
    async def test_first_sync_downloads_everything(
        self, storage: CacheStorage, tmp_path: Path
    ) -> None:
        """Empty cache leads to a full download without stop id."""
        client = FakeClient([make_message(3), make_message(2), make_message(1)])
        manager = make_manager(storage, client, tmp_path)

        new_messages = await manager.sync_chat(CHAT_ID, include_media=False)

        assert len(new_messages) == 3
        assert client.calls[0]["stop_before_id"] is None
        cached = await storage.load_messages(CHAT_ID)
        assert [m.id for m in cached] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_second_sync_fetches_only_delta(
        self, storage: CacheStorage, tmp_path: Path
    ) -> None:
        """Sync passes the max cached id and merges only new messages."""
        await storage.save_messages(CHAT_ID, [make_message(1), make_message(2)])
        client = FakeClient([make_message(4), make_message(3)])
        manager = make_manager(storage, client, tmp_path)

        new_messages = await manager.sync_chat(CHAT_ID, include_media=False)

        assert [m.id for m in new_messages] == [4, 3]
        assert client.calls[0]["stop_before_id"] == 2
        cached = await storage.load_messages(CHAT_ID)
        assert [m.id for m in cached] == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_sync_downloads_media_for_new_messages(
        self, storage: CacheStorage, tmp_path: Path
    ) -> None:
        """Media of new messages is downloaded and path is cached."""
        message = make_message(5, media_type="photo", media_file_id="abc")
        client = FakeClient([message])
        manager = make_manager(storage, client, tmp_path)

        new_messages = await manager.sync_chat(CHAT_ID)

        assert new_messages[0].downloaded_media_path is not None
        assert new_messages[0].downloaded_media_path.exists()
        cached = await storage.load_messages(CHAT_ID)
        assert cached[0].downloaded_media_path == new_messages[0].downloaded_media_path

    @pytest.mark.asyncio
    async def test_sync_uses_custom_media_dir(
        self, storage: CacheStorage, tmp_path: Path
    ) -> None:
        """Custom media_dir overrides the default downloads directory."""
        message = make_message(6, media_type="photo", media_file_id="abc")
        client = FakeClient([message])
        manager = make_manager(storage, client, tmp_path)
        custom_dir = tmp_path / "custom_media"

        new_messages = await manager.sync_chat(CHAT_ID, media_dir=custom_dir)

        path = new_messages[0].downloaded_media_path
        assert path is not None
        assert path.parent == custom_dir


class TestSendMessage:
    """Tests for sending messages and files."""

    @pytest.mark.asyncio
    async def test_send_converts_markdown(
        self, storage: CacheStorage, tmp_path: Path
    ) -> None:
        """Text is converted to Telegram markup before sending."""
        client = FakeClient([])
        manager = make_manager(storage, client, tmp_path)

        sent = await manager.send_message(CHAT_ID, text="> цитата\n**жирный**")

        call = client.calls[0]
        assert call["method"] == "send_message"
        assert call["text"] == "<blockquote>цитата</blockquote>\n**жирный**"
        assert call["disable_markup"] is False
        assert sent.id == 100

    @pytest.mark.asyncio
    async def test_send_plain_skips_conversion(
        self, storage: CacheStorage, tmp_path: Path
    ) -> None:
        """markdown=False sends the text untouched with markup disabled."""
        client = FakeClient([])
        manager = make_manager(storage, client, tmp_path)

        await manager.send_message(CHAT_ID, text="> as is", markdown=False)

        call = client.calls[0]
        assert call["text"] == "> as is"
        assert call["disable_markup"] is True

    @pytest.mark.asyncio
    async def test_send_file_with_caption_and_reply(
        self, storage: CacheStorage, tmp_path: Path
    ) -> None:
        """Files go through send_file with converted caption and reply id."""
        client = FakeClient([])
        manager = make_manager(storage, client, tmp_path)
        attachment = tmp_path / "report.pdf"

        await manager.send_message(
            CHAT_ID,
            text="**подпись**",
            file_path=attachment,
            reply_to_message_id=42,
        )

        call = client.calls[0]
        assert call["method"] == "send_file"
        assert call["file_path"] == attachment
        assert call["caption"] == "**подпись**"
        assert call["reply_to_message_id"] == 42

    @pytest.mark.asyncio
    async def test_sent_message_is_not_cached(
        self, storage: CacheStorage, tmp_path: Path
    ) -> None:
        """Sending must not advance the cached max id past unseen messages."""
        await storage.save_messages(CHAT_ID, [make_message(1)])
        client = FakeClient([])
        manager = make_manager(storage, client, tmp_path)

        await manager.send_message(CHAT_ID, text="hello")

        cached = await storage.load_messages(CHAT_ID)
        assert [m.id for m in cached] == [1]


class TestSaveMessagesMerge:
    """Tests for cache merge behavior."""

    @pytest.mark.asyncio
    async def test_merge_preserves_downloaded_media_path(
        self, storage: CacheStorage, tmp_path: Path
    ) -> None:
        """Merge keeps downloaded_media_path from the cached copy."""
        media_path = tmp_path / "old_media.jpg"
        old = make_message(
            1,
            media_type="photo",
            media_file_id="abc",
            downloaded_media_path=media_path,
        )
        await storage.save_messages(CHAT_ID, [old])

        fresh = make_message(1, media_type="photo", media_file_id="abc")
        await storage.save_messages(CHAT_ID, [fresh])

        cached = await storage.load_messages(CHAT_ID)
        assert cached[0].downloaded_media_path == media_path
