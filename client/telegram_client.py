"""Main Telegram client implementation."""

from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union, cast

from pyrogram import Client
from pyrogram.errors import AuthKeyUnregistered, SessionExpired, SessionRevoked
from pyrogram.raw import functions
from pyrogram.raw import types as raw_types
from pyrogram.types import Chat, ChatPreview

from config import get_settings
from data.models import ChatInfo, FolderInfo, MessageInfo, UserInfo


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

        client = cast(Any, self._client)
        me = await client.get_me()
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

        client = cast(Any, self._client)
        dialogs = []
        async for dialog in client.get_dialogs(limit=limit):
            chat_info = self._convert_chat_to_info(dialog.chat)
            chat_info = await self._enrich_chat_status_if_needed(chat_info)
            dialogs.append(chat_info)

        return dialogs

    async def get_archived_chat_ids(self, limit: int = 0) -> List[int]:
        """Get chat ids from Telegram archive folder."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Client not connected")

        client = cast(Any, self._client)
        result = await client.invoke(
            functions.messages.GetDialogs(
                offset_date=0,
                offset_id=0,
                offset_peer=raw_types.InputPeerEmpty(),
                limit=limit or 10000,
                hash=0,
                folder_id=1,
            )
        )
        archived_ids = []
        for dialog in getattr(result, "dialogs", []) or []:
            chat_id = self._peer_to_chat_id(getattr(dialog, "peer", None))
            if chat_id is not None:
                archived_ids.append(chat_id)
        return list(dict.fromkeys(archived_ids))

    async def get_folders(self) -> List[FolderInfo]:
        """Get Telegram dialog folders/filters."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Client not connected")

        client = cast(Any, self._client)
        raw_filters = await client.invoke(functions.messages.GetDialogFilters())
        folders: List[FolderInfo] = []
        for raw_filter in raw_filters:
            folder_id = getattr(raw_filter, "id", None)
            title = getattr(raw_filter, "title", None)
            if folder_id is None or title is None:
                continue

            pinned_ids = [
                chat_id
                for chat_id in (
                    self._input_peer_to_chat_id(peer)
                    for peer in getattr(raw_filter, "pinned_peers", []) or []
                )
                if chat_id is not None
            ]
            included_ids = [
                chat_id
                for chat_id in (
                    self._input_peer_to_chat_id(peer)
                    for peer in getattr(raw_filter, "include_peers", []) or []
                )
                if chat_id is not None
            ]
            excluded_ids = [
                chat_id
                for chat_id in (
                    self._input_peer_to_chat_id(peer)
                    for peer in getattr(raw_filter, "exclude_peers", []) or []
                )
                if chat_id is not None
            ]

            folders.append(
                FolderInfo(
                    id=folder_id,
                    title=title,
                    explicit_chat_ids=list(dict.fromkeys(pinned_ids + included_ids)),
                    excluded_chat_ids=list(dict.fromkeys(excluded_ids)),
                    include_contacts=bool(getattr(raw_filter, "contacts", False)),
                    include_non_contacts=bool(
                        getattr(raw_filter, "non_contacts", False)
                    ),
                    include_groups=bool(getattr(raw_filter, "groups", False)),
                    include_channels=bool(getattr(raw_filter, "broadcasts", False)),
                    include_bots=bool(getattr(raw_filter, "bots", False)),
                    exclude_muted=bool(getattr(raw_filter, "exclude_muted", False)),
                    exclude_read=bool(getattr(raw_filter, "exclude_read", False)),
                    exclude_archived=bool(
                        getattr(raw_filter, "exclude_archived", False)
                    ),
                )
            )
        return folders

    async def get_chat_info(self, chat_id: Union[int, str]) -> ChatInfo:
        """Get information about a specific chat."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Client not connected")

        client = cast(Any, self._client)
        chat = await client.get_chat(chat_id)
        chat_info = self._convert_chat_to_info(chat)
        return await self._enrich_chat_status_if_needed(chat_info)

    async def get_chat_messages(
        self,
        chat_id: Union[int, str],
        limit: int = 100,
        offset_date: Optional[datetime] = None,
    ) -> List[MessageInfo]:
        """Get recent chat messages."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Client not connected")

        client = cast(Any, self._client)
        kwargs: dict[str, Any] = {"chat_id": chat_id, "limit": limit}
        if offset_date is not None:
            kwargs["offset_date"] = offset_date

        messages: List[MessageInfo] = []
        async for message in client.get_chat_history(**kwargs):
            messages.append(self._convert_message_to_info(message))
        return messages

    async def search_messages(
        self,
        query: str,
        chat_id: Optional[Union[int, str]] = None,
        limit: int = 100,
    ) -> List[MessageInfo]:
        """Search messages globally or inside a selected chat."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Client not connected")

        client = cast(Any, self._client)
        messages: List[MessageInfo] = []
        if chat_id is None and hasattr(client, "search_global"):
            async for message in client.search_global(query=query, limit=limit):
                messages.append(self._convert_message_to_info(message))
            return messages

        if chat_id is None:
            raise ValueError(
                "Global Telegram search is not supported by this Pyrogram version"
            )

        async for message in client.search_messages(
            chat_id=chat_id, query=query, limit=limit
        ):
            messages.append(self._convert_message_to_info(message))
        return messages

    async def delete_and_leave_chat(self, chat_id: Union[int, str]) -> None:
        """Leave a chat and delete it from dialogs/history where possible.

        For groups/supergroups/channels Pyrogram's leave_chat(..., delete=True)
        removes the dialog after leaving. Private chats cannot be "left", so we
        fall back to deleting local chat history.
        """
        if not self._client or not self._is_connected:
            raise RuntimeError("Client not connected")

        client = cast(Any, self._client)
        chat = await client.get_chat(chat_id)
        chat_type = getattr(getattr(chat, "type", None), "value", None)

        if chat_type == "private":
            await client.delete_chat_history(chat_id=chat_id, revoke=False)
            return

        await client.leave_chat(chat_id=chat_id, delete=True)

    async def download_message_media(
        self, message: MessageInfo, output_dir: Path
    ) -> Optional[Path]:
        """Download media for a message, if it has media."""
        if not self._client or not self._is_connected:
            raise RuntimeError("Client not connected")
        if not message.media_type or not message.media_file_id:
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        client = cast(Any, self._client)
        result = await client.download_media(
            message=message.media_file_id,
            file_name=str(output_dir / f"{message.chat_id}_{message.id}_"),
        )
        return Path(str(result)) if result else None

    def _convert_chat_to_info(self, chat: Union[Chat, ChatPreview]) -> ChatInfo:
        """Convert Pyrogram Chat to our ChatInfo model."""
        chat_obj = cast(Any, chat)
        chat_type = getattr(chat_obj, "type", None)
        return ChatInfo(
            id=chat_obj.id,
            title=getattr(chat_obj, "title", None),
            username=getattr(chat_obj, "username", None),
            type=chat_type.value
            if chat_type is not None and hasattr(chat_type, "value")
            else "unknown",
            members_count=getattr(chat_obj, "members_count", None),
        )

    async def _enrich_chat_status_if_needed(self, chat: ChatInfo) -> ChatInfo:
        """Enrich suspected dead/migrated basic groups via raw Telegram API."""
        if chat.type == "private" or chat.members_count not in (0, None):
            return chat
        if not self._client or not self._is_connected:
            return chat

        updates: dict[str, object] = {}
        if chat.members_count == 0 and chat.type != "private":
            updates["is_inaccessible"] = True

        if chat.type != "group":
            return chat.model_copy(update=updates) if updates else chat

        client = cast(Any, self._client)
        raw_chat_id = abs(chat.id)
        try:
            full_chat = await client.invoke(
                functions.messages.GetFullChat(chat_id=raw_chat_id)
            )
        except Exception:
            return chat.model_copy(update=updates) if updates else chat

        raw_chats = getattr(full_chat, "chats", []) or []
        raw_chat = raw_chats[0] if raw_chats else None
        if raw_chat is None:
            return chat.model_copy(update=updates) if updates else chat

        if getattr(raw_chat, "deactivated", False):
            updates["is_deactivated"] = True
            updates["is_inaccessible"] = True

        migrated_to = getattr(raw_chat, "migrated_to", None)
        channel_id = getattr(migrated_to, "channel_id", None)
        if channel_id is not None:
            updates["migrated_to_chat_id"] = int(f"-100{channel_id}")
            updates["is_inaccessible"] = True

        return chat.model_copy(update=updates) if updates else chat

    def _convert_message_to_info(self, message: object) -> MessageInfo:
        """Convert Pyrogram Message to our MessageInfo model."""
        chat = getattr(message, "chat", None)
        from_user = getattr(message, "from_user", None)
        media = getattr(message, "media", None)
        media_type = (
            media.value if media is not None and hasattr(media, "value") else None
        )
        text = getattr(message, "text", None) or getattr(message, "caption", None)
        reply_to = getattr(message, "reply_to_message", None)

        return MessageInfo(
            id=getattr(message, "id"),
            chat_id=getattr(chat, "id", 0),
            from_user_id=getattr(from_user, "id", None),
            text=text,
            date=getattr(message, "date"),
            reply_to_message_id=getattr(reply_to, "id", None),
            media_type=media_type,
            media_file_id=self._extract_media_file_id(message, media_type),
        )

    def _input_peer_to_chat_id(self, peer: object) -> Optional[int]:
        """Convert raw InputPeer to Pyrogram-style chat id."""
        return self._peer_to_chat_id(peer)

    def _peer_to_chat_id(self, peer: object) -> Optional[int]:
        """Convert raw Peer/InputPeer to Pyrogram-style chat id."""
        user_id = getattr(peer, "user_id", None)
        if user_id is not None:
            return int(user_id)
        chat_id = getattr(peer, "chat_id", None)
        if chat_id is not None:
            return -int(chat_id)
        channel_id = getattr(peer, "channel_id", None)
        if channel_id is not None:
            return int(f"-100{channel_id}")
        return None

    def _extract_media_file_id(
        self, message: object, media_type: Optional[str]
    ) -> Optional[str]:
        """Extract file_id for known media types."""
        if not media_type:
            return None
        media_obj = getattr(message, media_type, None)
        return getattr(media_obj, "file_id", None)

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
