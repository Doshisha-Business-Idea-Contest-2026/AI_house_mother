"""Shared Flex design tokens and helpers (T4.13).

This module is the single source of truth for the Flex look-and-feel used
by every builder in :mod:`src.templates.flex`. The design language is a
white, airy style: a **white header** with the title in navy, a thin navy
accent bar to its left, and a navy hairline beneath it; the body groups
information with whitespace and hairline dividers rather than filled cards.
Brand and category colours live in the header accent bar (adapted from the
left accent bar of ``kcb_linebot/flex_templates.py`` ``create_stop_info_box``).

See ``docs/07_architecture.md §4.6`` and ``docs/04_functional_spec.md §8``.

Builders must not hard-code colours, separators, or bubble skeletons of
their own; they compose the helpers below so the five Flex messages stay
visually consistent.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Colour tokens
# ---------------------------------------------------------------------------

#: Doshisha navy — the brand colour used for titles, accent bars and the
#: hairline beneath the header.
NAVY = "#00579C"
WHITE = "#ffffff"

#: Hairline separator colour reused across every builder.
SEPARATOR = "#e0e0e0"

#: Text tone hierarchy (primary → faint). ``TEXT_FAINT`` is reserved for the
#: freshness caveat so it never competes with the content.
TEXT_MAIN = "#333333"
TEXT_SUB = "#666666"
TEXT_WEAK = "#999999"
TEXT_FAINT = "#aaaaaa"

# ---------------------------------------------------------------------------
# Layout tokens
# ---------------------------------------------------------------------------

ACCENT_WIDTH = "4px"
RADIUS_BAR = "2px"
PAD_HEADER = "16px"
BODY_SPACING = "lg"

# ---------------------------------------------------------------------------
# Category colours (navy-harmonised, T4.13)
# ---------------------------------------------------------------------------

#: Accent-bar colour per ``reference_type`` for activity proposals. Muted,
#: navy-leaning tones for a cohesive look. ``generated`` stays navy,
#: ``senior_post`` stays slate, and ``sponsored`` keeps its gold so the PR
#: slot remains visually distinct per FR-S9.
CATEGORY_COLORS: dict[str, str] = {
    "event": "#3A6EA5",  # muted steel blue
    "volunteer": "#4E8C6A",  # calm green
    "workshop": "#6E5B99",  # muted violet
    "festival": "#B85C7A",  # dusty rose
    "study_group": "#455A9C",  # muted indigo
    "store": "#B7823C",  # amber
    "senior_post": "#607D8B",  # slate (unchanged)
    "generated": NAVY,  # navy (unchanged)
    "static_fallback": "#7A6A5D",  # muted brown
    "sponsored": "#C9A227",  # gold — corporate PR slot (FR-S9, unchanged)
}


def get_category_color(reference_type: str) -> str:
    """Return the accent colour for ``reference_type``.

    Args:
        reference_type: The proposal's reference type (e.g. ``event``,
            ``generated``, ``sponsored``).

    Returns:
        The mapped colour, or :data:`NAVY` when unknown.
    """
    return CATEGORY_COLORS.get(reference_type, NAVY)


# ---------------------------------------------------------------------------
# Structural helpers
# ---------------------------------------------------------------------------


def hairline() -> dict[str, Any]:
    """Return a thin grey separator using the shared :data:`SEPARATOR` colour."""
    return {"type": "separator", "color": SEPARATOR}


def accent_bar(color: str, *, width: str = ACCENT_WIDTH) -> dict[str, Any]:
    """Return a thin vertical accent bar box.

    An empty box that stretches to its row height when placed in a
    horizontal layout, mimicking ``kcb_linebot``'s ``create_stop_info_box``.

    Args:
        color: The bar fill colour.
        width: The bar width. Defaults to :data:`ACCENT_WIDTH`.
    """
    return {
        "type": "box",
        "layout": "vertical",
        "width": width,
        "backgroundColor": color,
        "cornerRadius": RADIUS_BAR,
        "contents": [],
    }


def heading_row(
    title: str,
    *,
    accent: str = NAVY,
    size: str = "xl",
    color: str = NAVY,
    weight: str = "bold",
) -> dict[str, Any]:
    """Return a heading row: a left accent bar followed by the title text.

    Shared by the bubble header (large) and body section headings (medium).

    Args:
        title: The heading text.
        accent: Colour of the left accent bar. Defaults to :data:`NAVY`.
        size: Font size of the title.
        color: Title text colour. Defaults to :data:`NAVY`.
        weight: Title font weight.
    """
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
            accent_bar(accent),
            {
                "type": "text",
                "text": title,
                "size": size,
                "color": color,
                "weight": weight,
                "wrap": True,
                "gravity": "center",
            },
        ],
    }


def section_heading(
    text: str, *, accent: str = NAVY, size: str = "md"
) -> dict[str, Any]:
    """Return a body section heading (a lighter :func:`heading_row`)."""
    return heading_row(text, accent=accent, size=size)


def white_header(
    title: str,
    *,
    subtitle: str | list[str] | None = None,
    accent: str = NAVY,
) -> dict[str, Any]:
    """Return the white bubble header with a navy accent and hairline.

    The header carries no filled background: the title sits in navy with a
    thin accent bar to its left (brand/category colour), optional muted
    subtitle line(s) above it, and a navy hairline beneath to divide it from
    the body.

    Args:
        title: The main header title (rendered navy, bold, ``xl``).
        subtitle: Optional small muted line(s) shown above the title (e.g. a
            category label or a PR badge plus company name). A single string
            or a list of strings, each rendered as its own line.
        accent: Colour of the left accent bar. Defaults to :data:`NAVY`;
            proposals pass the category colour and sponsored PR passes gold.
    """
    contents: list[dict[str, Any]] = []
    subtitles = [subtitle] if isinstance(subtitle, str) else (subtitle or [])
    for line in subtitles:
        contents.append(
            {"type": "text", "text": line, "size": "sm", "color": TEXT_WEAK}
        )
    contents.append(heading_row(title, accent=accent))
    contents.append({"type": "separator", "color": NAVY})
    return {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "backgroundColor": WHITE,
        "paddingAll": PAD_HEADER,
        "contents": contents,
    }


def label_value(label: str, value: str) -> dict[str, Any]:
    """Return a stacked label/value pair (weak label above a bold value).

    Args:
        label: The field label (rendered small and muted).
        value: The field value (rendered medium and bold, wrapped).
    """
    return {
        "type": "box",
        "layout": "vertical",
        "spacing": "xs",
        "contents": [
            {"type": "text", "text": label, "size": "xs", "color": TEXT_WEAK},
            {
                "type": "text",
                "text": value,
                "size": "md",
                "weight": "bold",
                "wrap": True,
                "color": TEXT_MAIN,
            },
        ],
    }


def bubble(
    *,
    header: dict[str, Any],
    body: list[dict[str, Any]],
    footer: list[dict[str, Any]] | None = None,
    body_spacing: str = BODY_SPACING,
) -> dict[str, Any]:
    """Return a ``mega`` bubble skeleton with a white body ground.

    Args:
        header: The header box (typically from :func:`white_header`).
        body: The body child components (section headings, text, hairlines).
        footer: Optional footer child components (e.g. postback buttons).
        body_spacing: Vertical spacing between body children.

    Returns:
        A Flex bubble ``dict`` ready to be sent as the message ``contents``.
    """
    result: dict[str, Any] = {
        "type": "bubble",
        "size": "mega",
        "header": header,
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": body_spacing,
            "backgroundColor": WHITE,
            "contents": body,
        },
        "styles": {"body": {"backgroundColor": WHITE}},
    }
    if footer is not None:
        result["footer"] = {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": footer,
        }
    return result
