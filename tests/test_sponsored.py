"""Unit tests for :mod:`src.services.sponsored` matching (FR-S9).

Cover the deterministic sponsored-PR selection (docs/04 §4.3, docs/05
§4.12): faculty partial match, grade string match, interest overlap,
empty ``target`` axes, ``active`` filtering, the score-0 no-show rule,
and top-1 selection among several candidates. Matching is exercised via
the ``items`` injection point so the tests stay seed-independent.

Style follows ``tests/test_activity_carousel.py``: no pytest dependency.
"""

from src.services import sponsored


def _entry(
    sponsor_id: str,
    *,
    faculties: list[str] | None = None,
    grades: list[str] | None = None,
    interest_tags: list[str] | None = None,
    active: bool = True,
) -> dict[str, object]:
    return {
        "sponsor_id": sponsor_id,
        "company_name": f"{sponsor_id}社（架空）",
        "title": f"{sponsor_id} イベント",
        "target": {
            "faculties": faculties or [],
            "grades": grades or [],
            "interest_tags": interest_tags or [],
        },
        "active": active,
    }


_PROFILE = {
    "faculty": "経済学部",
    "grade": "3",
    "interests": ["スポーツ", "学問・研究", "食・カフェ巡り"],
}


class TestScore:
    def test_faculty_partial_match_scores_one(self) -> None:
        entry = _entry("A", faculties=["経済"])
        assert sponsored._score(_PROFILE, entry) == 1

    def test_faculty_no_match_scores_zero(self) -> None:
        entry = _entry("A", faculties=["工"])
        assert sponsored._score(_PROFILE, entry) == 0

    def test_grade_string_match_scores_one(self) -> None:
        entry = _entry("A", grades=["3", "4"])
        assert sponsored._score(_PROFILE, entry) == 1

    def test_grade_type_coerced_to_string(self) -> None:
        # Defensive: even if a seed slips an int grade through, it matches.
        entry = _entry("A")
        entry["target"]["grades"] = [3, 4]  # type: ignore[index]
        assert sponsored._score(_PROFILE, entry) == 1

    def test_interest_overlap_counts_each_tag(self) -> None:
        entry = _entry("A", interest_tags=["学問・研究", "食・カフェ巡り"])
        assert sponsored._score(_PROFILE, entry) == 2

    def test_empty_target_axes_score_zero(self) -> None:
        entry = _entry("A")
        assert sponsored._score(_PROFILE, entry) == 0

    def test_combined_axes_sum(self) -> None:
        entry = _entry(
            "A", faculties=["経済"], grades=["3"], interest_tags=["学問・研究"]
        )
        assert sponsored._score(_PROFILE, entry) == 3


class TestMatchForProfile:
    def test_returns_none_when_no_axis_matches(self) -> None:
        entry = _entry("A", faculties=["工"], grades=["1"], interest_tags=["音楽"])
        assert sponsored.match_for_profile(_PROFILE, items=[entry]) is None

    def test_excludes_inactive_entries(self) -> None:
        entry = _entry("A", faculties=["経済"], active=False)
        assert sponsored.match_for_profile(_PROFILE, items=[entry]) is None

    def test_selects_highest_scoring_entry(self) -> None:
        low = _entry("LOW", faculties=["経済"])  # score 1
        high = _entry(
            "HIGH", faculties=["経済"], grades=["3"], interest_tags=["学問・研究"]
        )  # score 3
        match = sponsored.match_for_profile(_PROFILE, items=[low, high])
        assert match is not None
        assert match["sponsor_id"] == "HIGH"

    def test_ties_resolve_to_seed_order(self) -> None:
        first = _entry("FIRST", faculties=["経済"])  # score 1
        second = _entry("SECOND", grades=["3"])  # score 1
        match = sponsored.match_for_profile(_PROFILE, items=[first, second])
        assert match is not None
        assert match["sponsor_id"] == "FIRST"

    def test_empty_profile_returns_none(self) -> None:
        entry = _entry("A", faculties=["経済"])
        assert sponsored.match_for_profile({}, items=[entry]) is None
