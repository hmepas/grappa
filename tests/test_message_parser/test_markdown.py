"""Tests for Markdown to Telegram markup conversion."""

import pytest

from grappa.message_parser import md_to_telegram


class TestMdToTelegram:
    """Tests for the md_to_telegram converter."""

    def test_quote_lines_become_blockquote(self) -> None:
        """A ">"-prefixed line turns into a blockquote tag."""
        assert md_to_telegram("> цитата") == "<blockquote>цитата</blockquote>"

    def test_consecutive_quote_lines_merge(self) -> None:
        """Adjacent quote lines produce one blockquote."""
        result = md_to_telegram("> раз\n> два\nобычный текст")
        assert result == "<blockquote>раз\nдва</blockquote>\nобычный текст"

    def test_quote_without_space_prefix(self) -> None:
        """Both "> text" and ">text" are treated as quotes."""
        assert md_to_telegram(">без пробела") == (
            "<blockquote>без пробела</blockquote>"
        )

    def test_literal_html_is_escaped(self) -> None:
        """Literal angle brackets survive instead of being eaten as tags."""
        assert md_to_telegram("`List<int>` и a & b") == (
            "`List&lt;int&gt;` и a &amp; b"
        )

    def test_code_fence_protects_quote_lines(self) -> None:
        """Lines starting with ">" inside a code fence stay untouched."""
        text = "```\n> not a quote\n```"
        assert md_to_telegram(text) == "```\n&gt; not a quote\n```"

    def test_markdown_delimiters_pass_through(self) -> None:
        """Telegram Markdown styling is left for Pyrogram to parse."""
        text = "**b** __i__ --u-- ~~s~~ ||sp|| [t](https://e.com/)"
        assert md_to_telegram(text) == text

    @pytest.mark.asyncio
    async def test_converted_text_parses_to_all_entities(self) -> None:
        """End-to-end: Pyrogram parses converted text into expected entities."""
        from pyrogram.parser.markdown import Markdown

        source = (
            "**жирный** __курсив__ --подчёркнутый-- ~~зачёркнутый~~ ||спойлер||\n"
            "`List<int>` и [ссылка](https://example.com/)\n"
            "> цитата\n"
            "```python\nif a < b: pass\n```"
        )
        parsed = await Markdown(None).parse(md_to_telegram(source))

        entity_types = {type(entity).__name__ for entity in parsed["entities"]}
        assert entity_types == {
            "MessageEntityBold",
            "MessageEntityItalic",
            "MessageEntityUnderline",
            "MessageEntityStrike",
            "MessageEntitySpoiler",
            "MessageEntityCode",
            "MessageEntityTextUrl",
            "MessageEntityBlockquote",
            "MessageEntityPre",
        }
        assert "List<int>" in parsed["message"]
        assert "цитата" in parsed["message"]
