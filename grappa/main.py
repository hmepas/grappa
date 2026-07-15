"""Main CLI application."""

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

import click
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from grappa.chat_manager import ChatManager
from grappa.client import TelegramClient
from grappa.config import GLOBAL_ENV_FILE, get_settings
from grappa.data.models import ChatInfo, FolderInfo, MessageInfo
from grappa.message_parser import MessageManager, parse_cli_date
from grappa.storage.cache_storage import CacheStorage

console = Console()


def _ensure_configured() -> None:
    """Run first-time onboarding when Telegram API credentials are missing."""
    if "--help" in sys.argv[1:]:
        return
    try:
        get_settings()
        return
    except ValidationError as error:
        validation_error = error

    existing = [
        path for path in (Path.cwd() / ".env", GLOBAL_ENV_FILE) if path.exists()
    ]
    if existing:
        files = ", ".join(str(path) for path in existing)
        console.print(
            f"❌ Configuration in {files} is invalid:\n{validation_error}",
            style="red",
        )
        raise SystemExit(1)

    console.print(
        "⚙️  Grappa is not configured yet: Telegram API credentials are missing.",
        style="yellow",
    )
    console.print(
        "Get them at https://my.telegram.org/apps - "
        f"answers will be saved to {GLOBAL_ENV_FILE}"
    )
    try:
        api_id = click.prompt("TELEGRAM_API_ID", type=int)
        api_hash = click.prompt("TELEGRAM_API_HASH")
        phone = click.prompt(
            "TELEGRAM_PHONE_NUMBER (e.g. +79991234567, Enter to skip)",
            default="",
            show_default=False,
        )
    except click.Abort:
        console.print(
            "\nAborted. Set TELEGRAM_API_ID / TELEGRAM_API_HASH via environment "
            "variables or a .env file and retry.",
            style="red",
        )
        raise SystemExit(1)

    lines = [f"TELEGRAM_API_ID={api_id}", f"TELEGRAM_API_HASH={api_hash}"]
    if phone:
        lines.append(f"TELEGRAM_PHONE_NUMBER={phone}")
    GLOBAL_ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    GLOBAL_ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        get_settings()
    except ValidationError as error:
        console.print(f"❌ Configuration is still invalid:\n{error}", style="red")
        raise SystemExit(1)
    console.print(f"✅ Credentials saved to {GLOBAL_ENV_FILE}", style="green")


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug mode")
def cli(debug: bool) -> None:
    """Grappa - AI-augmented Telegram client."""
    if debug:
        console.print("🐛 Debug mode enabled", style="yellow")
    _ensure_configured()


@cli.command()
async def test_connection() -> None:
    """Test connection to Telegram."""
    try:
        async with TelegramClient() as client:
            me = await client.get_me()
            console.print(
                f"✅ Connected successfully as: {me.display_name}", style="green"
            )
    except Exception as e:
        console.print(f"❌ Connection failed: {e}", style="red")


@cli.group()
def chats() -> None:
    """Chat cache, sync and search commands."""


@chats.command("sync")
@click.option("--limit", default=0, help="How many dialogs to sync; 0 means all")
async def sync_chats(limit: int) -> None:
    """Synchronize local chat cache from Telegram."""
    try:
        manager = ChatManager()
        console.print("⏳ Syncing chats from Telegram...", style="yellow")
        chats_result = await manager.sync_chats(limit=limit)
        console.print(f"✅ Synced {len(chats_result)} chats", style="green")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@chats.command("list")
@click.option("--limit", default=20, help="Limit number of chats to show; 0 means all")
@click.option("--api", "from_api", is_flag=True, help="Force loading from Telegram API")
@click.option("--private-only", is_flag=True, help="Show only 1-on-1 private chats")
@click.option(
    "--non-private", is_flag=True, help="Show all chats except 1-on-1 private chats"
)
@click.option(
    "--zero-members",
    is_flag=True,
    help="Show only chats with members_count=0, usually inaccessible/dead chats",
)
@click.option("--deactivated", is_flag=True, help="Show only deactivated chats")
@click.option(
    "--migrated", is_flag=True, help="Show only chats migrated to another chat"
)
@click.option("--inaccessible", is_flag=True, help="Show only inaccessible/dead chats")
@click.option("--archived", is_flag=True, help="Show only archived chats")
@click.option("--exclude-archived", is_flag=True, help="Hide archived chats")
@click.option("--plain", is_flag=True, help="Print TSV rows without Rich table")
@click.option("--ids-only", is_flag=True, help="Print only chat ids, one per line")
async def chats_list(
    limit: int,
    from_api: bool,
    private_only: bool,
    non_private: bool,
    zero_members: bool,
    deactivated: bool,
    migrated: bool,
    inaccessible: bool,
    archived: bool,
    exclude_archived: bool,
    plain: bool,
    ids_only: bool,
) -> None:
    """List chats from cache by default, or from Telegram API."""
    try:
        if private_only and non_private:
            raise click.ClickException(
                "Use either --private-only or --non-private, not both"
            )
        if archived and exclude_archived:
            raise click.ClickException(
                "Use either --archived or --exclude-archived, not both"
            )

        manager = ChatManager()
        source_chats = await manager.list_chats(
            limit=0, cached=not from_api, force_refresh=from_api
        )
        filtered_chats = _filter_chats(
            source_chats,
            private_only,
            non_private,
            zero_members,
            deactivated,
            migrated,
            inaccessible,
            archived,
            exclude_archived,
        )
        chats_result = filtered_chats if limit <= 0 else filtered_chats[:limit]
        _print_chats(
            chats_result,
            title=(
                f"Chats: showing {len(chats_result)} of {len(filtered_chats)} "
                f"filtered / {len(source_chats)} total"
            ),
            plain=plain,
            ids_only=ids_only,
        )
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@cli.group()
def folders() -> None:
    """Telegram folder commands."""


@folders.command("sync")
async def folders_sync() -> None:
    """Synchronize Telegram folders cache."""
    try:
        manager = ChatManager()
        folders_result = await manager.sync_folders()
        console.print(f"✅ Synced {len(folders_result)} folders", style="green")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@folders.command("list")
@click.option("--api", "from_api", is_flag=True, help="Force loading from Telegram API")
@click.option("--plain", is_flag=True, help="Print TSV rows without Rich table")
@click.option("--ids-only", is_flag=True, help="Print only folder ids, one per line")
async def folders_list(from_api: bool, plain: bool, ids_only: bool) -> None:
    """List Telegram folders."""
    try:
        manager = ChatManager()
        folders_result = await manager.list_folders(cached=not from_api)
        _print_folders(folders_result, plain=plain, ids_only=ids_only)
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@folders.command("chats")
@click.argument("folder")
@click.option("--limit", default=20, help="Limit number of chats to show; 0 means all")
@click.option("--plain", is_flag=True, help="Print TSV rows without Rich table")
@click.option("--ids-only", is_flag=True, help="Print only chat ids, one per line")
async def folders_chats(folder: str, limit: int, plain: bool, ids_only: bool) -> None:
    """List cached chats belonging to a Telegram folder by id or title."""
    try:
        manager = ChatManager()
        chats_result = await manager.list_chats_by_folder(folder, limit=limit)
        _print_chats(
            chats_result,
            title=f"Folder chats: {folder}",
            plain=plain,
            ids_only=ids_only,
        )
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@chats.command("refresh-archive")
async def chats_refresh_archive() -> None:
    """Refresh archived flag for cached chats."""
    try:
        manager = ChatManager()
        console.print("⏳ Refreshing archived chat flags...", style="yellow")
        chats_result = await manager.refresh_archived_status()
        archived_count = sum(1 for chat in chats_result if chat.is_archived)
        console.print(
            f"✅ Refreshed {len(chats_result)} chats: {archived_count} archived",
            style="green",
        )
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@chats.command("refresh-status")
async def chats_refresh_status() -> None:
    """Refresh deactivated/migrated/inaccessible flags for cached chats."""
    try:
        manager = ChatManager()
        console.print("⏳ Refreshing chat status flags...", style="yellow")
        chats_result = await manager.refresh_chat_statuses()
        inaccessible_count = sum(
            1 for chat in chats_result if _is_chat_inaccessible(chat)
        )
        deactivated_count = sum(1 for chat in chats_result if chat.is_deactivated)
        migrated_count = sum(
            1 for chat in chats_result if chat.migrated_to_chat_id is not None
        )
        console.print(
            f"✅ Refreshed {len(chats_result)} chats: "
            f"{inaccessible_count} inaccessible, "
            f"{deactivated_count} deactivated, {migrated_count} migrated",
            style="green",
        )
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@chats.command("search")
@click.argument("query")
@click.option("--limit", default=20, help="Limit results")
@click.option("--plain", is_flag=True, help="Print TSV rows without Rich table")
@click.option("--ids-only", is_flag=True, help="Print only chat ids, one per line")
async def chats_search(query: str, limit: int, plain: bool, ids_only: bool) -> None:
    """Search chats in local cache."""
    try:
        manager = ChatManager()
        chats_result = await manager.search_chats(query=query, limit=limit)
        _print_chats(
            chats_result, title=f"Chat search: {query}", plain=plain, ids_only=ids_only
        )
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@chats.command("archive", context_settings={"ignore_unknown_options": True})
@click.argument("chat_ids", nargs=-1, required=True, type=str)
@click.option("--yes", is_flag=True, help="Confirm archive operation")
@click.option("--dry-run", is_flag=True, help="Only show what would be archived")
async def chats_archive(chat_ids: tuple[str, ...], yes: bool, dry_run: bool) -> None:
    """Move chats to Telegram archive by chat ids."""
    await _set_chats_archived_command(chat_ids, archived=True, yes=yes, dry_run=dry_run)


@chats.command("unarchive", context_settings={"ignore_unknown_options": True})
@click.argument("chat_ids", nargs=-1, required=True, type=str)
@click.option("--yes", is_flag=True, help="Confirm unarchive operation")
@click.option("--dry-run", is_flag=True, help="Only show what would be unarchived")
async def chats_unarchive(chat_ids: tuple[str, ...], yes: bool, dry_run: bool) -> None:
    """Move chats out of Telegram archive by chat ids."""
    await _set_chats_archived_command(
        chat_ids, archived=False, yes=yes, dry_run=dry_run
    )


@chats.command("delete-and-leave", context_settings={"ignore_unknown_options": True})
@click.argument("chat_ids", nargs=-1, required=True, type=str)
@click.option("--yes", is_flag=True, help="Confirm destructive operation")
@click.option("--dry-run", is_flag=True, help="Only show what would be deleted/left")
@click.option(
    "--delay",
    default=15.0,
    show_default=True,
    type=float,
    help="Delay in seconds between delete/leave actions",
)
@click.option(
    "--wait-flood/--no-wait-flood",
    default=True,
    show_default=True,
    help="Sleep and retry when Telegram returns FLOOD_WAIT",
)
@click.option(
    "--max-flood-wait",
    default=900,
    show_default=True,
    type=int,
    help="Maximum FLOOD_WAIT seconds to auto-sleep before treating it as error",
)
@click.option(
    "--stop-on-flood",
    is_flag=True,
    help="Stop batch on first FLOOD_WAIT instead of continuing",
)
async def chats_delete_and_leave(
    chat_ids: tuple[str, ...],
    yes: bool,
    dry_run: bool,
    delay: float,
    wait_flood: bool,
    max_flood_wait: int,
    stop_on_flood: bool,
) -> None:
    """Delete private chats or leave groups/channels by chat ids."""
    try:
        manager = ChatManager()
        cached_chats = await manager.storage.load_chats()
        cached_by_id = {chat.id: chat for chat in cached_chats}
        resolved = [await manager.resolve_chat(chat_id) for chat_id in chat_ids]
        console.print("Chats selected for delete/leave:", style="yellow")
        for original, item in zip(chat_ids, resolved):
            chat = cached_by_id.get(item) if isinstance(item, int) else None
            if chat:
                console.print(
                    f"  - {chat.id}\t{chat.type}\t"
                    f"members={chat.members_count if chat.members_count is not None else 'unknown'}\t"
                    f"{chat.display_name}\t{_chat_status(chat)}"
                )
            else:
                console.print(f"  - {item} (from {original}; not found in cache)")

        if dry_run:
            console.print("Dry run: nothing was changed", style="green")
            return
        if not yes:
            raise click.ClickException(
                "This is destructive. Re-run with --yes to confirm"
            )

        results = await manager.delete_and_leave_chats(
            list(chat_ids),
            delay_seconds=delay,
            wait_on_flood=wait_flood,
            max_flood_wait_seconds=max_flood_wait,
            stop_on_flood=stop_on_flood,
            progress_callback=lambda message: console.print(message, style="yellow"),
        )
        for result in results:
            if result.success:
                console.print(f"✅ {result.chat_ref}: deleted/left", style="green")
            else:
                console.print(f"❌ {result.chat_ref}: {result.error}", style="red")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@chats.command("info")
@click.argument("chat")
@click.option("--plain", is_flag=True, help="Print TSV rows without Rich table")
@click.option("--ids-only", is_flag=True, help="Print only chat ids, one per line")
async def chats_info(chat: str, plain: bool, ids_only: bool) -> None:
    """Show one chat info by id, @username, username or title substring."""
    try:
        manager = ChatManager()
        found = await manager.search_chats(chat, limit=1)
        if found:
            _print_chats(found, title="Chat info", plain=plain, ids_only=ids_only)
            return
        async with TelegramClient() as client:
            info = await client.get_chat_info(chat)
        _print_chats([info], title="Chat info", plain=plain, ids_only=ids_only)
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


# Backward-compatible old command.
@cli.command("list-chats")
@click.option("--limit", default=20, help="Limit number of chats to show; 0 means all")
@click.option("--api", "from_api", is_flag=True, help="Force loading from Telegram API")
@click.option("--private-only", is_flag=True, help="Show only 1-on-1 private chats")
@click.option(
    "--non-private", is_flag=True, help="Show all chats except 1-on-1 private chats"
)
@click.option(
    "--zero-members",
    is_flag=True,
    help="Show only chats with members_count=0, usually inaccessible/dead chats",
)
@click.option("--deactivated", is_flag=True, help="Show only deactivated chats")
@click.option(
    "--migrated", is_flag=True, help="Show only chats migrated to another chat"
)
@click.option("--inaccessible", is_flag=True, help="Show only inaccessible/dead chats")
@click.option("--archived", is_flag=True, help="Show only archived chats")
@click.option("--exclude-archived", is_flag=True, help="Hide archived chats")
@click.option("--plain", is_flag=True, help="Print TSV rows without Rich table")
@click.option("--ids-only", is_flag=True, help="Print only chat ids, one per line")
async def list_chats(
    limit: int,
    from_api: bool,
    private_only: bool,
    non_private: bool,
    zero_members: bool,
    deactivated: bool,
    migrated: bool,
    inaccessible: bool,
    archived: bool,
    exclude_archived: bool,
    plain: bool,
    ids_only: bool,
) -> None:
    """List user's chats. Alias for `chats list`."""
    try:
        if private_only and non_private:
            raise click.ClickException(
                "Use either --private-only or --non-private, not both"
            )
        if archived and exclude_archived:
            raise click.ClickException(
                "Use either --archived or --exclude-archived, not both"
            )

        manager = ChatManager()
        source_chats = await manager.list_chats(
            limit=0, cached=not from_api, force_refresh=from_api
        )
        filtered_chats = _filter_chats(
            source_chats,
            private_only,
            non_private,
            zero_members,
            deactivated,
            migrated,
            inaccessible,
            archived,
            exclude_archived,
        )
        chats_result = filtered_chats if limit <= 0 else filtered_chats[:limit]
        _print_chats(
            chats_result,
            title=(
                f"Chats: showing {len(chats_result)} of {len(filtered_chats)} "
                f"filtered / {len(source_chats)} total"
            ),
            plain=plain,
            ids_only=ids_only,
        )
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@cli.group()
def messages() -> None:
    """Message download and search commands."""


@messages.command("download")
@click.argument("chat")
@click.option("--limit", default=100, help="How many messages to download; 0 means all")
@click.option(
    "--from", "from_date", default=None, help="Start date: YYYY-MM-DD or ISO datetime"
)
@click.option(
    "--to", "to_date", default=None, help="End date: YYYY-MM-DD or ISO datetime"
)
@click.option("--media", is_flag=True, help="Download media files too")
@click.option(
    "--media-dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory for media files; default is downloads/<chat_id>/",
)
async def messages_download(
    chat: str,
    limit: int,
    from_date: Optional[str],
    to_date: Optional[str],
    media: bool,
    media_dir: Optional[Path],
) -> None:
    """Download selected chat messages into local cache."""
    try:
        manager = MessageManager()
        console.print("⏳ Downloading messages...", style="yellow")
        messages_result = await manager.download_chat(
            chat_ref=chat,
            limit=limit,
            from_date=parse_cli_date(from_date),
            to_date=parse_cli_date(to_date, end_of_day=True),
            include_media=media,
            media_dir=media_dir,
        )
        console.print(
            f"✅ Downloaded/cached {len(messages_result)} messages", style="green"
        )
        _print_messages(messages_result[:20], title="Downloaded messages preview")
        if len(messages_result) > 20:
            console.print(f"... and {len(messages_result) - 20} more", style="dim")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@messages.command("sync")
@click.argument("chat")
@click.option(
    "--media/--no-media",
    default=True,
    show_default=True,
    help="Download media files for new messages",
)
@click.option(
    "--media-dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory for media files; default is downloads/<chat_id>/",
)
@click.option(
    "--limit",
    default=0,
    help="Safety cap on fetched messages; 0 means no cap",
)
async def messages_sync(
    chat: str, media: bool, media_dir: Optional[Path], limit: int
) -> None:
    """Fetch only new messages since the last sync and merge into local cache.

    First run downloads the whole chat history; subsequent runs download only
    the delta above the newest cached message.
    """
    try:
        manager = MessageManager()
        console.print("⏳ Syncing new messages...", style="yellow")
        new_messages = await manager.sync_chat(
            chat_ref=chat,
            include_media=media,
            media_dir=media_dir,
            limit=limit,
        )
        console.print(f"✅ Synced {len(new_messages)} new messages", style="green")
        _print_messages_text(sorted(new_messages, key=lambda m: (m.date, m.id)))
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@messages.command("search")
@click.argument("query")
@click.option("--chat", default=None, help="Search inside one chat only")
@click.option("--limit", default=50, help="Limit results")
@click.option(
    "--api",
    "from_api",
    is_flag=True,
    help="Search via Telegram API instead of local cache",
)
async def messages_search(
    query: str, chat: Optional[str], limit: int, from_api: bool
) -> None:
    """Search messages globally or inside one chat."""
    try:
        manager = MessageManager()
        if from_api:
            messages_result = await manager.search_telegram_messages(
                query=query, chat_ref=chat, limit=limit
            )
        else:
            messages_result = await manager.search_cached_messages(
                query=query, chat_ref=chat, limit=limit
            )
        _print_messages(messages_result, title=f"Message search: {query}")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


@messages.command("list")
@click.argument("chat")
@click.option("--limit", default=50, help="Limit cached messages to show")
@click.option(
    "--text",
    "as_text",
    is_flag=True,
    help="Print plain text with local media file paths instead of a table",
)
async def messages_list(chat: str, limit: int, as_text: bool) -> None:
    """List cached messages for one chat."""
    try:
        storage = CacheStorage()
        chat_ref = await ChatManager(storage=storage).resolve_chat(chat)
        if not isinstance(chat_ref, int):
            console.print(
                "❌ Chat not found in cache; run `chats sync` first", style="red"
            )
            return
        messages_result = await storage.load_messages(chat_ref)
        shown = messages_result[-limit:] if limit > 0 else messages_result
        if as_text:
            _print_messages_text(shown)
            return
        _print_messages(shown, title=f"Cached messages: {chat}")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


async def _set_chats_archived_command(
    chat_ids: tuple[str, ...], archived: bool, yes: bool, dry_run: bool
) -> None:
    """Shared CLI implementation for archive/unarchive commands."""
    action = "archive" if archived else "unarchive"
    try:
        manager = ChatManager()
        cached_chats = await manager.storage.load_chats()
        cached_by_id = {chat.id: chat for chat in cached_chats}
        resolved = [await manager.resolve_chat(chat_id) for chat_id in chat_ids]
        console.print(f"Chats selected to {action}:", style="yellow")
        for original, item in zip(chat_ids, resolved):
            chat = cached_by_id.get(item) if isinstance(item, int) else None
            if chat:
                console.print(
                    f"  - {chat.id}\t{chat.type}\t"
                    f"archived={str(chat.is_archived).lower()}\t"
                    f"{chat.display_name}\t{_chat_status(chat)}"
                )
            else:
                console.print(f"  - {item} (from {original}; not found in cache)")

        if dry_run:
            console.print("Dry run: nothing was changed", style="green")
            return
        if not yes:
            raise click.ClickException(
                f"This changes Telegram folders. Re-run with --yes to {action}"
            )

        results = await manager.set_chats_archived(list(chat_ids), archived=archived)
        for result in results:
            if result.success:
                console.print(f"✅ {result.chat_ref}: {action}d", style="green")
            else:
                console.print(f"❌ {result.chat_ref}: {result.error}", style="red")
    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


def _filter_chats(
    chats_result: Iterable[ChatInfo],
    private_only: bool,
    non_private: bool,
    zero_members: bool,
    deactivated: bool,
    migrated: bool,
    inaccessible: bool,
    archived: bool,
    exclude_archived: bool,
) -> list[ChatInfo]:
    """Filter chats by CLI flags."""
    chats_list_result = list(chats_result)
    if private_only:
        chats_list_result = [
            chat for chat in chats_list_result if chat.type == "private"
        ]
    if non_private:
        chats_list_result = [
            chat for chat in chats_list_result if chat.type != "private"
        ]
    if zero_members:
        chats_list_result = [
            chat for chat in chats_list_result if chat.members_count == 0
        ]
    if deactivated:
        chats_list_result = [chat for chat in chats_list_result if chat.is_deactivated]
    if migrated:
        chats_list_result = [
            chat for chat in chats_list_result if chat.migrated_to_chat_id is not None
        ]
    if inaccessible:
        chats_list_result = [
            chat for chat in chats_list_result if _is_chat_inaccessible(chat)
        ]
    if archived:
        chats_list_result = [chat for chat in chats_list_result if chat.is_archived]
    if exclude_archived:
        chats_list_result = [chat for chat in chats_list_result if not chat.is_archived]
    return chats_list_result


def _is_chat_inaccessible(chat: ChatInfo) -> bool:
    """Return whether chat looks inaccessible/dead for this account."""
    return (
        chat.is_inaccessible
        or chat.is_deactivated
        or chat.migrated_to_chat_id is not None
        or (chat.type != "private" and chat.members_count == 0)
    )


def _chat_status(chat: ChatInfo) -> str:
    """Build compact chat status string."""
    statuses = []
    if chat.is_archived:
        statuses.append("archived")
    if chat.is_deactivated:
        statuses.append("deactivated")
    if chat.migrated_to_chat_id is not None:
        statuses.append(f"migrated→{chat.migrated_to_chat_id}")
    if _is_chat_inaccessible(chat):
        statuses.append("inaccessible")
    return ", ".join(statuses) if statuses else "—"


def _print_chats(
    chats_result: Iterable[ChatInfo],
    title: str,
    plain: bool = False,
    ids_only: bool = False,
) -> None:
    chats_list_result = list(chats_result)
    if ids_only:
        for chat in chats_list_result:
            click.echo(str(chat.id))
        return
    if plain:
        for chat in chats_list_result:
            click.echo(_chat_tsv_row(chat))
        return

    if not chats_list_result:
        console.print("No chats found", style="yellow")
        return

    table = Table(title=title)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Type", style="magenta")
    table.add_column("Username", style="blue")
    table.add_column("Members", style="yellow")
    table.add_column("Folders", style="cyan")
    table.add_column("Status", style="red")

    for chat in chats_list_result:
        table.add_row(
            str(chat.id),
            chat.display_name,
            chat.type,
            f"@{chat.username}" if chat.username else "—",
            str(chat.members_count) if chat.members_count is not None else "—",
            ", ".join(chat.folder_names) if chat.folder_names else "—",
            _chat_status(chat),
        )
    console.print(table)


def _print_folders(
    folders_result: Iterable[FolderInfo], plain: bool = False, ids_only: bool = False
) -> None:
    """Print folders as Rich table, TSV, or ids-only."""
    folders_list_result = list(folders_result)
    if ids_only:
        for folder in folders_list_result:
            click.echo(str(folder.id))
        return
    if plain:
        for folder in folders_list_result:
            click.echo(_folder_tsv_row(folder))
        return
    if not folders_list_result:
        console.print("No folders found", style="yellow")
        return

    table = Table(title=f"Folders ({len(folders_list_result)})")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Explicit chats", style="yellow")
    table.add_column("Rules", style="magenta")

    for folder in folders_list_result:
        table.add_row(
            str(folder.id),
            folder.title,
            str(folder.explicit_count),
            _folder_rules(folder),
        )
    console.print(table)


def _folder_rules(folder: FolderInfo) -> str:
    """Build compact folder rule description."""
    rules = []
    if folder.include_contacts:
        rules.append("contacts")
    if folder.include_non_contacts:
        rules.append("non_contacts")
    if folder.include_groups:
        rules.append("groups")
    if folder.include_channels:
        rules.append("channels")
    if folder.include_bots:
        rules.append("bots")
    if folder.exclude_muted:
        rules.append("exclude_muted")
    if folder.exclude_read:
        rules.append("exclude_read")
    if folder.exclude_archived:
        rules.append("exclude_archived")
    return ", ".join(rules) if rules else "—"


def _folder_tsv_row(folder: FolderInfo) -> str:
    """Serialize folder as headerless TSV row for scripts."""
    fields = [
        str(folder.id),
        folder.title,
        str(folder.explicit_count),
        _folder_rules(folder),
    ]
    return "\t".join(field.replace("\t", " ").replace("\n", " ") for field in fields)


def _chat_tsv_row(chat: ChatInfo) -> str:
    """Serialize chat as headerless TSV row for scripts."""
    fields = [
        str(chat.id),
        chat.type,
        "" if chat.members_count is None else str(chat.members_count),
        chat.username or "",
        ",".join(chat.folder_names),
        str(chat.is_archived).lower(),
        str(chat.is_deactivated).lower(),
        "" if chat.migrated_to_chat_id is None else str(chat.migrated_to_chat_id),
        str(_is_chat_inaccessible(chat)).lower(),
        chat.display_name,
    ]
    return "\t".join(field.replace("\t", " ").replace("\n", " ") for field in fields)


def _print_messages(messages_result: Iterable[MessageInfo], title: str) -> None:
    messages_list_result = list(messages_result)
    if not messages_list_result:
        console.print("No messages found", style="yellow")
        return

    table = Table(title=title)
    table.add_column("Chat", style="cyan")
    table.add_column("ID", style="cyan")
    table.add_column("Date", style="green")
    table.add_column("Media", style="magenta")
    table.add_column("Text", style="white")

    for message in messages_list_result:
        text = (message.text or "").replace("\n", " ")
        if len(text) > 120:
            text = text[:117] + "..."
        table.add_row(
            str(message.chat_id),
            str(message.id),
            message.date.isoformat(sep=" ", timespec="seconds"),
            message.media_type or "—",
            text,
        )
    console.print(table)


def _print_messages_text(messages_result: Iterable[MessageInfo]) -> None:
    """Print messages as plain text with local media file paths."""
    printed = False
    for message in messages_result:
        printed = True
        header = (
            f"[{message.date.isoformat(sep=' ', timespec='seconds')}] #{message.id}"
        )
        if message.from_user_id is not None:
            header += f" from={message.from_user_id}"
        if message.reply_to_message_id is not None:
            header += f" reply_to={message.reply_to_message_id}"
        click.echo(header)
        if message.text:
            click.echo(message.text)
        if message.downloaded_media_path:
            click.echo(f"media: {message.downloaded_media_path}")
        elif message.media_type:
            click.echo(f"media: <{message.media_type}: not downloaded>")
        click.echo("")
    if not printed:
        console.print("No messages found", style="yellow")


def main() -> None:
    """Entry point with asyncio support."""
    import inspect

    def wrap_command(command: click.Command) -> None:
        if isinstance(command, click.Group):
            for subcommand in command.commands.values():
                wrap_command(subcommand)

        if command.callback and inspect.iscoroutinefunction(command.callback):
            original_callback = command.callback

            def make_wrapper(callback: Callable[..., Any]) -> Callable[..., Any]:
                def wrapper(*args: Any, **kwargs: Any) -> Any:
                    return asyncio.run(callback(*args, **kwargs))

                return wrapper

            command.callback = make_wrapper(original_callback)

    wrap_command(cli)
    cli()


if __name__ == "__main__":
    main()
