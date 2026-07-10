"""Unit tests for :mod:`src.services.prompts` freshness annotation (Phase 3).

These verify NFR-Truth-4 behaviour: seed freshness fields are surfaced to
Gemini via the ``_summarise_*`` helpers, and the life-consultation prompt
instructs Gemini to quote them at the end of any reply that names a real
store or area. See ``docs/04_functional_spec.md §4.4`` and
``docs/06_ai_spec.md §4.2``.

Style follows ``tests/test_text_format.py``: no pytest dependency, plain
``assert`` inside class-grouped methods so the file can be executed
directly on machines without pytest / ``fcntl`` (e.g. Windows).
"""

from src.services import prompts


class TestSummariseStores:
    def test_includes_data_freshness_note(self) -> None:
        stores = [
            {
                "name": "喫茶進々堂",
                "category": "cafe",
                "area": "百万遍",
                "description": "老舗喫茶",
                "data_freshness_note": "2026-07 時点の情報",
            }
        ]
        out = prompts._summarise_stores(stores)
        assert "2026-07 時点の情報" in out
        assert "[情報鮮度:" in out

    def test_falls_back_to_unknown_when_field_missing(self) -> None:
        stores = [
            {
                "name": "無鮮度店",
                "category": "restaurant",
                "area": "上京区",
                "description": "",
            }
        ]
        out = prompts._summarise_stores(stores)
        assert "[情報鮮度: 不明]" in out

    def test_empty_stores_returns_placeholder(self) -> None:
        assert prompts._summarise_stores([]) == "（該当なし）"


class TestSummariseAreas:
    def test_includes_last_verified_at(self) -> None:
        areas = [
            {
                "name": "京都市上京区役所",
                "category": "government",
                "description": "行政窓口",
                "last_verified_at": "2026-07",
            }
        ]
        out = prompts._summarise_areas(areas)
        assert "2026-07" in out
        assert "[情報鮮度:" in out

    def test_falls_back_to_unknown_when_field_missing(self) -> None:
        areas = [{"name": "無鮮度エリア", "category": "district", "description": ""}]
        out = prompts._summarise_areas(areas)
        assert "[情報鮮度: 不明]" in out


class TestSummariseEvents:
    def test_includes_last_verified_at(self) -> None:
        events = [
            {
                "name": "同志社EVE",
                "category": "festival",
                "area": "今出川",
                "description": "学園祭",
                "schedule": "毎年11月",
                "last_verified_at": "2026-07",
            }
        ]
        out = prompts._summarise_events(events)
        assert "2026-07" in out
        assert "[情報鮮度:" in out


class TestBuildLifeConsultationPrompt:
    def _build(self, *, total_hits: int = 1) -> str:
        return prompts.build_life_consultation_prompt(
            profile=None,
            user_message="近くのカフェを教えて",
            stores=[
                {
                    "name": "喫茶進々堂",
                    "category": "cafe",
                    "area": "百万遍",
                    "description": "老舗喫茶",
                    "data_freshness_note": "2026-07 時点の情報",
                }
            ],
            areas=[],
            senior_posts=[],
            student_posts=[],
            total_hits=total_hits,
        )

    def test_freshness_extraction_rule_present(self) -> None:
        # The prompt must instruct Gemini to lift the [情報鮮度: ...] value
        # verbatim and add it as "※ (値)" at the end of the answer.
        text = self._build()
        assert "情報鮮度" in text
        assert "※" in text

    def test_store_freshness_value_reaches_prompt(self) -> None:
        # The concrete freshness note from the seed record must be present
        # in the prompt body (so Gemini can quote it).
        text = self._build()
        assert "2026-07 時点の情報" in text

    def test_zero_context_line_included_when_no_hits(self) -> None:
        text = self._build(total_hits=0)
        assert "total_hits が 0" in text

    def test_json_output_fields_instructed(self) -> None:
        # docs/06 §4.2: the prompt must request a JSON object with the
        # empathy / answer / closing keys so the handler can split bubbles.
        text = self._build()
        assert "JSON" in text
        assert '"empathy"' in text
        assert '"answer"' in text
        assert '"closing"' in text
