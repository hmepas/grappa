"""Data models for the Telegram client application."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class UserInfo(BaseModel):
    """Information about a Telegram user."""

    id: int = Field(description="Unique user ID")
    username: Optional[str] = Field(default=None, description="Username without @")
    first_name: Optional[str] = Field(default=None, description="User's first name")
    last_name: Optional[str] = Field(default=None, description="User's last name")
    phone: Optional[str] = Field(default=None, description="Phone number")
    is_self: bool = Field(default=False, description="Is this the current user")

    @property
    def display_name(self) -> str:
        """Get display name for the user."""
        if self.username:
            return f"@{self.username}"
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) if parts else f"User {self.id}"


class ChatInfo(BaseModel):
    """Information about a Telegram chat."""

    id: int = Field(description="Unique chat ID")
    title: Optional[str] = Field(default=None, description="Chat title")
    username: Optional[str] = Field(default=None, description="Chat username")
    type: str = Field(description="Chat type (private, group, supergroup, channel)")
    members_count: Optional[int] = Field(default=None, description="Number of members")
    last_seen: Optional[datetime] = Field(
        default=None, description="Last seen in dialogs"
    )
    message_count: Optional[int] = Field(
        default=None, description="Known message count"
    )
    activity_score: float = Field(default=0.0, description="Calculated activity score")
    access_count: int = Field(default=0, description="How often chat was accessed")
    is_deactivated: bool = Field(
        default=False, description="Telegram marks chat as deactivated"
    )
    migrated_to_chat_id: Optional[int] = Field(
        default=None, description="New chat id if this chat was migrated"
    )
    is_inaccessible: bool = Field(
        default=False, description="Chat looks inaccessible/dead for this account"
    )
    folder_ids: list[int] = Field(
        default_factory=list, description="Telegram folder/filter ids containing chat"
    )
    folder_names: list[str] = Field(
        default_factory=list, description="Telegram folder/filter names containing chat"
    )
    is_archived: bool = Field(default=False, description="Chat is in Telegram archive")

    @property
    def display_name(self) -> str:
        """Get display name for the chat."""
        if self.title:
            return self.title
        if self.username:
            return f"@{self.username}"
        return f"Chat {self.id}"


class FolderInfo(BaseModel):
    """Information about a Telegram dialog folder/filter."""

    id: int = Field(description="Telegram dialog filter id")
    title: str = Field(description="Folder title")
    explicit_chat_ids: list[int] = Field(
        default_factory=list, description="Pinned or explicitly included chat ids"
    )
    excluded_chat_ids: list[int] = Field(
        default_factory=list, description="Explicitly excluded chat ids"
    )
    include_contacts: bool = Field(default=False, description="Includes contacts")
    include_non_contacts: bool = Field(
        default=False, description="Includes non-contacts"
    )
    include_groups: bool = Field(default=False, description="Includes groups")
    include_channels: bool = Field(default=False, description="Includes channels")
    include_bots: bool = Field(default=False, description="Includes bots")
    exclude_muted: bool = Field(default=False, description="Excludes muted chats")
    exclude_read: bool = Field(default=False, description="Excludes read chats")
    exclude_archived: bool = Field(default=False, description="Excludes archived chats")

    @property
    def explicit_count(self) -> int:
        """Return number of explicit chats in this folder."""
        return len(set(self.explicit_chat_ids))


class MessageInfo(BaseModel):
    """Information about a Telegram message."""

    id: int = Field(description="Message ID")
    chat_id: int = Field(description="Chat ID where message was sent")
    from_user_id: Optional[int] = Field(default=None, description="Sender user ID")
    text: Optional[str] = Field(default=None, description="Message text")
    date: datetime = Field(description="Message timestamp")
    reply_to_message_id: Optional[int] = Field(
        default=None, description="ID of replied message"
    )
    media_type: Optional[str] = Field(
        default=None, description="Type of media (photo, video, document, etc.)"
    )
    media_file_id: Optional[str] = Field(
        default=None, description="Telegram media file id"
    )
    downloaded_media_path: Optional[Path] = Field(
        default=None, description="Local downloaded media path"
    )

    def get_message_link(self, chat_username: Optional[str] = None) -> Optional[str]:
        """Generate link to the message."""
        if chat_username:
            return f"https://t.me/{chat_username}/{self.id}"
        # For private chats or chats without username, we can't generate public links
        return None


class MentionInfo(BaseModel):
    """Information about a user mention in a chat."""

    message: MessageInfo = Field(description="Message containing the mention")
    chat: ChatInfo = Field(description="Chat where mention occurred")
    mentioned_user: UserInfo = Field(description="User who was mentioned")
    mention_text: str = Field(description="Exact mention text from message")
    context_before: str = Field(
        default="", description="Text before mention for context"
    )
    context_after: str = Field(default="", description="Text after mention for context")

    @property
    def message_link(self) -> Optional[str]:
        """Get link to the message with mention."""
        return self.message.get_message_link(self.chat.username)

    @property
    def context_summary(self) -> str:
        """Get summary of mention context."""
        max_context_len = 50
        before = (
            f"...{self.context_before[-max_context_len:]}"
            if len(self.context_before) > max_context_len
            else self.context_before
        )
        after = (
            f"{self.context_after[:max_context_len]}..."
            if len(self.context_after) > max_context_len
            else self.context_after
        )
        return f"{before}[{self.mention_text}]{after}".strip()
