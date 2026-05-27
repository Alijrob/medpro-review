"""
test_pii.py -- Tests for ai.pii.scrub_pii (Phase 4-H).

Run:
    PYTHONPATH=src:. pytest tests/ai/test_pii.py -v
"""
from __future__ import annotations

from ai.pii import scrub_pii


class TestScrubPII:
    def test_removes_home_address(self):
        data = {"npi": "123", "home_address": "123 Main St"}
        result = scrub_pii(data)
        assert "home_address" not in result
        assert result["npi"] == "123"

    def test_removes_personal_phone(self):
        data = {"npi": "123", "personal_phone": "555-0100"}
        result = scrub_pii(data)
        assert "personal_phone" not in result

    def test_removes_personal_email(self):
        data = {"npi": "123", "personal_email": "dr@home.com"}
        result = scrub_pii(data)
        assert "personal_email" not in result

    def test_removes_dob(self):
        data = {"npi": "123", "dob": "1975-03-15"}
        result = scrub_pii(data)
        assert "dob" not in result

    def test_removes_ssn(self):
        data = {"npi": "123", "ssn": "123-45-6789"}
        result = scrub_pii(data)
        assert "ssn" not in result

    def test_preserves_non_pii_fields(self):
        data = {
            "npi": "1234567890",
            "name": "Dr. Smith",
            "specialty": "Cardiology",
            "licenses": [{"state": "MA", "status": "active"}],
        }
        result = scrub_pii(data)
        assert result["npi"] == "1234567890"
        assert result["name"] == "Dr. Smith"
        assert result["specialty"] == "Cardiology"
        assert len(result["licenses"]) == 1

    def test_does_not_mutate_original(self):
        original = {"npi": "123", "ssn": "999-99-9999", "name": "Dr. X"}
        _ = scrub_pii(original)
        assert "ssn" in original  # original unchanged

    def test_scrubs_nested_dicts(self):
        data = {
            "npi": "123",
            "identity": {
                "name": "Dr. Smith",
                "dob": "1970-01-01",
                "personal_phone": "555-0100",
            },
        }
        result = scrub_pii(data)
        assert "dob" not in result["identity"]
        assert "personal_phone" not in result["identity"]
        assert result["identity"]["name"] == "Dr. Smith"

    def test_scrubs_pii_in_list_of_dicts(self):
        data = {
            "records": [
                {"source": "NPI", "home_address": "REDACTED"},
                {"source": "NPPES", "specialty": "Surgery"},
            ]
        }
        result = scrub_pii(data)
        assert "home_address" not in result["records"][0]
        assert result["records"][1]["specialty"] == "Surgery"

    def test_handles_empty_dict(self):
        assert scrub_pii({}) == {}

    def test_handles_scalar(self):
        assert scrub_pii("hello") == "hello"
        assert scrub_pii(42) == 42
        assert scrub_pii(None) is None

    def test_handles_list_of_scalars(self):
        data = ["a", "b", "c"]
        result = scrub_pii(data)
        assert result == ["a", "b", "c"]

    def test_all_pii_fields_removed_at_once(self):
        data = {
            "npi": "1234567890",
            "home_address": "1 Private Rd",
            "personal_phone": "555-0000",
            "personal_email": "private@home.com",
            "dob": "1980-06-15",
            "ssn": "000-00-0000",
            "specialty": "Neurology",
        }
        result = scrub_pii(data)
        for pii_key in ("home_address", "personal_phone", "personal_email", "dob", "ssn"):
            assert pii_key not in result
        assert result["npi"] == "1234567890"
        assert result["specialty"] == "Neurology"
