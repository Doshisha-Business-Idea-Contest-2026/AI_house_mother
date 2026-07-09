"""Shared Flex design tokens and helpers (T4.13).

This module is the single source of truth for the Flex look-and-feel used
by every builder in :mod:`src.templates.flex`. It centralises the colour
palette (Doshisha navy ``#00579C`` base, plus the per-category header
colours), corner radii, paddings, and a small set of helpers that assemble
the "card-in-card" structure — a coloured header, section headings with a
left accent bar, and rounded tone-tinted cards that group body content.

The design language is adapted from ``kcb_linebot/flex_templates.py``
(``create_stop_info_box`` for the left accent bar and
``create_single_route_bubble`` for the section background control). See
``docs/07_architecture.md §4.6`` and ``docs/04_functional_spec.md §8``.

Builders must not hard-code colours, separators, or bubble skeletons of
their own; they compose the helpers below so the five Flex messages stay
visually consistent.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Colour tokens
# ---------------------------------------------------------------------------

#: Doshisha navy — the base brand colour and default header/accent colour.
NAVY = "#00579C"
WHITE = "#ffffff"

#: Card-in-card fills: a light card ground and a slightly cooler tone used
#: to emphasise a single value block (e.g. the invitation code).
CARD_BG = "#f5f5f5"
TONE_BG = "#eef2f7"

#: Hairline separator colour reused across every builder.
SEPARATOR = "#e0e0e0"

#: Text tone hierarchy (primary → faint). ``TEXT_FAINT`` is reserved for the
#: freshness caveat so it never competes with the content.
TEXT_MAIN = "#333333"
TEXT_SUB = "#666666"
TEXT_WEAK = "#999999"
TEXT_FAINT = "#aaaaaa"

# ---------------------------------------------------------------------------
# Radius / padding tokens
# ---------------------------------------------------------------------------

RADIUS_CARD = "8px"
RADIUS_BAR = "2px"
RADIUS_TONE = "4px"

PAD_HEADER = "16px"
PAD_CARD = "12px"

# ---------------------------------------------------------------------------
# Category colours (navy-harmonised, T4.13)
# ---------------------------------------------------------------------------

#: Header colour per ``reference_type`` for activity proposals. Re-tuned to a
#: muted, navy-leaning palette for a cohesive look (T4.13). ``generated``
#: stays navy, ``senior_post`` stays slate, and ``sponsored`` keeps its gold
#: so the PR slot remains visually distinct per FR-S9.
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
    """Return the header colour for ``reference_type``.

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


def separator() -> dict[str, Any]:
    """Return a hairline separator using the shared :data:`SEPARATOR` colour."""
    return {"type": "separator", "color": SEPARATOR}


def accent_bar(color: str) -> dict[str, Any]:
    """Return a thin vertical accent bar box.

    An empty ``5px``-wide box that stretches to its row height when placed in
    a horizontal layout, mimicking ``kcb_linebot``'s ``create_stop_info_box``.

    Args:
        color: The bar fill colour.
    """
    return {
        "type": "box",
        "layout": "vertical",
        "width": "5px",
        "backgroundColor": color,
        "cornerRadius": RADIUS_BAR,
        "contents": [],
    }


def header_box(color: str, contents: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the coloured bubble header box.

    The ``backgroundColor`` is kept at the top level of the returned box so
    callers (and tests) can read it directly.

    Args:
        color: Header background colour.
        contents: Header child components (already styled for the coloured
            background, e.g. white text).
    """
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": color,
        "paddingAll": PAD_HEADER,
        "contents": contents,
    }


def section_heading(
    text: str, *, bar_color: str = NAVY, size: str = "md"
) -> dict[str, Any]:
    """Return a section heading row with a left accent bar.

    Args:
        text: The heading label.
        bar_color: Colour of the left accent bar. Defaults to :data:`NAVY`.
        size: Font size of the heading text.
    """
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
            accent_bar(bar_color),
            {
                "type": "text",
                "text": text,
                "weight": "bold",
                "size": size,
                "color": TEXT_MAIN,
                "wrap": True,
                "gravity": "center",
            },
        ],
    }


def card(
    contents: list[dict[str, Any]],
    *,
    bg: str = CARD_BG,
    spacing: str = "sm",
) -> dict[str, Any]:
    """Return a rounded, tone-tinted card grouping body content.

    Args:
        contents: The child components rendered inside the card.
        bg: Card background colour. Defaults to :data:`CARD_BG`.
        spacing: Vertical spacing between children.
    """
    return {
        "type": "box",
        "layout": "vertical",
        "spacing": spacing,
        "backgroundColor": bg,
        "cornerRadius": RADIUS_CARD,
        "paddingAll": PAD_CARD,
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
    body_spacing: str = "md",
) -> dict[str, Any]:
    """Return a ``mega`` bubble skeleton with a white body ground.

    Args:
        header: The header box (typically from :func:`header_box`).
        body: The body child components (section headings and cards).
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
