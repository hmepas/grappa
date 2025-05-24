"""Tests for TelegramClient."""

from unittest.mock import MagicMock, patch

import pytest

from client.telegram_client import TelegramClient
from data.models import UserInfo


class TestTelegramClient:
    """Test cases for TelegramClient."""

    @pytest.fixture
    async def client(self, mock_settings):
        """Create a client instance for testing."""
        with patch("client.telegram_client.get_settings", return_value=mock_settings):
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

        with patch("client.telegram_client.Client", return_value=mock_pyrogram_client):
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

        with patch("client.telegram_client.Client", return_value=mock_pyrogram_client):
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

        with patch("client.telegram_client.Client", return_value=mock_pyrogram_client):
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

        with patch("client.telegram_client.Client", return_value=mock_pyrogram_client):
            async with client as c:
                assert c is client
                assert c._is_connected is True

            # Should be disconnected after exiting context
            mock_pyrogram_client.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_operations_without_connection(self, client):
        """Test that operations fail when not connected."""
        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.get_me()

        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.get_dialogs()

        with pytest.raises(RuntimeError, match="Client not connected"):
            await client.get_chat_info(123)
