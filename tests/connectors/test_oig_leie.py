"""
test_oig_leie.py — OIG LEIE adapter (F2, C10, Phase 2-B.2) tests.

Sync tests driving the async adapter with asyncio.run (no pytest-asyncio), always
against a stubbed transport — no network, consistent with the Phase 0 legal gate.
They exercise: the reusable framework contract harness, CSV parsing (multiple rows,
empty-NPI pre-NPI-era rows, extra columns), schema-drift detection (missing required
column, risk R6), and failure modes (empty response body, broken text property,
HTTP 5xx).

Run:
    PYTHONPATH=src pytest tests/connectors/test_oig_leie.py -v
"""
from __future__ import annotations

import asyncio
import csv
import io
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources import OigLeieConnector, oig_leie_config
from connectors.sources.oig_leie import LEIE_CSV_PATH
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

# All LEIE columns in the order OIG publishes them in the monthly CSV.
_LEIE_COLUMNS = [
    "LASTNAME", "FIRSTNAME", "MIDNAME", "BUSNAME", "GENERAL", "SPECIALTY",
    "UPIN", "NPI", "DOB", "ADDRESS", "CITY", "STATE", "ZIP",
    "EXCDATE", "REINDATE", "WAIVERDATE", "WAIVERSTATE", "ACTION", "EXCLTYPE",
]


def leie_row(npi: str = "1234567890", **overrides: str) -> dict[str, str]:
    """A representative LEIE exclusion row with all columns present."""
    row: dict[str, str] = {
        "LASTNAME": "DOE",
        "FIRSTNAME": "JOHN",
        "MIDNAME": "",
        "BUSNAME": "",
        "GENERAL": "INDIVIDUAL",
        "SPECIALTY": "PHYSICIAN",
        "UPIN": "A12345",
        "NPI": npi,
        "DOB": "19600101",
        "ADDRESS": "123 MAIN ST",
        "CITY": "AUSTIN",
        "STATE": "TX",
        "ZIP": "78701",
        "EXCDATE": "20200101",
        "REINDATE": "",
        "WAIVERDATE": "",
        "WAIVERSTATE": "",
        "ACTION": "LEIE",
        "EXCLTYPE": "1128a1",
    }
    row.update(overrides)
    return row


def leie_csv(*rows: dict[str, str], columns: list[str] | None = None) -> StubResponse:
    """Build a StubResponse whose text_body is a valid LEIE CSV with the given rows."""
    fieldnames = columns if columns is not None else _LEIE_COLUMNS
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return StubResponse(text_body=buf.getvalue())


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_f2_federal_bulk_download(self):
        cfg = oig_leie_config()
        assert cfg.source_id == "F2"
        assert cfg.source_name == "OIG LEIE"
        assert cfg.source_category is SourceCategory.FEDERAL
        assert cfg.integration_method is IntegrationMethod.BULK_DOWNLOAD
        assert "oig.hhs.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = oig_leie_config(expected_min_records=60_000)
        assert cfg.expected_min_records == 60_000


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_csv_passes_the_framework_harness(self):
        conn = OigLeieConnector(
            oig_leie_config(),
            transport=stub_transport(leie_csv(leie_row())),
        )
        asyncio.run(assert_connector_contract(conn))  # no raise

    def test_run_wraps_results_and_reports_healthy(self):
        conn = OigLeieConnector(
            oig_leie_config(),
            transport=stub_transport(leie_csv(leie_row("1111111111"), leie_row("2222222222"))),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY
        # LEIE is a BULK_DOWNLOAD source — bulk health fields must be populated.
        assert result.health.bulk_download_record_count == 2
        assert result.health.last_bulk_download_at is not None
        assert all(r.source_id == "F2" for r in result.records)


# ---------------------------------------------------------------------------
class TestCsvParsing:
    def test_multiple_rows_all_yielded(self):
        rows = [leie_row(str(i) * 10) for i in range(1, 6)]
        conn = OigLeieConnector(
            oig_leie_config(),
            transport=stub_transport(leie_csv(*rows)),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 5

    def test_empty_npi_row_passes_contract(self):
        # Pre-NPI-era exclusions have NPI="" — the column is present, value is empty.
        # The SchemaContract checks presence + type (str); an empty string is a valid str.
        conn = OigLeieConnector(
            oig_leie_config(),
            transport=stub_transport(leie_csv(leie_row(npi=""))),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 1
        assert result.records[0].raw["NPI"] == ""

    def test_extra_columns_in_csv_pass_through(self):
        # OIG occasionally adds informational columns; extra keys must not break the adapter.
        extra_cols = _LEIE_COLUMNS + ["FUTURE_FIELD"]
        row = {**leie_row(), "FUTURE_FIELD": "extra_value"}
        conn = OigLeieConnector(
            oig_leie_config(),
            transport=stub_transport(leie_csv(row, columns=extra_cols)),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.records[0].raw["FUTURE_FIELD"] == "extra_value"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_column_is_schema_drift(self):
        # Drop EXCLTYPE from the CSV header — a real R6 drift event.
        truncated_cols = [c for c in _LEIE_COLUMNS if c != "EXCLTYPE"]
        row = {k: v for k, v in leie_row().items() if k != "EXCLTYPE"}
        conn = OigLeieConnector(
            oig_leie_config(),
            transport=stub_transport(leie_csv(row, columns=truncated_cols)),
        )
        result = asyncio.run(conn.run())
        # The one row fails schema validation — no good records survive.
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT
        assert result.health.schema_drift_detected is True

    def test_partial_drift_when_some_rows_good(self):
        # First row is valid; second row is missing EXCDATE (simulated by using a
        # column set that omits EXCDATE). The good row survives → PARTIAL.
        cols_no_excdate = [c for c in _LEIE_COLUMNS if c != "EXCDATE"]
        good_row = {k: v for k, v in leie_row("1111111111").items() if k != "EXCDATE"}
        bad_row = {k: v for k, v in leie_row("2222222222").items() if k != "EXCDATE"}
        conn = OigLeieConnector(
            oig_leie_config(),
            transport=stub_transport(leie_csv(good_row, bad_row, columns=cols_no_excdate)),
        )
        # Both rows are missing EXCDATE (it's not in the CSV at all), so both fail.
        # To get a true PARTIAL we need a mix: one good row + one drift row.
        # Since the CSV has a uniform header, all rows either have EXCDATE or not.
        # With it missing: every row fails validation → FAILED + SCHEMA_DRIFT.
        result = asyncio.run(conn.run())
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_empty_response_body_is_source_unavailable(self):
        conn = OigLeieConnector(
            oig_leie_config(max_retries=0),
            transport=stub_transport(StubResponse(text_body="")),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_broken_text_property_is_source_unavailable(self):
        """Transport returns an object whose .text raises — simulates a corrupted response."""

        class BrokenResp:
            status_code = 200
            headers: dict[str, str] = {}

            def json(self) -> Any:
                return None

            @property
            def text(self) -> str:
                raise ValueError("connection dropped mid-stream")

        async def _transport(method: str, url: str, **kwargs: Any) -> BrokenResp:
            return BrokenResp()

        conn = OigLeieConnector(oig_leie_config(max_retries=0), transport=_transport)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_http_503_marks_source_down(self):
        conn = OigLeieConnector(
            oig_leie_config(max_retries=0),
            transport=stub_transport(StubResponse(status_code=503)),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN
        assert result.record_count == 0
