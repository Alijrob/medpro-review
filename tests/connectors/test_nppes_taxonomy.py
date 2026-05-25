"""
test_nppes_taxonomy.py -- NPPES taxonomy crosswalk (I4, Phase 2-B.7) tests.

No network I/O, no SourceConnector -- pure unit tests on the crosswalk table
and the two helper functions.

Test coverage:
  - crosswalk_taxonomy_code: known physician codes, known non-physician codes,
    unknown codes, empty string, case normalization
  - infer_specialty_group: primary flag preferred, fallback to non-primary,
    multiple taxonomies with primary, all-unknown codes, empty list
  - Crosswalk coverage: major specialty groups are represented in the table

Run:
    PYTHONPATH=src pytest tests/connectors/test_nppes_taxonomy.py -v
"""
from __future__ import annotations

import pytest

from connectors.sources.nppes_taxonomy import (
    TAXONOMY_CROSSWALK,
    crosswalk_taxonomy_code,
    infer_specialty_group,
)


# ---------------------------------------------------------------------------
class TestCrosswalkTaxonomyCode:
    def test_internal_medicine_code_maps_correctly(self):
        assert crosswalk_taxonomy_code("207R00000X") == "Internal Medicine"

    def test_cardiology_subspecialty_maps_correctly(self):
        assert crosswalk_taxonomy_code("207RC0000X") == "Cardiology"

    def test_family_medicine_maps_correctly(self):
        assert crosswalk_taxonomy_code("207Q00000X") == "Family Medicine"

    def test_psychiatry_maps_correctly(self):
        assert crosswalk_taxonomy_code("2084P0800X") == "Psychiatry"

    def test_neurology_maps_correctly(self):
        assert crosswalk_taxonomy_code("2084N0400X") == "Neurology"

    def test_nurse_practitioner_maps_correctly(self):
        assert crosswalk_taxonomy_code("363L00000X") == "Nurse Practitioner"

    def test_physician_assistant_maps_correctly(self):
        assert crosswalk_taxonomy_code("363A00000X") == "Physician Assistant"

    def test_radiology_maps_correctly(self):
        assert crosswalk_taxonomy_code("2085R0001X") == "Radiology"

    def test_pediatrics_maps_correctly(self):
        assert crosswalk_taxonomy_code("208000000X") == "Pediatrics"

    def test_unknown_code_returns_none(self):
        assert crosswalk_taxonomy_code("999Z99999X") is None

    def test_empty_string_returns_none(self):
        assert crosswalk_taxonomy_code("") is None

    def test_lookup_is_case_insensitive(self):
        # Codes are uppercase in NUCC; lower-case input should still map.
        assert crosswalk_taxonomy_code("207r00000x") == "Internal Medicine"

    def test_mixed_case_code_maps_correctly(self):
        assert crosswalk_taxonomy_code("207Q00000x") == "Family Medicine"

    def test_surgery_general_maps_correctly(self):
        assert crosswalk_taxonomy_code("208600000X") == "Surgery"

    def test_vascular_surgery_subspecialty_maps_correctly(self):
        assert crosswalk_taxonomy_code("2086S0129X") == "Vascular Surgery"

    def test_orthopedic_surgery_maps_correctly(self):
        assert crosswalk_taxonomy_code("207X00000X") == "Orthopedic Surgery"

    def test_pathology_maps_correctly(self):
        assert crosswalk_taxonomy_code("207Z00000X") == "Pathology"

    def test_chiropractic_maps_correctly(self):
        assert crosswalk_taxonomy_code("111N00000X") == "Chiropractic"

    def test_dentistry_maps_correctly(self):
        assert crosswalk_taxonomy_code("122300000X") == "Dentistry"


# ---------------------------------------------------------------------------
class TestInferSpecialtyGroup:
    def test_primary_taxonomy_is_preferred(self):
        taxonomies = [
            {"code": "207Q00000X", "desc": "Family Medicine", "primary": True},
            {"code": "207R00000X", "desc": "Internal Medicine", "primary": False},
        ]
        assert infer_specialty_group(taxonomies) == "Family Medicine"

    def test_non_primary_used_when_primary_code_is_unknown(self):
        taxonomies = [
            {"code": "999Z99999X", "desc": "Unknown", "primary": True},
            {"code": "207RC0000X", "desc": "Cardiology", "primary": False},
        ]
        assert infer_specialty_group(taxonomies) == "Cardiology"

    def test_first_entry_used_when_no_primary_flag(self):
        # Neither has primary=True; first in order should be returned.
        taxonomies = [
            {"code": "207W00000X", "desc": "Ophthalmology"},
            {"code": "207X00000X", "desc": "Orthopedic Surgery"},
        ]
        assert infer_specialty_group(taxonomies) == "Ophthalmology"

    def test_empty_list_returns_none(self):
        assert infer_specialty_group([]) is None

    def test_all_unknown_codes_returns_none(self):
        taxonomies = [
            {"code": "999A99999X", "primary": True},
            {"code": "999B99999X", "primary": False},
        ]
        assert infer_specialty_group(taxonomies) is None

    def test_single_taxonomy_with_known_code(self):
        taxonomies = [{"code": "2084P0800X", "desc": "Psychiatry", "primary": True}]
        assert infer_specialty_group(taxonomies) == "Psychiatry"

    def test_primary_false_explicitly_falls_back_in_order(self):
        # Primary is False for first, second is also False; first one maps.
        taxonomies = [
            {"code": "207Y00000X", "desc": "Otolaryngology", "primary": False},
            {"code": "208600000X", "desc": "Surgery", "primary": False},
        ]
        # Both are non-primary; first in list order should be returned.
        assert infer_specialty_group(taxonomies) == "Otolaryngology"

    def test_missing_code_key_is_skipped_gracefully(self):
        taxonomies = [
            {"desc": "No code field here", "primary": True},
            {"code": "207V00000X", "desc": "Obstetrics & Gynecology", "primary": False},
        ]
        assert infer_specialty_group(taxonomies) == "Obstetrics & Gynecology"


# ---------------------------------------------------------------------------
class TestCrosswalkCoverage:
    """Sanity checks that major specialty groups are represented in the table."""

    def test_crosswalk_is_not_empty(self):
        assert len(TAXONOMY_CROSSWALK) > 50

    def test_all_keys_are_strings(self):
        assert all(isinstance(k, str) for k in TAXONOMY_CROSSWALK)

    def test_all_values_are_non_empty_strings(self):
        assert all(isinstance(v, str) and v for v in TAXONOMY_CROSSWALK.values())

    def test_major_specialty_groups_are_covered(self):
        groups = set(TAXONOMY_CROSSWALK.values())
        required = {
            "Internal Medicine",
            "Family Medicine",
            "Cardiology",
            "Gastroenterology",
            "Pediatrics",
            "Psychiatry",
            "Neurology",
            "Surgery",
            "Orthopedic Surgery",
            "Radiology",
            "Pathology",
            "Anesthesiology",
            "Obstetrics & Gynecology",
            "Nurse Practitioner",
            "Physician Assistant",
        }
        missing = required - groups
        assert not missing, f"Missing specialty groups in crosswalk: {missing}"
