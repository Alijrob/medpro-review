"""
connectors.sources — concrete source adapters (component C10, Phase 2-B+).

Each adapter subclasses `connectors.SourceConnector`, declares a `SchemaContract`,
and is exercised by the reusable `assert_connector_contract` harness with a stubbed
transport. The framework gives every adapter throttling, retry/backoff, HTTP→error
classification, provenance hashing, and a SourceHealthRecord for free.

LEGAL GATE: these adapters *describe* how to fetch real source data, but live
ingestion is governed by the Phase 0 FCRA determination. The code here performs no
network I/O on import and is tested only against stubbed transports; running an
adapter against its live endpoint is a deploy-time action behind that gate.

Phase 2-B federal batch (T1/L0 open-data, see docs/reference/source-priority.md):
    F1  NPPES / NPI Registry   — connectors.sources.nppes   (built)
    F2  OIG LEIE               — pending (2-B.2)
    F3  SAM.gov Exclusions     — pending (2-B.3)
"""
from .nppes import NppesConnector, NppesQuery, nppes_config

__all__ = ["NppesConnector", "NppesQuery", "nppes_config"]
