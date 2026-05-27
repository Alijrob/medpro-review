"""
connectors.sources.review_platforms -- Phase 3-E review platform adapters (R1, R2).

Both adapters require API keys before live ingest. Each raises AuthenticationError on
fetch_raw() if api_key is absent. Tested stub-only.

ToS constraints:
    Google Places: paid Maps Platform account; per-request pricing; caching TTL limits;
                   Google attribution required on display. See tos-matrix.md row R1.
    Yelp Fusion:   Yelp Developer account; 1000-result hard cap per search; 24-hour cache
                   limit; Yelp branding required on display. See tos-matrix.md row R2.

LICENSE GATE: live ingest additionally requires the Phase 0 FCRA determination.
See docs/reference/tos-matrix.md rows R1-R2 and source-priority.md.

Phase 3-E review platform batch:
    R1  Google Places Provider Reviews  -- review_platforms.google_places  (T2, API key required)
    R2  Yelp Fusion Provider Reviews    -- review_platforms.yelp            (T2, API key required)
"""
from .google_places import GooglePlacesConnector, google_places_config
from .yelp import YelpConnector, yelp_config

__all__ = [
    # R1 -- Google Places (T2, paid Maps Platform API key)
    "GooglePlacesConnector",
    "google_places_config",
    # R2 -- Yelp Fusion (T2, Yelp Developer API key)
    "YelpConnector",
    "yelp_config",
]
