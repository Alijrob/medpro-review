"""
oig_leie.py — OIG LEIE (List of Excluded Individuals/Entities) adapter
(source F2, component C10, Phase 2-B.2).

The LEIE is the authoritative federal exclusion list: a provider on it cannot
be paid by Medicare, Medicaid, or any other federal healthcare program. Checking
LEIE status is a required step in any credentialing-adjacent report. Absence on
LEIE is itself a high-value signal ("no active federal exclusion found").

Mode: **Bulk download** — the monthly LEIE exclusions CSV published by HHS OIG
at `https://oig.hhs.gov/exclusions/downloadables/LEIE.csv`. Each row is one
excluded individual or entity. The NPI column links to NPPES identity (F1) but
may be blank for pre-NPI-era exclusions (providers excluded before May 2008 who
were never assigned an NPI). The API spot-check (per-NPI real-time lookup at the
OIG exclusion search portal) is a deferred follow-on, consistent with building
the MVP-critical bulk path first (Entry 016).

Output is `RawRecord`s (one per LEIE row, pre-normalization). All field values are
strings — standard CSV semantics. Turning LEIE rows into typed exclusion signals
on a `CanonicalProviderProfile` is C11 (Normalization Layer, Phase 2-D).

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination. Nothing
here hits the network on import; tests drive it with a stubbed transport. Running
it against the live OIG endpoint is a deploy-time action behind that gate. F2 is
T1/L0 open-data (U.S. Government Work, public domain — no copyright restriction
on federal government data per 17 U.S.C. § 105).
"""
from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from typing import Any

from schema.v1.common import SourceCategory

from ..base import SourceConnector
from ..config import ConnectorConfig
from ..contract import SchemaContract
from ..errors import SourceUnavailableError
from ..models import IntegrationMethod

DEFAULT_BASE_URL = "https://oig.hhs.gov"
LEIE_CSV_PATH = "/exclusions/downloadables/LEIE.csv"

# LEIE CSV columns that must be present in any valid OIG exclusions file.
# OIG publishes the full column set as:
#   LASTNAME, FIRSTNAME, MIDNAME, BUSNAME, GENERAL, SPECIALTY, UPIN, NPI, DOB,
#   ADDRESS, CITY, STATE, ZIP, EXCDATE, REINDATE, WAIVERDATE, WAIVERSTATE, ACTION,
#   EXCLTYPE
# The SchemaContract guards the subset below — the fields that identity-link to
# NPPES (NPI), establish exclusion facts (EXCDATE, EXCLTYPE, ACTION), and locate
# the excluded party (ADDRESS, CITY, STATE, ZIP). Presence of MIDNAME, GENERAL,
# SPECIALTY, UPIN, REINDATE, WAIVERDATE, WAIVERSTATE is not guarded because their
# absence would not break any downstream normalization step. Guarding only the
# high-value columns keeps the contract a meaningful R6 drift alarm rather than a
# noisy "OIG added a column" alarm.
_LEIE_REQUIRED_FIELDS = frozenset({
    "LASTNAME",
    "FIRSTNAME",
    "BUSNAME",
    "NPI",
    "EXCDATE",
    "EXCLTYPE",
    "ACTION",
    "ADDRESS",
    "CITY",
    "STATE",
    "ZIP",
})


def oig_leie_config(**overrides: Any) -> ConnectorConfig:
    """Build the F2 ConnectorConfig (identity + operational defaults).

    The `expected_min_records` default is None (no threshold enforced). In
    production, set it to a value consistent with the LEIE's known size (~70 000
    active exclusions as of 2026) so that a drastically truncated download
    surfaces as FetchStatus.PARTIAL rather than a silent short run.
    Example: ``oig_leie_config(expected_min_records=60_000)``.
    """
    params: dict[str, Any] = dict(
        source_id="F2",
        source_name="OIG LEIE",
        source_category=SourceCategory.FEDERAL,
        integration_method=IntegrationMethod.BULK_DOWNLOAD,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (OIG LEIE F2)",
        # One bulk download per monthly refresh — no per-request rate cap needed.
        # A value of 1.0 is a courtesy floor; the OIG site is not rate-sensitive
        # for a single monthly download.
        rate_limit_per_sec=1.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class OigLeieConnector(SourceConnector):
    """OIG LEIE bulk-download adapter (F2).

    Downloads the monthly LEIE CSV from HHS OIG and yields one dict per
    exclusion row. `run()` (inherited) wraps each row in a provenance-hashed
    `RawRecord`, validates it against `contract`, and emits a `SourceHealthRecord`
    for the Source Health Monitor (C24).

    All yielded values are strings (standard CSV semantics). NPI may be an empty
    string for pre-NPI-era exclusions; downstream callers should treat an empty
    NPI as "NPI not recorded," not "no NPI exists."

    Deferred: API spot-check mode (per-NPI real-time lookup against the OIG
    exclusion search API). For MVP, the bulk CSV is the complete data surface and
    the per-NPI lookup is performed in-memory or in-DB after the bulk ingest.
    """

    contract = SchemaContract(
        required_fields=_LEIE_REQUIRED_FIELDS,
        field_types={
            "LASTNAME": str,
            "FIRSTNAME": str,
            "BUSNAME": str,
            "NPI": str,
            "EXCDATE": str,
            "EXCLTYPE": str,
            "ACTION": str,
            "STATE": str,
        },
    )

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Download the LEIE CSV and yield one dict per exclusion row."""
        resp = await self.request("GET", LEIE_CSV_PATH)
        text = self._parse_csv_text(resp)
        try:
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                yield dict(row)
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: failed to iterate LEIE CSV rows: {exc}"
            ) from exc

    def _parse_csv_text(self, resp: Any) -> str:
        """Extract non-empty text from the response or raise SourceUnavailableError."""
        try:
            text = resp.text
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: failed to read LEIE response text: {exc}"
            ) from exc
        if not isinstance(text, str) or not text.strip():
            raise SourceUnavailableError(
                f"{self.source_id}: empty or non-text LEIE response"
            )
        return text
