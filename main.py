"""Main CLI application."""

import asyncio

import click
from rich.console import Console
from rich.table import Table

from client import TelegramClient

console = Console()


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug mode")
def cli(debug: bool) -> None:
    """Grappa - AI-augmented Telegram client."""
    if debug:
        console.print("🐛 Debug mode enabled", style="yellow")


@cli.command()
@click.option("--limit", default=20, help="Limit number of chats to show")
async def list_chats(limit: int) -> None:
    """List user's chats and dialogs."""
    try:
        async with TelegramClient() as client:
            chats = await client.get_dialogs(limit=limit)

            if not chats:
                console.print("No chats found", style="yellow")
                return

            table = Table(title=f"Your Chats (showing {len(chats)} of {limit})")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Type", style="magenta")
            table.add_column("Username", style="blue")

            for chat in chats:
                table.add_row(
                    str(chat.id),
                    chat.display_name,
                    chat.type,
                    f"@{chat.username}" if chat.username else "—",
                )

            console.print(table)

    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


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


def main() -> None:
    """Entry point with asyncio support."""
    # Convert sync click commands to async
    import inspect
    from typing import Any, Callable

    for command in cli.commands.values():
        if inspect.iscoroutinefunction(command.callback):
            original_callback = command.callback

            def make_wrapper(callback: Callable[..., Any]) -> Callable[..., Any]:
                def wrapper(*args: Any, **kwargs: Any) -> Any:
                    return asyncio.run(callback(*args, **kwargs))

                return wrapper

            command.callback = make_wrapper(original_callback)

    cli()


if __name__ == "__main__":
    main()
