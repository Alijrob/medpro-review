"""
test_a1_pubmed.py -- Tests for PubmedNormalizer (A1).

Coverage:
  - Happy path: pmid, title, journal, publication_date, publication_year
  - entity_npi required and set on record
  - Missing entity_npi raises NormalizationError
  - source_record_id set to PMID
  - pubdate "2022 Jan" -> date(2022, 1, 1)
  - DOI extraction from elocationid
  - DOI extraction from articleids list
  - author_position is None (disambiguation deferred)
  - Missing uid raises NormalizationError
  - Missing title raises NormalizationError
"""
from __future__ import annotations

from datetime import date

import pytest

from connectors.models import RawRecord
from normalizers import NormalizationError, get_normalizer
from schema.v1.normalized import PubMedRecord

_normalizer = get_normalizer("A1")


def _make_raw(**overrides) -> RawRecord:
    base = {
        "uid": "12345678",
        "title": "A Study of Family Medicine",
        "pubdate": "2022 Jan",
        "authors": ["Doe J", "Smith A"],
        "source": "JAMA",
        "fulljournalname": "Journal of the American Medical Association",
        "elocationid": "10.1001/jama.2022.1234 [doi]",
        "articleids": [],
    }
    base.update(overrides)
    return RawRecord.from_raw("A1", base)


def test_happy_path_returns_pubmed_record():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert isinstance(rec, PubMedRecord)


def test_entity_npi_set():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.entity_npi == "1234567890"


def test_missing_entity_npi_raises():
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(_make_raw())
    assert "[A1]" in str(exc_info.value)


def test_pmid_extracted():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.pmid == "12345678"


def test_source_record_id_is_pmid():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.provenance.source_record_id == "12345678"


def test_title_extracted():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.title == "A Study of Family Medicine"


def test_journal_from_full_name():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.journal == "Journal of the American Medical Association"


def test_pubdate_year_month_parsed():
    rec = _normalizer.normalize(_make_raw(pubdate="2022 Jan"), entity_npi="1234567890")
    assert rec.publication_date == date(2022, 1, 1)
    assert rec.publication_year == 2022


def test_doi_from_elocationid():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.doi is not None
    assert "10.1001" in rec.doi


def test_doi_from_articleids_list():
    raw = _make_raw(
        elocationid="",
        articleids=[
            {"idtype": "doi", "value": "10.1056/NEJMoa2026766"},
            {"idtype": "pmid", "value": "12345678"},
        ],
    )
    rec = _normalizer.normalize(raw, entity_npi="1234567890")
    assert rec.doi == "10.1056/NEJMoa2026766"


def test_author_position_is_none():
    """Disambiguation deferred to C13 -- author_position must be None in C11."""
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.author_position is None


def test_missing_uid_raises():
    raw = _make_raw(uid="")
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw, entity_npi="1234567890")
    assert "[A1]" in str(exc_info.value)


def test_missing_title_raises():
    raw = _make_raw(title="")
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw, entity_npi="1234567890")
    assert "[A1]" in str(exc_info.value)
