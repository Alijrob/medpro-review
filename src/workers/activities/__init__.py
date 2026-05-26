"""
workers.activities -- Temporal activity functions for the per-NPI provider pipeline.

Phase 2-H activities (C15 basic + C17 basic):
    fetch_source_activity        -- C10 (connector run per source)
    normalize_records_activity   -- C11 (normalizer)
    resolve_identity_activity    -- C12 (identity resolver)
    link_and_merge_activity      -- C13 (entity linker)
    index_profile_activity       -- C14 (search indexer)
    generate_report_activity     -- C17 (report builder + renderer)

Phase 2-I activity:
    persist_report_activity      -- C18 (Aurora report persistence)

Activities are plain async (or sync) Python functions decorated with @activity.defn.
They can be called directly in tests without a running Temporal server.
"""
from .fetch import fetch_source_activity
from .generate_report import generate_report_activity
from .index import index_profile_activity
from .link import link_and_merge_activity
from .normalize import normalize_records_activity
from .persist_report import persist_report_activity
from .resolve import resolve_identity_activity

__all__ = [
    "fetch_source_activity",
    "normalize_records_activity",
    "resolve_identity_activity",
    "link_and_merge_activity",
    "index_profile_activity",
    "generate_report_activity",
    "persist_report_activity",
]
