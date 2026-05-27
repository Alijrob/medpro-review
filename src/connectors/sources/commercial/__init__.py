"""
connectors.sources.commercial -- Phase 3-D commercial data adapters (D1, D2, D3).

All three adapters require signed data license agreements before live ingest. Each
raises AuthenticationError on fetch_raw() if api_key is absent. Tested stub-only.

LICENSE GATE: live ingest additionally requires the Phase 0 FCRA determination.
See docs/reference/tos-matrix.md rows D1-D3 and source-priority.md sections 4.1-4.2.

Phase 3-D commercial batch:
    D1  Ribbon Health Provider Directory    -- commercial.ribbon_health  (T3, contract required)
    D2  Healthgrades Provider Profiles      -- commercial.healthgrades   (T4, license required)
    D3  Vitals Provider Profiles (WebMD)    -- commercial.vitals         (T4, license required)
"""
from .healthgrades import HealthgradesConnector, healthgrades_config
from .ribbon_health import RibbonHealthConnector, ribbon_health_config
from .vitals import VitalsConnector, vitals_config

__all__ = [
    # D1 -- Ribbon Health (T3, contract required)
    "RibbonHealthConnector",
    "ribbon_health_config",
    # D2 -- Healthgrades (T4, license required)
    "HealthgradesConnector",
    "healthgrades_config",
    # D3 -- Vitals / WebMD Health Corp. (T4, license required)
    "VitalsConnector",
    "vitals_config",
]
