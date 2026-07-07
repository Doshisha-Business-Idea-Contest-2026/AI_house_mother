"""Plain-text formatting helpers for LINE replies.

LINE does not render Markdown, so any ``**bold**`` / ``# heading`` / ``- item``
markers produced by Gemini would leak into the chat as raw symbols. These
helpers strip that residue, normalise blank lines, and join reply blocks
(disclaimer / body / followup) with exactly one blank line between them so a
life-consultation answer stays readable in a single text bubble.

See ``docs/06_ai_spec.md §4.2`` and ``docs/04_functional_spec.md §4.4``.
"""
from __future__ import annotations

import re

# Inline emphasis / code markers to unwrap (keep the inner text).
_BOLD_ASTERISK = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BOLD_UNDERSCORE = re.compile(r"__(.+?)__", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]+)`")

# Leftover stray markers after the paired ones are unwrapped.
_STRAY_MARKERS = re.compile(r"\*\*|__|`")

# Line-leading Markdown constructs.
_HEADING_PREFIX = re.compile(r"^\s*#{1,6}\s*")
_BULLET_PREFIX = re.compile(r"^\s*[-*+•]\s+")

# Three or more consecutive newlines collapse to a single blank line.
_EXCESS_NEWLINES = re.compile(r"\n{3,}")


def normalize_markdown(text: str) -> str:
    """Strip Markdown residue that LINE would show as raw symbols.

    Inline ``**bold**`` / ``__bold__`` / ```` `code` ```` markers are
    unwrapped to their inner text, line-leading heading markers (``#``) are
    dropped, and line-leading bullet markers (``-``/``*``/``+``/``•``) are
    converted to the full-width bullet ``・`` used across the bot.

    Args:
        text: Raw model output that may contain Markdown.

    Returns:
        The text with Markdown markers removed or converted. Blank-line
        normalisation is left to :func:`collapse_blank_lines`.
    """
    if not text:
        return ""

    unwrapped = _BOLD_ASTERISK.sub(r"\1", text)
    unwrapped = _BOLD_UNDERSCORE.sub(r"\1", unwrapped)
    unwrapped = _INLINE_CODE.sub(r"\1", unwrapped)
    unwrapped = _STRAY_MARKERS.sub("", unwrapped)

    lines: list[str] = []
    for line in unwrapped.split("\n"):
        line = _HEADING_PREFIX.sub("", line)
        line = _BULLET_PREFIX.sub("・", line)
        lines.append(line)
    return "\n".join(lines)


def collapse_blank_lines(text: str) -> str:
    """Trim trailing spaces and collapse runs of blank lines.

    Each line is right-stripped, three or more consecutive newlines are
    reduced to two (one blank line), and surrounding whitespace is removed.

    Args:
        text: Text to normalise.

    Returns:
        The normalised text with at most one blank line between blocks.
    """
    if not text:
        return ""
    stripped_lines = "\n".join(line.rstrip() for line in text.split("\n"))
    return _EXCESS_NEWLINES.sub("\n\n", stripped_lines).strip()


def join_blocks(blocks: list[str]) -> str:
    """Join reply blocks with exactly one blank line between them.

    Empty or whitespace-only blocks are dropped, so a body-only reply or a
    disclaimer + body + followup reply both come out cleanly separated
    regardless of the constants' own leading / trailing newlines.

    Args:
        blocks: Reply segments in display order (e.g. disclaimer, body,
            followup).

    Returns:
        The blocks joined by a single blank line, blank-line normalised.
    """
    non_empty = [block.strip() for block in blocks if block and block.strip()]
    return collapse_blank_lines("\n\n".join(non_empty))
