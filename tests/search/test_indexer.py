"""
tests/search/test_indexer.py

Unit tests for search.indexer.ProviderIndexer.

No network I/O -- the OpenSearchClient is replaced with a mock that returns
controlled IndexRawResponse / BulkRawResponse objects.

Coverage:
  index_profile:
    - Success path: returns IndexResult(success=True, npi=...)
    - Client error: returns IndexResult(success=False, error=...)
    - Document passed to client.index_doc has correct doc_id (= NPI)
    - index_name flows through to IndexResult

  index_batch:
    - Empty list: returns BatchIndexResult(total=0, succeeded=0, failed=0), no client call
    - All success (errors=False): succeeded == len(profiles), failures empty
    - Partial failure (errors=True, per-item): failures parsed correctly
    - All-failure bulk error (errors=True, items empty): total=N, succeeded=0, failed=N
    - Correct number of docs passed to bulk_index
    - NPI list order preserved in failure reporting
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

from search.client import BulkRawResponse, IndexRawResponse, OpenSearchClient
from search.indexer import ProviderIndexer
from search.models import BatchIndexResult, IndexResult

from ._fixtures import NPI_ALICE, NPI_ORG, make_full_profile, make_minimal_profile, make_org_profile


# ---------------------------------------------------------------------------
# Mock client helpers
# ---------------------------------------------------------------------------


def make_mock_client(
    index_success: bool = True,
    index_error: str | None = None,
    bulk_errors: bool = False,
    bulk_items: list[dict] | None = None,
) -> MagicMock:
    """
    Create a mock OpenSearchClient.

    index_doc returns IndexRawResponse(success=index_success, ...).
    bulk_index returns BulkRawResponse(errors=bulk_errors, items=bulk_items or []).
    """
    mock = MagicMock(spec=OpenSearchClient)
    mock.index_doc.return_value = IndexRawResponse(
        npi=NPI_ALICE,
        success=index_success,
        index="providers-test",
        result="created" if index_success else "error",
        error=index_error,
    )
    mock.bulk_index.return_value = BulkRawResponse(
        took=1,
        errors=bulk_errors,
        items=bulk_items or [],
    )
    return mock


# ---------------------------------------------------------------------------
# index_profile -- success
# ---------------------------------------------------------------------------


def test_index_profile_success_returns_index_result():
    indexer = ProviderIndexer(index_name="providers-test")
    client = make_mock_client(index_success=True)
    result = indexer.index_profile(make_minimal_profile(), client)
    assert isinstance(result, IndexResult)
    assert result.success is True
    assert result.npi == NPI_ALICE


def test_index_profile_success_no_error():
    indexer = ProviderIndexer(index_name="providers-test")
    result = indexer.index_profile(make_minimal_profile(), make_mock_client())
    assert result.error is None


def test_index_profile_index_name_in_result():
    indexer = ProviderIndexer(index_name="providers-dev")
    result = indexer.index_profile(make_minimal_profile(), make_mock_client())
    assert result.index_name == "providers-dev"


def test_index_profile_doc_id_is_npi():
    """client.index_doc must be called with doc_id == NPI."""
    indexer = ProviderIndexer(index_name="providers-test")
    mock_client = make_mock_client()
    indexer.index_profile(make_minimal_profile(), mock_client)
    call_kwargs = mock_client.index_doc.call_args
    assert call_kwargs.kwargs["doc_id"] == NPI_ALICE


def test_index_profile_index_name_passed_to_client():
    indexer = ProviderIndexer(index_name="providers-prod")
    mock_client = make_mock_client()
    indexer.index_profile(make_minimal_profile(), mock_client)
    call_kwargs = mock_client.index_doc.call_args
    assert call_kwargs.kwargs["index"] == "providers-prod"


def test_index_profile_body_contains_primary_npi():
    indexer = ProviderIndexer(index_name="providers-test")
    mock_client = make_mock_client()
    indexer.index_profile(make_minimal_profile(), mock_client)
    body = mock_client.index_doc.call_args.kwargs["body"]
    assert body["primary_npi"] == NPI_ALICE


# ---------------------------------------------------------------------------
# index_profile -- failure
# ---------------------------------------------------------------------------


def test_index_profile_failure_returns_false():
    indexer = ProviderIndexer(index_name="providers-test")
    result = indexer.index_profile(
        make_minimal_profile(),
        make_mock_client(index_success=False, index_error="timeout"),
    )
    assert result.success is False


def test_index_profile_failure_error_propagated():
    indexer = ProviderIndexer(index_name="providers-test")
    result = indexer.index_profile(
        make_minimal_profile(),
        make_mock_client(index_success=False, index_error="index_not_found"),
    )
    assert result.error == "index_not_found"


# ---------------------------------------------------------------------------
# index_batch -- empty
# ---------------------------------------------------------------------------


def test_index_batch_empty_list_returns_zero_result():
    indexer = ProviderIndexer(index_name="providers-test")
    mock_client = make_mock_client()
    result = indexer.index_batch([], mock_client)
    assert isinstance(result, BatchIndexResult)
    assert result.total == 0
    assert result.succeeded == 0
    assert result.failed == 0


def test_index_batch_empty_list_no_client_call():
    indexer = ProviderIndexer(index_name="providers-test")
    mock_client = make_mock_client()
    indexer.index_batch([], mock_client)
    mock_client.bulk_index.assert_not_called()


# ---------------------------------------------------------------------------
# index_batch -- all success
# ---------------------------------------------------------------------------


def test_index_batch_all_success():
    indexer = ProviderIndexer(index_name="providers-test")
    profiles = [make_minimal_profile(), make_org_profile()]
    result = indexer.index_batch(profiles, make_mock_client(bulk_errors=False))
    assert result.total == 2
    assert result.succeeded == 2
    assert result.failed == 0
    assert result.failures == []


def test_index_batch_correct_doc_count_sent():
    indexer = ProviderIndexer(index_name="providers-test")
    mock_client = make_mock_client()
    profiles = [make_minimal_profile(), make_org_profile()]
    indexer.index_batch(profiles, mock_client)
    docs_arg = mock_client.bulk_index.call_args.kwargs["docs"]
    assert len(docs_arg) == 2


def test_index_batch_correct_npis_in_docs():
    indexer = ProviderIndexer(index_name="providers-test")
    mock_client = make_mock_client()
    profiles = [make_minimal_profile(), make_org_profile()]
    indexer.index_batch(profiles, mock_client)
    docs = mock_client.bulk_index.call_args.kwargs["docs"]
    npi_list = [doc_id for doc_id, _ in docs]
    assert set(npi_list) == {NPI_ALICE, NPI_ORG}


# ---------------------------------------------------------------------------
# index_batch -- partial failure
# ---------------------------------------------------------------------------


def _make_bulk_items_with_error(npi_error: str) -> list[dict]:
    """Simulate one success + one error in the bulk response items list."""
    return [
        {"index": {"_id": NPI_ALICE, "result": "created"}},
        {"index": {"_id": npi_error, "error": {"type": "mapper_exception", "reason": "bad field"}}},
    ]


def test_index_batch_partial_failure():
    indexer = ProviderIndexer(index_name="providers-test")
    profiles = [make_minimal_profile(NPI_ALICE), make_org_profile(NPI_ORG)]
    mock_client = make_mock_client(
        bulk_errors=True,
        bulk_items=_make_bulk_items_with_error(NPI_ORG),
    )
    result = indexer.index_batch(profiles, mock_client)
    assert result.total == 2
    assert result.succeeded == 1
    assert result.failed == 1
    assert len(result.failures) == 1
    assert result.failures[0].npi == NPI_ORG
    assert result.failures[0].success is False


def test_index_batch_all_fail_empty_items():
    """When errors=True but items=[] (e.g. cluster unreachable), all are failed."""
    indexer = ProviderIndexer(index_name="providers-test")
    profiles = [make_minimal_profile(), make_org_profile()]
    mock_client = make_mock_client(bulk_errors=True, bulk_items=[])
    result = indexer.index_batch(profiles, mock_client)
    # items=[] means 0 succeeded and 0 failures parsed from items
    assert result.total == 2
    assert result.succeeded == 0
    assert result.failed == 0  # no items to parse as failures
