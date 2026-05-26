"""
test_store.py -- Unit tests for IdentityStore (Phase 2-E, C12).

Validates CRUD operations and boundary conditions for the in-memory bundle store.
"""
import pytest

from identity.store import IdentityStore
from schema.v1.common import EntityType, Gender, ProviderName
from schema.v1.identity import UnifiedIdBundle


def _bundle(npi: str, first: str = "Alice", last: str = "Smith") -> UnifiedIdBundle:
    return UnifiedIdBundle(
        primary_npi=npi,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first=first, last=last),
        identity_confidence=0.95,
    )


# ---------------------------------------------------------------------------
# Basic operations
# ---------------------------------------------------------------------------

def test_empty_store_get_returns_none():
    store = IdentityStore()
    assert store.get("1234567890") is None


def test_put_and_get_returns_bundle():
    store = IdentityStore()
    b = _bundle("1234567890")
    store.put(b)
    result = store.get("1234567890")
    assert result is not None
    assert result.primary_npi == "1234567890"


def test_put_overwrites_existing():
    store = IdentityStore()
    b1 = _bundle("1234567890", first="Alice")
    b2 = _bundle("1234567890", first="Updated")
    store.put(b1)
    store.put(b2)
    assert store.get("1234567890").primary_name.first == "Updated"


def test_get_returns_exact_object():
    store = IdentityStore()
    b = _bundle("1234567890")
    store.put(b)
    assert store.get("1234567890") is b


def test_different_npis_stored_independently():
    store = IdentityStore()
    b1 = _bundle("1234567890")
    b2 = _bundle("0987654321")
    store.put(b1)
    store.put(b2)
    assert store.get("1234567890").primary_npi == "1234567890"
    assert store.get("0987654321").primary_npi == "0987654321"


# ---------------------------------------------------------------------------
# get_all / list_npis / len
# ---------------------------------------------------------------------------

def test_get_all_empty():
    store = IdentityStore()
    assert store.get_all() == []


def test_get_all_returns_all_bundles():
    store = IdentityStore()
    b1 = _bundle("1234567890")
    b2 = _bundle("0987654321")
    store.put(b1)
    store.put(b2)
    all_bundles = store.get_all()
    assert len(all_bundles) == 2
    npis = {b.primary_npi for b in all_bundles}
    assert npis == {"1234567890", "0987654321"}


def test_list_npis():
    store = IdentityStore()
    store.put(_bundle("1234567890"))
    store.put(_bundle("0987654321"))
    npis = store.list_npis()
    assert set(npis) == {"1234567890", "0987654321"}


def test_len():
    store = IdentityStore()
    assert len(store) == 0
    store.put(_bundle("1234567890"))
    assert len(store) == 1
    store.put(_bundle("0987654321"))
    assert len(store) == 2


def test_contains():
    store = IdentityStore()
    store.put(_bundle("1234567890"))
    assert "1234567890" in store
    assert "0000000000" not in store


# ---------------------------------------------------------------------------
# remove / clear
# ---------------------------------------------------------------------------

def test_remove_existing():
    store = IdentityStore()
    store.put(_bundle("1234567890"))
    store.remove("1234567890")
    assert store.get("1234567890") is None
    assert len(store) == 0


def test_remove_nonexistent_is_noop():
    store = IdentityStore()
    store.remove("9999999999")  # should not raise


def test_clear_empties_store():
    store = IdentityStore()
    store.put(_bundle("1234567890"))
    store.put(_bundle("0987654321"))
    store.clear()
    assert len(store) == 0
    assert store.get_all() == []
