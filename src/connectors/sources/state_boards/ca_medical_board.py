"""
ca_medical_board.py -- California Medical Board adapter (source state_board_ca, Phase 3-A).

The California Medical Board (a division of the CA Department of Consumer Affairs, DCA)
publishes a bulk download of all licensed physicians, surgeons, and related practitioners.
The DCA bulk data endpoint provides a CSV file containing all active and inactive licenses.

Integration method: **BULK_DOWNLOAD** -- one HTTP request downloads the full CSV; no
pagination required. This is the authoritative, complete dataset (unlike a per-provider
lookup which would require iterating NPI by NPI).

Endpoint: https://search.dca.ca.gov/results (POST request returns CSV) or the DCA
OpenData bulk file at https://data.ca.gov/dataset/dca-license-data (SODA or direct CSV).
This adapter uses the DCA bulk CSV at DEFAULT_BASE_URL/DEFAULT_PATH.

Schema contract (7 fields):
    license_number   -- CA license identifier (e.g. A12345 for Physician/Surgeon)
    last_name        -- practitioner last name
    first_name       -- practitioner first name
    license_type     -- e.g. "Physician and Surgeon", "Osteopathic Physician"
    license_status   -- e.g. "Active", "Expired", "Revoked", "Surrendered"
    expiration_date  -- date string (MM/DD/YYYY format in DCA export)
    city             -- city of practice address

LEGAL GATE: live ingest governed by Phase 0 FCRA determination. Tested with stub transports.
"""
from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from typing import Any

from schema.v1.common import SourceCategory

from ...base import SourceConnector
from ...config import ConnectorConfig
from ...contract import SchemaContract
from ...errors import SourceUnavailableError
from ...models import IntegrationMethod

DEFAULT_BASE_URL = "https://search.dca.ca.gov"
DEFAULT_PATH = "/bulkdata/physician-surgeon-csv"

_CA_REQUIRED_FIELDS = frozenset({
    "license_number",
    "last_name",
    "first_name",
    "license_type",
    "license_status",
    "expiration_date",
    "city",
})


def ca_medical_board_config(**overrides: Any) -> ConnectorConfig:
    """Build the CA Medical Board (state_board_ca) ConnectorConfig.

    BULK_DOWNLOAD: one request per run, full dataset. Rate limit 1 req/s
    (courteous for a state government server). expected_min_records should be set
    to ~100 000 in production (CA has the largest physician population in the US).
    """
    params: dict[str, Any] = dict(
        source_id="state_board_ca",
        source_name="California Medical Board",
        source_category=SourceCategory.STATE_BOARD,
        integration_method=IntegrationMethod.BULK_DOWNLOAD,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (CA Medical Board state_board_ca)",
        rate_limit_per_sec=1.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class CaMedicalBoardConnector(SourceConnector):
    """California Medical Board bulk CSV adapter (state_board_ca).

    Downloads the DCA bulk CSV, parses it with csv.DictReader, and yields one
    dict per row. The CSV field names are normalized to snake_case to match the
    schema contract. C11 normalization (deferred) extracts the NPI from the raw
    record and converts dates to ISO 8601.

    The CSV header row names may vary across DCA releases; the _CSV_FIELD_MAP
    maps known DCA column names to the contract field names. Columns not in the
    map are passed through as-is (extra fields do not trigger drift detection).
    """

    contract = SchemaContract(
        required_fields=_CA_REQUIRED_FIELDS,
        field_types={f: str for f in _CA_REQUIRED_FIELDS},
    )

    # Maps DCA CSV header variants -> contract field names.
    # DCA has used slightly different column names across bulk file versions.
    _CSV_FIELD_MAP: dict[str, str] = {
        # Common DCA column name variants
        "License Number": "license_number",
        "LicenseNumber": "license_number",
        "LICENSENUM": "license_number",
        "Last Name": "last_name",
        "LastName": "last_name",
        "LNAME": "last_name",
        "First Name": "first_name",
        "FirstName": "first_name",
        "FNAME": "first_name",
        "License Type": "license_type",
        "LicenseType": "license_type",
        "LICTYPE": "license_type",
        "License Status": "license_status",
        "Status": "license_status",
        "STATUS": "license_status",
        "Expiration Date": "expiration_date",
        "ExpirationDate": "expiration_date",
        "EXP_DATE": "expiration_date",
        "City": "city",
        "CITY": "city",
    }

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        path: str = DEFAULT_PATH,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._path = path

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Download the bulk CSV and yield one dict per row."""
        resp = await self.request("GET", self._path)
        rows = self._parse_csv(resp)
        for row in rows:
            yield row

    def _parse_csv(self, resp: Any) -> list[dict[str, Any]]:
        """Parse CSV response body into a list of dicts with normalized field names."""
        try:
            text: str = resp.text
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: could not read response body: {exc}"
            ) from exc

        if not text or not text.strip():
            raise SourceUnavailableError(
                f"{self.source_id}: empty CSV response from CA Medical Board"
            )

        reader = csv.DictReader(io.StringIO(text))
        rows: list[dict[str, Any]] = []
        for raw_row in reader:
            # Normalize field names using the map; pass unknown columns through.
            normalized: dict[str, Any] = {}
            for col, val in raw_row.items():
                mapped = self._CSV_FIELD_MAP.get(col, col)
                normalized[mapped] = val
            rows.append(normalized)
        return rows
