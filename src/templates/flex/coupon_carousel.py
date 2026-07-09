"""Flex Message carousel builder for coupon distribution (FR-S10).

Awarded when a student's experience-post count hits a new milestone
(docs/04 §4.8). Each bubble follows the shared white/airy design language
in :mod:`src.templates.flex.style`: a store-coloured header, the discount
and validity in the body, and a single URI button to the (fictional) store
page. Coupons are demo-only — there is no redemption or consumption — so
no click-tracking postback is attached. Text is rendered verbatim from the
seed (docs/05 §4.15).
"""

from __future__ import annotations

from typing import Any

from src.templates.flex import style

MAX_BUBBLES = 3

#: Store amber accent shared with the ``store`` category (docs/04 §4.8).
_COUPON_COLOR = style.CATEGORY_COLORS["store"]
_COUPON_BADGE_TEXT = "🎫 クーポン"


def build_coupon_carousel(coupons: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a Flex carousel JSON containing up to three coupon bubbles.

    Args:
        coupons: The coupon dicts to render. Extra items beyond
            :data:`MAX_BUBBLES` are dropped.

    Returns:
        A single bubble dict when only one coupon is given, otherwise a
        ``carousel`` dict. Ready to pass as the Flex message ``contents``.

    Raises:
        ValueError: If ``coupons`` is empty.
    """
    if not coupons:
        raise ValueError("coupons must not be empty")

    bubbles = [_build_coupon_bubble(c) for c in coupons[:MAX_BUBBLES]]

    if len(bubbles) == 1:
        return bubbles[0]

    return {
        "type": "carousel",
        "contents": bubbles,
    }


def _build_coupon_bubble(coupon: dict[str, Any]) -> dict[str, Any]:
    """Build a single coupon bubble from a seed entry (FR-S10).

    The header carries a "🎫 クーポン" badge plus the store name; the body
    highlights the discount and the validity date; the footer holds a URI
    button to the store page. No freshness note is shown because the store
    is fictional (docs/05 §4.15).
    """
    store_name = coupon.get("store_name") or ""
    title = coupon.get("title") or "クーポン"
    summary = coupon.get("summary") or ""
    discount = coupon.get("discount") or ""
    store_url = coupon.get("store_url") or ""
    valid_until = coupon.get("valid_until") or ""

    subtitle = [_COUPON_BADGE_TEXT, store_name] if store_name else [_COUPON_BADGE_TEXT]
    header = style.white_header(title, subtitle=subtitle, accent=_COUPON_COLOR)

    body_contents: list[dict[str, Any]] = []
    if discount:
        body_contents.append(style.label_value("特典", discount))
    if summary:
        body_contents.append(
            {
                "type": "text",
                "text": summary,
                "wrap": True,
                "size": "sm",
                "color": style.TEXT_MAIN,
            }
        )
    if valid_until:
        body_contents.append(
            {
                "type": "text",
                "text": f"⏳ 有効期限: {valid_until}",
                "size": "sm",
                "color": style.TEXT_SUB,
                "wrap": True,
            }
        )

    footer_contents: list[dict[str, Any]] = []
    if store_url:
        footer_contents.append(
            {
                "type": "button",
                "style": "primary",
                "color": _COUPON_COLOR,
                "height": "sm",
                "action": {
                    "type": "uri",
                    "label": "お店で使う",
                    "uri": store_url,
                },
            }
        )

    return style.bubble(
        header=header,
        body=body_contents,
        footer=footer_contents or None,
    )
