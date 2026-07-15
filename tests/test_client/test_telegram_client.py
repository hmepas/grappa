"""Tests for TelegramClient."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grappa.client.telegram_client import TelegramClient
from grappa.data.models import MessageInfo, UserInfo


def make_raw_message(message_id: int) -> SimpleNamespace:
    """Build a minimal Pyrogram-like message object."""
    return SimpleNamespace(
        id=message_id,
        chat=SimpleNamespace(id=-100123),
        from_user=None,
        media=None,
        text=f"message {message_id}",
        caption=None,
        reply_to_message=None,
        date=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


class TestTelegramClient:
    """Test cases for TelegramClient."""

    @pytest.fixture
    async def client(self, mock_settings):
        """Create a client instance for testing."""
        with patch(
            "grappa.client.telegram_client.get_settings", return_value=mock_settings
        ):
            return TelegramClient()

    @pytest.mark.asyncio
    async def test_initialization(self, client):
        """Test client initialization."""
        assert client._client is None
        assert client._is_connected is False
        assert client.settings is not None

    @pytest.mark.asyncio
    async def test_connect_success(self, client, mock_pyrogram_client):
        """Test successful connection."""
        # Mock user object with proper attributes
        mock_user = MagicMock()
        mock_user.id = 123456789
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        mock_user.phone_number = "+1234567890"

        mock_pyrogram_client.get_me.return_value = mock_user

        with patch(
            "grappa.client.telegram_client.Client", return_value=mock_pyrogram_client
        ):
            await client.connect()

            assert client._is_connected is True
            mock_pyrogram_client.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_me(self, client, mock_pyrogram_client):
        """Test getting current user info."""
        mock_user = MagicMock()
        mock_user.id = 123456789
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        mock_user.phone_number = "+1234567890"

        mock_pyrogram_client.get_me.return_value = mock_user

        with patch(
            "grappa.client.telegram_client.Client", return_value=mock_pyrogram_client
        ):
            await client.connect()
            me = await client.get_me()

            assert isinstance(me, UserInfo)
            assert me.id == 123456789
            assert me.username == "testuser"
            assert me.first_name == "Test"
            assert me.is_self is True

    @pytest.mark.asyncio
    async def test_disconnect(self, client, mock_pyrogram_client):
        """Test disconnection."""
        # Mock user for connect
        mock_user = MagicMock()
        mock_user.id = 123456789
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        mock_user.phone_number = "+1234567890"
        mock_pyrogram_client.get_me.return_value = mock_user

        with patch(
            "grappa.client.telegram_client.Client", return_value=mock_pyrogram_client
        ):
            await client.connect()
            await client.disconnect()

            assert client._is_connected is False
            mock_pyrogram_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self, client, mock_pyrogram_client):
        """Test using client as async context manager."""
        mock_user = MagicMock()
        mock_user.id = 123456789
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        mock_user.phone_number = "+1234567890"
        mock_pyrogram_client.get_me.return_value = mock_user

        with patch(
            "grappa.client.telegram_client.Client", return_value=mock_pyrogram_client
        ):
            async with client as c:
                assert c is client
                assert c._is_connected is True

            # Should be disconnected after exiting context
            mock_pyrogram_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_chat_messages_stops_at_known_id(self, client):
        """Iteration stops at the first message with id <= stop_before_id."""
        consumed = []

        def get_chat_history(**kwargs):
            async def generator():
                for message_id in (5, 4, 3, 2, 1):
                    consumed.append(message_id)
                    yield make_raw_message(message_id)

            return generator()

        client._client = MagicMock()
        client._client.get_chat_history = get_chat_history
        client._is_connected = True

        messages = await client.get_chat_messages(
            chat_id=-100123, limit=0, stop_before_id=3
        )

        assert [m.id for m in messages] == [5, 4]
        assert consumed == [5, 4, 3]

    @pytest.mark.asyncio
    async def test_download_media_uses_original_file_name(self, client, tmp_path):
        """Downloaded file is named <message_id>_<original_name>."""
        message = MessageInfo(
            id=77,
            chat_id=-100123,
            date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            media_type="document",
            media_file_id="file-id",
            media_file_name="report.pdf",
        )
        expected = tmp_path / "77_report.pdf"
        client._client = MagicMock()
        client._client.download_media = AsyncMock(return_value=str(expected))
        client._is_connected = True

        result = await client.download_message_media(message, tmp_path)

        assert result == expected
        client._client.download_media.assert_awaited_once_with(
            message="file-id", file_name=str(expected)
        )

    @pytest.mark.asyncio
    async def test_download_media_without_name_gets_id_prefix(self, client, tmp_path):
        """Pyrogram-generated file name is prefixed with the message id."""
        message = MessageInfo(
            id=88,
            chat_id=-100123,
            date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            media_type="photo",
            media_file_id="file-id",
        )
        generated = tmp_path / "photo_2026-07-01_00-00-00.jpg"
        generated.write_bytes(b"jpeg")
        client._client = MagicMock()
        client._client.download_media = AsyncMock(return_value=str(generated))
        client._is_connected = True

        result = await client.download_message_media(message, tmp_path)

        assert result == tmp_path / "88_photo_2026-07-01_00-00-00.jpg"
        assert result.exists()
        assert not generated.exists()

    @pytest.mark.asyncio
    async def test_operations_without_connection(self, client):
        """Test that operations fail when not connected."""
        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.get_me()

        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.get_dialogs()

        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.get_chat_info(123)
