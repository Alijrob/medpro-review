"""
connectors.sources.court_records -- P2/P3 court record adapters (Phase 3-C).

Builds on the C9 connector framework (connectors.base.SourceConnector). These
adapters cover federal court records (C1-C2 in the source priority matrix) and
the three highest-physician-population state court systems (NY, TX, FL) as
early P3 exploration adapters.

Court record adapters differ from state board adapters in one key way: they
are lookup-by-name rather than full-dump. The party_name (or last_name/
first_name for PACER) is injected at the connector level as a constructor arg.
This matches the on-demand per-provider report pipeline rather than the batch
ingest pattern used for state board license data.

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination. No
adapter performs network I/O on import; all tests use stubbed transports.
Running an adapter against its live endpoint is a deploy-time action behind
the legal gate. See docs/reference/tos-matrix.md for per-source legal status.

Source ID namespace: court_* to avoid collision with state_board_* and federal
F/I/A source IDs.

Phase 3-C court record batch:
    C2  CourtListener / RECAP Archive (federal, cursor pagination)
        -- court_records.court_listener  (built, 3-C)
    C1  PACER Case Locator (federal, page-number)
        -- court_records.pacer           (built, 3-C)
    TX  Texas Courts Search (state, offset/limit)
        -- court_records.tx_courts       (built, 3-C)
    FL  Florida eCourts (state, offset/limit)
        -- court_records.fl_courts       (built, 3-C)
    NY  New York eCourts WebCivil (state, page-number)
        -- court_records.ny_courts       (built, 3-C)
"""
from .court_listener import CourtListenerConnector, court_listener_config
from .fl_courts import FlCourtsConnector, fl_courts_config
from .ny_courts import NyCourtsConnector, ny_courts_config
from .pacer import PacerConnector, pacer_config
from .tx_courts import TxCourtsConnector, tx_courts_config

__all__ = [
    # C2 -- CourtListener / RECAP Archive
    "CourtListenerConnector",
    "court_listener_config",
    # C1 -- PACER Case Locator
    "PacerConnector",
    "pacer_config",
    # TX -- Texas Courts Search
    "TxCourtsConnector",
    "tx_courts_config",
    # FL -- Florida eCourts
    "FlCourtsConnector",
    "fl_courts_config",
    # NY -- New York eCourts WebCivil
    "NyCourtsConnector",
    "ny_courts_config",
]
