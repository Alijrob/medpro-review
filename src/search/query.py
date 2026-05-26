"""
query.py -- OpenSearch Query DSL builders for the Provider Search Service (C14).

All functions are pure: they accept parameters and return a dict suitable for
POST to OpenSearch's /{index}/_search endpoint. No I/O.

Design decisions (DECISIONS.md Entry 028):
  - NPI lookup: single `term` query on `primary_npi` (keyword field, exact match).
    Document _id also equals the NPI; get_doc() is used for direct fetch.
  - Name/specialty text search: `multi_match` with `best_fields`, `fuzziness=AUTO`,
    `operator=and`. Fields:
      primary_name.last (^3), primary_name.full_name_display (^3),
      primary_name.first (^2), name_variants, primary_specialty.description,
      all_taxonomy_descriptions.
    No ngram on the query side (name_search_analyzer strips ngrams; Phase 1-C setting).
  - Boolean filters: `term` on `known_states` (2-letter code), `primary_specialty.code`
    (keyword), `entity_type` (keyword), `has_active_exclusion` (bool), `has_active_license`
    (bool). Filter clauses do not affect relevance scoring.
  - Ranking boost: `function_score` with `field_value_factor` on `identity_confidence`
    (factor=1.5, modifier=none) so high-confidence verified profiles rank above partial
    ones with the same keyword match score.
  - `_source` projection on all queries: only the fields needed by ProviderSearchHit
    are returned, keeping payload size down.
"""
from __future__ import annotations

# Fields returned for every search hit. Mirrors ProviderSearchHit.
_SEARCH_SOURCE_FIELDS = [
    "primary_npi",
    "entity_type",
    "primary_name",
    "primary_specialty",
    "known_states",
    "has_active_exclusion",
    "has_active_license",
    "identity_confidence",
]


def build_npi_query(npi: str) -> dict:
    """
    Exact NPI lookup query.

    Returns a term query that matches exactly one document (the provider whose
    primary_npi == npi). Used by GET /v1/providers/{npi} via client.get_doc(),
    but also useful when testing via the _search endpoint.
    """
    return {
        "query": {"term": {"primary_npi": npi}},
        "size": 1,
        "_source": _SEARCH_SOURCE_FIELDS,
    }


def build_search_query(
    q: str | None = None,
    *,
    state: str | None = None,
    specialty_code: str | None = None,
    entity_type: str | None = None,
    has_exclusion: bool | None = None,
    has_active_license: bool | None = None,
    from_offset: int = 0,
    page_size: int = 10,
) -> dict:
    """
    Build a bool + function_score query for /v1/providers/search.

    When `q` is None or blank, a `match_all` is used (browse mode).
    Filter parameters narrow results without affecting relevance scores.
    The function_score wrapper boosts results by identity_confidence so that
    verified providers rank above partial ones for the same text match.

    Args:
        q:                Free-text query string (name, specialty, city).
        state:            2-letter state code filter (e.g. "CA").
        specialty_code:   NUCC taxonomy code filter (e.g. "207Q00000X").
        entity_type:      "individual" or "organization".
        has_exclusion:    True to show only excluded providers; False to exclude them.
        has_active_license: True/False filter on has_active_license field.
        from_offset:      Zero-based offset for pagination.
        page_size:        Number of results per page.

    Returns:
        OpenSearch request body dict (ready to POST to /{index}/_search).
    """
    must: list[dict] = []
    filter_clauses: list[dict] = []

    # --- Full-text query ---
    if q and q.strip():
        must.append(
            {
                "multi_match": {
                    "query": q.strip(),
                    "fields": [
                        "primary_name.last^3",
                        "primary_name.full_name_display^3",
                        "primary_name.first^2",
                        "name_variants",
                        "primary_specialty.description",
                        "all_taxonomy_descriptions",
                    ],
                    "type": "best_fields",
                    "operator": "and",
                    "fuzziness": "AUTO",
                }
            }
        )
    else:
        must.append({"match_all": {}})

    # --- Filter clauses (no scoring impact) ---
    if state:
        filter_clauses.append({"term": {"known_states": state.upper()}})

    if specialty_code:
        filter_clauses.append({"term": {"primary_specialty.code": specialty_code}})

    if entity_type:
        filter_clauses.append({"term": {"entity_type": entity_type.lower()}})

    if has_exclusion is not None:
        filter_clauses.append({"term": {"has_active_exclusion": has_exclusion}})

    if has_active_license is not None:
        filter_clauses.append({"term": {"has_active_license": has_active_license}})

    bool_query: dict = {"must": must}
    if filter_clauses:
        bool_query["filter"] = filter_clauses

    # --- Wrap in function_score to boost by identity_confidence ---
    return {
        "query": {
            "function_score": {
                "query": {"bool": bool_query},
                "functions": [
                    {
                        "field_value_factor": {
                            "field": "identity_confidence",
                            "factor": 1.5,
                            "modifier": "none",
                            "missing": 0.0,
                        }
                    }
                ],
                "boost_mode": "multiply",
                "score_mode": "sum",
            }
        },
        "from": from_offset,
        "size": page_size,
        "_source": _SEARCH_SOURCE_FIELDS,
    }
