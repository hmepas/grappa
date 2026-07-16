"""Markdown to Telegram markup conversion for outgoing messages."""

import html

# ">" after html.escape()
_QUOTE_PREFIX = "&gt;"
_CODE_FENCE = "```"


def md_to_telegram(text: str) -> str:
    """Convert user Markdown into markup understood by Pyrogram.

    Pyrogram's combined parser handles Telegram-flavoured Markdown
    (**bold**, __italic__, --underline--, ~~strike~~, ||spoiler||, `code`,
    ```pre```, [text](url)) but has no blockquote syntax, and its HTML stage
    silently swallows anything that looks like an unknown tag (e.g. List<int>).

    This function escapes literal HTML characters so user text survives as-is,
    and turns groups of ">"-prefixed lines into <blockquote> tags. Lines inside
    ``` code fences are left untouched.
    """
    escaped = html.escape(text, quote=False)
    result: list[str] = []
    quote: list[str] = []
    in_code_fence = False

    def flush_quote() -> None:
        if quote:
            result.append("<blockquote>" + "\n".join(quote) + "</blockquote>")
            quote.clear()

    for line in escaped.split("\n"):
        if line.lstrip().startswith(_CODE_FENCE):
            flush_quote()
            in_code_fence = not in_code_fence
            result.append(line)
            continue
        if not in_code_fence and line.startswith(_QUOTE_PREFIX):
            stripped = line[len(_QUOTE_PREFIX) :]
            quote.append(stripped[1:] if stripped.startswith(" ") else stripped)
            continue
        flush_quote()
        result.append(line)
    flush_quote()
    return "\n".join(result)
