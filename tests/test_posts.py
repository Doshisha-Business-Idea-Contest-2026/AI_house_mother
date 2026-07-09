"""Unit tests for :mod:`src.services.posts` (FR-S6, T4.14).

Cover the structured experience-post capture: skip-token normalization,
``body`` composition from the five structured fields, and the record
shape / truncation produced by ``add_post``. See
``docs/04_functional_spec.md`` §4.5 and ``docs/05_data_model.md`` §4.3.

Style follows ``tests/test_usage_stats.py``: no pytest fixtures; each
test class redirects ``src.services.storage.DATA_DIR`` to a temp path in
``setup_method`` and restores it in ``teardown_method`` so the real
``data/`` directory is never touched.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from src.services import posts, storage


class _TempDataDirMixin:
    def setup_method(self) -> None:
        self._orig_data_dir = storage.DATA_DIR
        self._tmp = Path(tempfile.mkdtemp(prefix="ai_house_mother_test_"))
        storage.DATA_DIR = self._tmp

    def teardown_method(self) -> None:
        storage.DATA_DIR = self._orig_data_dir
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestNormalizeSkippable:
    def test_none_returns_none(self) -> None:
        assert posts._normalize_skippable(None) is None

    def test_empty_and_whitespace_return_none(self) -> None:
        assert posts._normalize_skippable("") is None
        assert posts._normalize_skippable("   ") is None

    def test_skip_tokens_return_none(self) -> None:
        for token in ("skip", "SKIP", "スキップ", "なし", "無し"):
            assert posts._normalize_skippable(token) is None

    def test_real_value_is_stripped_and_kept(self) -> None:
        assert posts._normalize_skippable("  下鴨神社  ") == "下鴨神社"

    def test_normalize_area_delegates(self) -> None:
        assert posts._normalize_area("skip") is None
        assert posts._normalize_area("進々堂") == "進々堂"


class TestComposeBody:
    def test_all_fields_render_in_fixed_order(self) -> None:
        body = posts.compose_body(
            period="先週末",
            summary="清掃に参加",
            learned="地域の人と話せた",
            regret="朝が早い",
            advice="動きやすい服で",
        )
        assert body == (
            "【いつ】先週末\n"
            "【やったこと】清掃に参加\n"
            "【学び】地域の人と話せた\n"
            "【残念・注意】朝が早い\n"
            "【次の人へ】動きやすい服で"
        )

    def test_skipped_fields_are_omitted(self) -> None:
        body = posts.compose_body(
            period=None,
            summary="清掃に参加",
            learned="地域の人と話せた",
            regret=None,
            advice=None,
        )
        assert body == "【やったこと】清掃に参加\n【学び】地域の人と話せた"

    def test_all_empty_returns_empty_string(self) -> None:
        assert posts.compose_body(None, "", "", None, "   ") == ""

    def test_result_is_truncated_to_max_body_len(self) -> None:
        long = "あ" * (posts.MAX_BODY_LEN + 50)
        body = posts.compose_body(None, long, None, None, None)
        assert len(body) == posts.MAX_BODY_LEN


class TestAddPost(_TempDataDirMixin):
    def _add(self, **overrides: object) -> dict:
        kwargs: dict = {
            "line_user_id": "U-abc",
            "category": "volunteer",
            "title": "下鴨神社の清掃",
            "summary": "月例清掃に参加",
            "learned": "地域の人と話せた",
            "area": "下鴨神社",
            "share_with_parent": True,
            "period": "2025年10月",
            "period_raw": "去年の10月",
            "regret": "朝が早い",
            "advice": "動きやすい服で",
        }
        kwargs.update(overrides)
        return posts.add_post(**kwargs)  # type: ignore[arg-type]

    def test_record_has_structured_fields_and_composed_body(self) -> None:
        record = self._add()
        assert record["period"] == "2025年10月"
        assert record["period_raw"] == "去年の10月"
        assert record["summary"] == "月例清掃に参加"
        assert record["learned"] == "地域の人と話せた"
        assert record["regret"] == "朝が早い"
        assert record["advice"] == "動きやすい服で"
        # The body uses the normalized period, not the raw words.
        assert record["body"] == posts.compose_body(
            "2025年10月",
            "月例清掃に参加",
            "地域の人と話せた",
            "朝が早い",
            "動きやすい服で",
        )
        assert record["post_id"] == "P00001"
        assert record["share_with_parent"] is True

    def test_body_period_falls_back_to_raw_when_not_normalized(self) -> None:
        # When normalization was skipped/failed, period is None but the
        # raw words are kept and used for the body's 【いつ】 (docs/05 §4.3).
        record = self._add(period=None, period_raw="去年の10月")
        assert record["period"] is None
        assert record["period_raw"] == "去年の10月"
        assert record["body"].startswith("【いつ】去年の10月\n")

    def test_skipped_optionals_stored_as_none(self) -> None:
        record = self._add(period=None, period_raw=None, regret=None, advice=None)
        assert record["period"] is None
        assert record["period_raw"] is None
        assert record["regret"] is None
        assert record["advice"] is None
        assert (
            record["body"] == "【やったこと】月例清掃に参加\n【学び】地域の人と話せた"
        )

    def test_fields_are_truncated_to_their_caps(self) -> None:
        record = self._add(
            summary="さ" * (posts.MAX_SUMMARY_LEN + 10),
            learned="ま" * (posts.MAX_LEARNED_LEN + 10),
        )
        assert len(record["summary"]) == posts.MAX_SUMMARY_LEN
        assert len(record["learned"]) == posts.MAX_LEARNED_LEN

    def test_invalid_category_raises(self) -> None:
        raised = False
        try:
            self._add(category="not-a-category")
        except ValueError:
            raised = True
        assert raised

    def test_composed_body_reaches_context_projection(self) -> None:
        # The SECI context reader must see the composed body verbatim so
        # downstream stays unchanged (docs/06 §4.2).
        self._add()
        projected = posts.list_all_for_context()
        assert len(projected) == 1
        assert projected[0]["body"] == posts.compose_body(
            "2025年10月",
            "月例清掃に参加",
            "地域の人と話せた",
            "朝が早い",
            "動きやすい服で",
        )
        assert "line_user_id" not in projected[0]
