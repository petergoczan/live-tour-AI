"""Unit tests for generator module: _parse_fact_list, _display_name_for_lang, _origin_name, JobStatus."""
import pytest

from api.v1.generator import (
    _parse_fact_list,
    _display_name_for_lang,
    _origin_name,
)
from core.schemas import JobStatus


class TestJobStatus:
    """JobStatus enum values are used as string status in storage and API."""

    def test_values_are_strings(self):
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.GENERATING.value == "generating"
        assert JobStatus.DONE.value == "done"
        assert JobStatus.FAILED.value == "failed"


class TestParseFactList:
    """_parse_fact_list extracts a 5-element JSON array from model output."""

    def test_valid_json_array(self):
        raw = '["fact one", "fact two", "fact three", "fact four", "fact five"]'
        result = _parse_fact_list(raw)
        assert result == ["fact one", "fact two", "fact three", "fact four", "fact five"]

    def test_json_inside_markdown_code_block(self):
        raw = 'Some text\n```json\n["a", "b", "c", "d", "e"]\n```\nmore text'
        result = _parse_fact_list(raw)
        assert result == ["a", "b", "c", "d", "e"]

    def test_json_code_block_without_lang(self):
        raw = '```\n["x", "y", "z", "w", "v"]\n```'
        result = _parse_fact_list(raw)
        assert result == ["x", "y", "z", "w", "v"]

    def test_surrounded_text(self):
        raw = 'Here is the list: ["one", "two", "three", "four", "five"] and that is all.'
        result = _parse_fact_list(raw)
        assert result == ["one", "two", "three", "four", "five"]

    def test_wrong_length_returns_none(self):
        raw = '["a", "b", "c"]'
        assert _parse_fact_list(raw) is None
        raw = '["a", "b", "c", "d", "e", "f"]'
        assert _parse_fact_list(raw) is None

    def test_no_array_returns_none(self):
        assert _parse_fact_list("no brackets here") is None
        assert _parse_fact_list("") is None

    def test_invalid_json_returns_none(self):
        raw = '["unclosed string, "b", "c", "d", "e"]'
        assert _parse_fact_list(raw) is None

    def test_non_list_json_returns_none(self):
        raw = '{"key": "value"}'
        assert _parse_fact_list(raw) is None


class TestDisplayNameForLang:
    """_display_name_for_lang picks name_hu for HU, name_en for EN, with fallbacks."""

    def test_hu_uses_name_hu(self):
        m = {"name_hu": "Medve", "name_en": "Bear", "origin_name": "Ursus"}
        assert _display_name_for_lang(m, "HU") == "Medve"
        assert _display_name_for_lang(m, "hu") == "Medve"

    def test_en_uses_name_en(self):
        m = {"name_hu": "Medve", "name_en": "Bear", "origin_name": "Ursus"}
        assert _display_name_for_lang(m, "EN") == "Bear"
        assert _display_name_for_lang(m, "en") == "Bear"

    def test_hu_fallback_when_name_hu_empty(self):
        m = {"name_hu": "", "name_en": "Bear", "origin_name": "Ursus"}
        assert _display_name_for_lang(m, "HU") == "Bear"
        m = {"name_hu": "  ", "name_en": "Bear", "origin_name": "Ursus"}
        assert _display_name_for_lang(m, "HU") == "Bear"

    def test_en_fallback_when_name_en_empty(self):
        m = {"name_hu": "Medve", "name_en": "", "origin_name": "Ursus"}
        assert _display_name_for_lang(m, "EN") == "Medve"

    def test_fallback_to_origin_name(self):
        m = {"name_hu": "", "name_en": "", "origin_name": "Ursus arctos"}
        assert _display_name_for_lang(m, "HU") == "Ursus arctos"
        assert _display_name_for_lang(m, "EN") == "Ursus arctos"

    def test_unknown_returns_unknown(self):
        m = {"name_hu": "", "name_en": "", "origin_name": ""}
        assert _display_name_for_lang(m, "HU") == "Unknown"
        assert _display_name_for_lang(m, "EN") == "Unknown"


class TestOriginName:
    """_origin_name returns marker's origin_name or a default for the prompt."""

    def test_returns_origin_when_present(self):
        m = {"origin_name": "Ursus arctos"}
        assert _origin_name(m) == "Ursus arctos"

    def test_returns_none_placeholder_when_empty(self):
        m = {}
        assert _origin_name(m) == "(none)"
        m = {"origin_name": ""}
        assert _origin_name(m) == "(none)"
        m = {"origin_name": "   "}
        assert _origin_name(m) == "(none)"
