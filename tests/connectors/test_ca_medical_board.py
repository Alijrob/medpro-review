"""
test_ca_medical_board.py -- California Medical Board adapter tests (Phase 3-A, S1).

Exercises the CaMedicalBoardConnector against stub transports; no network I/O,
consistent with the Phase 0 legal gate. Tests cover: config identity, contract
harness, CSV parsing, field-name normalization, empty-body error handling, and
schema drift detection on missing required fields.

Run:
    PYTHONPATH=src pytest tests/connectors/test_ca_medical_board.py -v
"""
from __future__ import annotations

import asyncio
import io
import csv
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.state_boards import CaMedicalBoardConnector, ca_medical_board_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _csv_row(**fields: str) -> dict[str, str]:
    """Return a dict with all 7 required CA contract fields (plus any extras)."""
    row: dict[str, str] = {
        "license_number": "A12345",
        "last_name": "Smith",
        "first_name": "Jane",
        "license_type": "Physician and Surgeon",
        "license_status": "Active",
        "expiration_date": "12/31/2026",
        "city": "Los Angeles",
    }
    row.update(fields)
    return row


def _csv_response(rows: list[dict[str, str]]) -> StubResponse:
    """Render a list of dicts to a CSV string and wrap it in a StubResponse."""
    if not rows:
        return StubResponse(text_body="")
    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return StubResponse(text_body=buf.getvalue())


def _camel_csv_response(*rows_camel: dict[str, str]) -> StubResponse:
    """Build a CSV using DCA camelCase column names (tests normalization)."""
    camel_rows = []
    for row in rows_camel:
        camel_rows.append(row)
    if not camel_rows:
        return StubResponse(text_body="")
    fieldnames = list(camel_rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(camel_rows)
    return StubResponse(text_body=buf.getvalue())


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_state_board_ca_bulk_download(self):
        cfg = ca_medical_board_config()
        assert cfg.source_id == "state_board_ca"
        assert cfg.source_name == "California Medical Board"
        assert cfg.source_category is SourceCategory.STATE_BOARD
        assert cfg.integration_method is IntegrationMethod.BULK_DOWNLOAD

    def test_base_url_points_to_dca(self):
        cfg = ca_medical_board_config()
        assert "dca.ca.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = ca_medical_board_config(rate_limit_per_sec=2.0)
        assert cfg.rate_limit_per_sec == 2.0

    def test_default_rate_limit_is_1(self):
        cfg = ca_medical_board_config()
        assert cfg.rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_csv_passes_contract_harness(self):
        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=stub_transport(_csv_response([_csv_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=stub_transport(_csv_response([_csv_row(), _csv_row(license_number="B99999")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=stub_transport(_csv_response([_csv_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "state_board_ca" for r in result.records)


# ---------------------------------------------------------------------------
class TestCsvNormalization:
    def test_snake_case_headers_pass_through_unchanged(self):
        """Headers that already match contract field names are left as-is."""
        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=stub_transport(_csv_response([_csv_row()])),
        )
        result = asyncio.run(conn.run())
        raw = result.records[0].raw
        assert "license_number" in raw
        assert "last_name" in raw

    def test_camel_case_license_number_is_normalized(self):
        """DCA 'LicenseNumber' variant normalizes to 'license_number'."""
        row = {
            "LicenseNumber": "A12345",
            "LastName": "Smith",
            "FirstName": "Jane",
            "LicenseType": "Physician and Surgeon",
            "Status": "Active",
            "ExpirationDate": "12/31/2026",
            "City": "Los Angeles",
        }
        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=stub_transport(_camel_csv_response(row)),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        assert "license_number" in raw
        assert raw["license_number"] == "A12345"

    def test_space_separated_headers_normalized(self):
        """DCA 'Last Name' (with space) normalizes to 'last_name'."""
        row = {
            "License Number": "A12345",
            "Last Name": "Smith",
            "First Name": "Jane",
            "License Type": "Physician and Surgeon",
            "License Status": "Active",
            "Expiration Date": "12/31/2026",
            "City": "San Francisco",
        }
        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=stub_transport(_camel_csv_response(row)),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        assert raw["last_name"] == "Smith"
        assert raw["city"] == "San Francisco"

    def test_unknown_columns_pass_through(self):
        """Extra columns not in _CSV_FIELD_MAP are preserved as-is."""
        row = _csv_row()
        row["npi_number"] = "1234567890"  # extra column not in the contract
        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=stub_transport(_csv_response([row])),
        )
        result = asyncio.run(conn.run())
        assert result.records[0].raw.get("npi_number") == "1234567890"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_empty_body_raises_source_unavailable(self):
        from connectors.errors import SourceUnavailableError
        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=stub_transport(StubResponse(text_body="")),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_missing_required_field_triggers_schema_drift(self):
        """A CSV whose header lacks a required column triggers drift on every row.

        In a CSV adapter, column headers are shared across all rows. If 'city' is
        absent from the header, every row will be missing it -- all rows fail and
        the run status is FAILED (not PARTIAL).
        """
        no_city = {k: v for k, v in _csv_row().items() if k != "city"}
        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=stub_transport(_csv_response([no_city, no_city])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.schema_drift_detected is True

    def test_all_bad_rows_returns_failed(self):
        bad = _csv_row()
        del bad["license_number"]
        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=stub_transport(_csv_response([bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_bulk_download_makes_single_request(self):
        """CA is BULK_DOWNLOAD -- exactly one GET per run."""
        calls: list[Any] = []
        original = _csv_response([_csv_row()])

        async def recording_transport(method: str, url: str, **kwargs: Any) -> StubResponse:
            calls.append((method, url))
            return original

        conn = CaMedicalBoardConnector(
            ca_medical_board_config(),
            transport=recording_transport,
        )
        asyncio.run(conn.run())
        assert len(calls) == 1
        assert calls[0][0] == "GET"
