"""
normalizers/sources -- Concrete source normalizers for Phase 2-D (C11).

Importing this package registers all 8 P1 normalizers in the registry
(DECISIONS.md Entry 025). The registration order does not matter.

Normalizers registered by this module:
  F1  NppesNormalizer          -- NPPES NPI Registry
  F2  OigLeieNormalizer        -- OIG LEIE Exclusions
  F3  SamGovNormalizer         -- SAM.gov Exclusions
  F4  CmsCareCompareNormalizer -- CMS Care Compare (Doctors and Clinicians)
  I1  MedicareEnrollmentNormalizer -- CMS Medicare Enrollment + Opt-Out
  I2  MedicaidEnrollmentNormalizer -- CMS Medicaid Enrollment
  A1  PubmedNormalizer         -- PubMed / NCBI Entrez
  A2  ClinicalTrialsNormalizer -- ClinicalTrials.gov

NOTE: I4 (NPPES Specialty Crosswalk) is a pure helper module, not a
SourceConnector -- it has no normalizer. Use get_specialty_group() from
normalizers.sources.f1_nppes directly (called by C13).

LEGAL GATE: normalizers transform raw data but do not ingest from live sources.
No network I/O occurs on import. Live ingestion is governed by the Phase 0
FCRA determination.
"""
from .a1_pubmed import PubmedNormalizer as PubmedNormalizer
from .a2_clinical_trials import ClinicalTrialsNormalizer as ClinicalTrialsNormalizer
from .f1_nppes import NppesNormalizer as NppesNormalizer
from .f1_nppes import get_specialty_group as get_specialty_group
from .f2_oig_leie import OigLeieNormalizer as OigLeieNormalizer
from .f3_sam_gov import SamGovNormalizer as SamGovNormalizer
from .f4_cms_care_compare import CmsCareCompareNormalizer as CmsCareCompareNormalizer
from .i1_medicare_enrollment import MedicareEnrollmentNormalizer as MedicareEnrollmentNormalizer
from .i2_medicaid_enrollment import MedicaidEnrollmentNormalizer as MedicaidEnrollmentNormalizer
