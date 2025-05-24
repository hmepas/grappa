"""Main Telegram client implementation."""

from typing import List, Optional, Union

from pyrogram import Client
from pyrogram.errors import AuthKeyUnregistered, SessionExpired, SessionRevoked
from pyrogram.types import Chat, ChatPreview

from config import get_settings
from data.models import ChatInfo, UserInfo


class TelegramClient:
    """Telegram client wrapper around Pyrogram."""

    def __init__(self) -> None:
        """Initialize the client with settings."""
        self.settings = get_settings()
        self._client: Optional[Client] = None
        self._is_connected = False

    async def connect(self) -> None:
        """Connect to Telegram and authenticate."""
        if self._client is None:
            session_path = (
                self.settings.app.session_dir
                / f"{self.settings.telegram.session_name}.session"
            )

            self._client = Client(
                name=str(session_path.with_suffix("")),
                api_id=self.settings.telegram.api_id,
                api_hash=self.settings.telegram.api_hash,
                phone_number=self.settings.telegram.phone_number or "",
                workdir=str(self.settings.app.session_dir),
            )

        try:
            await self._client.start()
            self._is_connected = True
            print(f"✅ Connected as: {await self.get_me()}")

        except (AuthKeyUnregistered, SessionExpired, SessionRevoked) as e:
            print(f"❌ Session error: {e}")
            await self._handle_session_error()

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self._client and self._is_connected:
            await self._client.stop()
            self._is_connected = False
            print("✅ Disconnected from Telegram")

    async def get_me(self) -> UserInfo:
        """Get information about the current user."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Client not connected")

        me = await self._client.get_me()
        return UserInfo(
            id=me.id,
            username=me.username,
            first_name=me.first_name,
            last_name=me.last_name,
            phone=me.phone_number,
            is_self=True,
        )

    async def get_dialogs(self, limit: int = 100) -> List[ChatInfo]:
        """Get list of user's dialogs (chats)."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Client not connected")

        dialogs = []
        async for dialog in self._client.get_dialogs(limit=limit):
            chat_info = self._convert_chat_to_info(dialog.chat)
            dialogs.append(chat_info)

        return dialogs

    async def get_chat_info(self, chat_id: int) -> ChatInfo:
        """Get information about a specific chat."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Client not connected")

        chat = await self._client.get_chat(chat_id)
        return self._convert_chat_to_info(chat)

    def _convert_chat_to_info(self, chat: Union[Chat, ChatPreview]) -> ChatInfo:
        """Convert Pyrogram Chat to our ChatInfo model."""
        return ChatInfo(
            id=chat.id,
            title=getattr(chat, "title", None),
            username=getattr(chat, "username", None),
            type=chat.type.value if hasattr(chat, "type") else "unknown",
            members_count=getattr(chat, "members_count", None),
        )

    async def _handle_session_error(self) -> None:
        """Handle session-related errors."""
        print("⚠️ Session is invalid or expired")
        print("Please delete the session file and restart the application")

        session_files = list(self.settings.app.session_dir.glob("*.session*"))
        if session_files:
            print(f"Session files to delete: {[str(f) for f in session_files]}")

        raise RuntimeError("Session authentication failed")

    async def __aenter__(self) -> "TelegramClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self, exc_type: object, exc_val: object, exc_tb: object
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()
