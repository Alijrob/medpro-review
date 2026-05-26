"""
tests/search/test_query.py

Unit tests for search.query DSL builders.

Pure functions -- no I/O, no mocks needed.

Coverage:
  build_npi_query:
    - Returns a term query on primary_npi
    - size=1 always
    - _source fields present

  build_search_query:
    - No q + no filters: match_all inside function_score
    - With q: multi_match on name/specialty fields
    - state filter: term on known_states (uppercased)
    - specialty_code filter: term on primary_specialty.code
    - entity_type filter: term on entity_type (lowercased)
    - has_exclusion True/False: term on has_active_exclusion
    - has_active_license True/False: term on has_active_license
    - Combined filters: all appear in filter array
    - Pagination: from/size in body
    - _source fields always present
    - function_score structure: field_value_factor on identity_confidence
    - Empty q string treated as match_all
"""
from __future__ import annotations

import pytest

from search.query import build_npi_query, build_search_query


# ---------------------------------------------------------------------------
# build_npi_query
# ---------------------------------------------------------------------------


def test_npi_query_structure():
    body = build_npi_query("1234567890")
    assert "query" in body
    assert "term" in body["query"]
    assert "primary_npi" in body["query"]["term"]
    assert body["query"]["term"]["primary_npi"] == "1234567890"


def test_npi_query_size_one():
    body = build_npi_query("1234567890")
    assert body.get("size") == 1


def test_npi_query_source_fields():
    body = build_npi_query("1234567890")
    assert "_source" in body
    assert "primary_npi" in body["_source"]


# ---------------------------------------------------------------------------
# build_search_query -- baseline structure
# ---------------------------------------------------------------------------


def test_search_query_returns_dict():
    body = build_search_query()
    assert isinstance(body, dict)


def test_search_query_has_query_key():
    body = build_search_query()
    assert "query" in body


def test_search_query_function_score_present():
    body = build_search_query()
    assert "function_score" in body["query"]


def test_search_query_function_score_has_identity_confidence_factor():
    body = build_search_query()
    fs = body["query"]["function_score"]
    funcs = fs.get("functions", [])
    assert len(funcs) == 1
    fvf = funcs[0]["field_value_factor"]
    assert fvf["field"] == "identity_confidence"
    assert fvf["factor"] == 1.5


def test_search_query_boost_mode():
    body = build_search_query()
    fs = body["query"]["function_score"]
    assert fs["boost_mode"] == "multiply"


def test_search_query_source_fields_present():
    body = build_search_query()
    src = body["_source"]
    assert "primary_npi" in src
    assert "primary_name" in src
    assert "known_states" in src
    assert "identity_confidence" in src


def test_search_query_from_and_size():
    body = build_search_query(from_offset=20, page_size=5)
    assert body["from"] == 20
    assert body["size"] == 5


def test_search_query_default_pagination():
    body = build_search_query()
    assert body["from"] == 0
    assert body["size"] == 10


# ---------------------------------------------------------------------------
# build_search_query -- no q = match_all
# ---------------------------------------------------------------------------


def _extract_bool(body: dict) -> dict:
    """Unwrap function_score -> query -> bool."""
    return body["query"]["function_score"]["query"]["bool"]


def test_no_q_uses_match_all():
    body = build_search_query()
    bool_q = _extract_bool(body)
    must = bool_q["must"]
    assert len(must) == 1
    assert "match_all" in must[0]


def test_empty_q_string_uses_match_all():
    body = build_search_query(q="   ")
    bool_q = _extract_bool(body)
    must = bool_q["must"]
    assert "match_all" in must[0]


# ---------------------------------------------------------------------------
# build_search_query -- with q = multi_match
# ---------------------------------------------------------------------------


def test_with_q_uses_multi_match():
    body = build_search_query(q="Smith cardiology")
    bool_q = _extract_bool(body)
    must = bool_q["must"]
    assert len(must) == 1
    assert "multi_match" in must[0]


def test_multi_match_query_value():
    body = build_search_query(q="  Alice Smith  ")
    mm = _extract_bool(body)["must"][0]["multi_match"]
    assert mm["query"] == "Alice Smith"


def test_multi_match_covers_last_name_field():
    body = build_search_query(q="Jones")
    fields = _extract_bool(body)["must"][0]["multi_match"]["fields"]
    assert any("last" in f for f in fields)


def test_multi_match_covers_full_name_display():
    body = build_search_query(q="Jones")
    fields = _extract_bool(body)["must"][0]["multi_match"]["fields"]
    assert any("full_name_display" in f for f in fields)


def test_multi_match_covers_specialty_description():
    body = build_search_query(q="cardiology")
    fields = _extract_bool(body)["must"][0]["multi_match"]["fields"]
    assert any("description" in f for f in fields)


def test_multi_match_operator_and():
    body = build_search_query(q="Alice Smith")
    mm = _extract_bool(body)["must"][0]["multi_match"]
    assert mm["operator"] == "and"


def test_multi_match_fuzziness_auto():
    body = build_search_query(q="Smyth")
    mm = _extract_bool(body)["must"][0]["multi_match"]
    assert mm["fuzziness"] == "AUTO"


# ---------------------------------------------------------------------------
# build_search_query -- filters
# ---------------------------------------------------------------------------


def _get_filter_terms(body: dict) -> list[dict]:
    bool_q = _extract_bool(body)
    return bool_q.get("filter", [])


def test_no_filters_no_filter_clause():
    body = build_search_query()
    bool_q = _extract_bool(body)
    assert "filter" not in bool_q


def test_state_filter_uppercased():
    body = build_search_query(state="ca")
    terms = _get_filter_terms(body)
    assert any(t.get("term", {}).get("known_states") == "CA" for t in terms)


def test_specialty_code_filter():
    body = build_search_query(specialty_code="207Q00000X")
    terms = _get_filter_terms(body)
    assert any(t.get("term", {}).get("primary_specialty.code") == "207Q00000X" for t in terms)


def test_entity_type_filter_lowercased():
    body = build_search_query(entity_type="INDIVIDUAL")
    terms = _get_filter_terms(body)
    assert any(t.get("term", {}).get("entity_type") == "individual" for t in terms)


def test_has_exclusion_true_filter():
    body = build_search_query(has_exclusion=True)
    terms = _get_filter_terms(body)
    assert any(t.get("term", {}).get("has_active_exclusion") is True for t in terms)


def test_has_exclusion_false_filter():
    body = build_search_query(has_exclusion=False)
    terms = _get_filter_terms(body)
    assert any(t.get("term", {}).get("has_active_exclusion") is False for t in terms)


def test_has_active_license_filter():
    body = build_search_query(has_active_license=True)
    terms = _get_filter_terms(body)
    assert any(t.get("term", {}).get("has_active_license") is True for t in terms)


def test_combined_filters_all_present():
    body = build_search_query(
        q="Smith",
        state="NY",
        specialty_code="207Q00000X",
        entity_type="individual",
        has_exclusion=False,
        has_active_license=True,
    )
    terms = _get_filter_terms(body)
    field_names = [list(t.get("term", {}).keys())[0] for t in terms if "term" in t]
    assert "known_states" in field_names
    assert "primary_specialty.code" in field_names
    assert "entity_type" in field_names
    assert "has_active_exclusion" in field_names
    assert "has_active_license" in field_names
    assert len(terms) == 5
