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
    F1  NPPES / NPI Registry     -- connectors.sources.nppes                     (built, 2-B.1)
    F2  OIG LEIE                 -- connectors.sources.oig_leie                  (built, 2-B.2)
    F3  SAM.gov Exclusions       -- connectors.sources.sam_gov                   (built, 2-B.3)
    F4  CMS Care Compare         -- connectors.sources.cms_care_compare          (built, 2-B.4)
    I1  CMS Medicare Enrollment  -- connectors.sources.cms_medicare_enrollment   (built, 2-B.5)
    I2  CMS Medicaid Enrollment  -- connectors.sources.cms_medicaid_enrollment   (built, 2-B.6)
    I4  NPPES Specialty Crosswalk -- connectors.sources.nppes_taxonomy           (built, 2-B.7)
    A1  PubMed / NCBI Entrez     -- connectors.sources.pubmed                    (built, 2-B.8)
    A2  ClinicalTrials.gov       -- connectors.sources.clinical_trials           (built, 2-B.9)

Phase 3-A state board batch (P2 sources, see docs/reference/source-priority.md):
    S1  CA Medical Board         -- connectors.sources.state_boards.ca_medical_board (built, 3-A)
    S2  NY NYSED OP              -- connectors.sources.state_boards.ny_op_nysed      (built, 3-A)
    S3  TX Medical Board         -- connectors.sources.state_boards.tx_medical_board (built, 3-A)
    S4  FL DOH FDBPR             -- connectors.sources.state_boards.fl_doh           (built, 3-A)
    S5  IL IDFPR                 -- connectors.sources.state_boards.il_idfpr         (built, 3-A)

Phase 3-B state board batch (P2 sources):
    S6  GA Composite Medical Board -- connectors.sources.state_boards.ga_composite_medical_board (built, 3-B)
    S7  PA State Medical Board     -- connectors.sources.state_boards.pa_medical_board           (built, 3-B)
    S8  OH State Medical Board     -- connectors.sources.state_boards.oh_state_medical_board     (built, 3-B)
    S9  MI LARA BPL                -- connectors.sources.state_boards.mi_lara                    (built, 3-B)
    S10 NC Medical Board           -- connectors.sources.state_boards.nc_medical_board           (built, 3-B)

Phase 3-C court record batch (C1-C2 P2 + state courts early P3 exploration):
    C2  CourtListener / RECAP Archive -- connectors.sources.court_records.court_listener (built, 3-C)
    C1  PACER Case Locator            -- connectors.sources.court_records.pacer          (built, 3-C)
    TX  Texas Courts Search           -- connectors.sources.court_records.tx_courts      (built, 3-C)
    FL  Florida eCourts               -- connectors.sources.court_records.fl_courts      (built, 3-C)
    NY  New York eCourts WebCivil     -- connectors.sources.court_records.ny_courts      (built, 3-C)
"""
from .clinical_trials import ClinicalTrialsConnector, clinical_trials_config
from .court_records import (
    CourtListenerConnector,
    court_listener_config,
    FlCourtsConnector,
    fl_courts_config,
    NyCourtsConnector,
    ny_courts_config,
    PacerConnector,
    pacer_config,
    TxCourtsConnector,
    tx_courts_config,
)
from .state_boards import (
    CaMedicalBoardConnector,
    ca_medical_board_config,
    FlDohConnector,
    fl_doh_config,
    IlIdfprConnector,
    il_idfpr_config,
    NyMedicalBoardConnector,
    ny_op_nysed_config,
    TxMedicalBoardConnector,
    tx_medical_board_config,
)
from .cms_care_compare import CmsCareCompareConnector, cms_care_compare_config
from .cms_medicaid_enrollment import (
    CmsMedicaidEnrollmentConnector,
    cms_medicaid_enrollment_config,
)
from .cms_medicare_enrollment import (
    CmsMedicareEnrollmentConnector,
    cms_medicare_enrollment_config,
)
from .nppes import NppesConnector, NppesQuery, nppes_config
from .nppes_taxonomy import TAXONOMY_CROSSWALK, crosswalk_taxonomy_code, infer_specialty_group
from .oig_leie import OigLeieConnector, oig_leie_config
from .pubmed import PubmedConnector, pubmed_config
from .sam_gov import SamGovConnector, sam_gov_config

__all__ = [
    # F1 -- NPPES
    "NppesConnector",
    "NppesQuery",
    "nppes_config",
    # I4 -- NPPES Taxonomy Crosswalk (derived signal, no connector)
    "TAXONOMY_CROSSWALK",
    "crosswalk_taxonomy_code",
    "infer_specialty_group",
    # F2 -- OIG LEIE
    "OigLeieConnector",
    "oig_leie_config",
    # F3 -- SAM.gov Exclusions
    "SamGovConnector",
    "sam_gov_config",
    # F4 -- CMS Care Compare
    "CmsCareCompareConnector",
    "cms_care_compare_config",
    # I1 -- CMS Medicare Enrollment
    "CmsMedicareEnrollmentConnector",
    "cms_medicare_enrollment_config",
    # I2 -- CMS Medicaid Enrollment
    "CmsMedicaidEnrollmentConnector",
    "cms_medicaid_enrollment_config",
    # A1 -- PubMed / NCBI Entrez
    "PubmedConnector",
    "pubmed_config",
    # A2 -- ClinicalTrials.gov
    "ClinicalTrialsConnector",
    "clinical_trials_config",
    # S1 -- CA Medical Board
    "CaMedicalBoardConnector",
    "ca_medical_board_config",
    # S2 -- NY NYSED Office of Professions
    "NyMedicalBoardConnector",
    "ny_op_nysed_config",
    # S3 -- Texas Medical Board
    "TxMedicalBoardConnector",
    "tx_medical_board_config",
    # S4 -- Florida DOH FDBPR
    "FlDohConnector",
    "fl_doh_config",
    # S5 -- Illinois IDFPR
    "IlIdfprConnector",
    "il_idfpr_config",
    # Phase 3-B -- State Boards (GA/PA/OH/MI/NC) -- exported via state_boards package
    # Phase 3-C -- Court Records
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
