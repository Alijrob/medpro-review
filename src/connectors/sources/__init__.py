"""
connectors.sources -- concrete source adapters (component C10, Phase 2-B+).

Each adapter subclasses `connectors.SourceConnector`, declares a `SchemaContract`,
and is exercised by the reusable `assert_connector_contract` harness with a stubbed
transport. The framework gives every adapter throttling, retry/backoff, HTTP->error
classification, provenance hashing, and a SourceHealthRecord for free.

LEGAL GATE: these adapters *describe* how to fetch real source data, but live
ingestion is governed by the Phase 0 FCRA determination. The code here performs no
network I/O on import and is tested only against stubbed transports; running an
adapter against its live endpoint is a deploy-time action behind that gate.

Phase 2-B federal batch (T1/L0 open-data, see docs/reference/source-priority.md):
    F1  NPPES / NPI Registry   -- connectors.sources.nppes                    (built, 2-B.1)
    F2  OIG LEIE               -- connectors.sources.oig_leie                 (built, 2-B.2)
    F3  SAM.gov Exclusions     -- connectors.sources.sam_gov                  (built, 2-B.3)
    F4  CMS Care Compare       -- connectors.sources.cms_care_compare         (built, 2-B.4)
    I1  CMS Medicare Enrollment -- connectors.sources.cms_medicare_enrollment (built, 2-B.5)
"""
from .cms_care_compare import CmsCareCompareConnector, cms_care_compare_config
from .cms_medicare_enrollment import (
    CmsMedicareEnrollmentConnector,
    cms_medicare_enrollment_config,
)
from .nppes import NppesConnector, NppesQuery, nppes_config
from .oig_leie import OigLeieConnector, oig_leie_config
from .sam_gov import SamGovConnector, sam_gov_config

__all__ = [
    "NppesConnector",
    "NppesQuery",
    "nppes_config",
    "OigLeieConnector",
    "oig_leie_config",
    "SamGovConnector",
    "sam_gov_config",
    "CmsCareCompareConnector",
    "cms_care_compare_config",
    "CmsMedicareEnrollmentConnector",
    "cms_medicare_enrollment_config",
]
