"""
test_confidence.py -- Unit tests for ConfidenceScorer (Phase 2-E, C12).

Validates the source-tier confidence model described in DECISIONS.md Entry 026.
All tests are synchronous; no network, no DB.
"""
import pytest

from identity.confidence import ConfidenceScorer
from identity.config import IdentitySettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def scorer(
    *,
    human_review_threshold: float = 0.850,
    f1_base: float = 0.950,
    boost: float = 0.015,
    partial: float = 0.005,
    max_conf: float = 0.999,
    no_f1_max: float = 0.750,
) -> ConfidenceScorer:
    settings = IdentitySettings(
        f1_base_confidence=f1_base,
        npi_corroborating_boost=boost,
        npi_partial_boost=partial,
        max_confidence=max_conf,
        no_f1_max_confidence=no_f1_max,
        human_review_threshold=human_review_threshold,
    )
    return ConfidenceScorer(settings)


# ---------------------------------------------------------------------------
# F1-present scoring
# ---------------------------------------------------------------------------

def test_f1_alone():
    """F1 alone gives the base confidence (0.950)."""
    s = scorer()
    assert s.score(["F1"]) == pytest.approx(0.950)


def test_f1_plus_f4():
    """F1 + F4 (NPI-corroborating) adds one boost."""
    s = scorer()
    assert s.score(["F1", "F4"]) == pytest.approx(0.965)


def test_f1_plus_i1():
    """F1 + I1 (NPI-corroborating) adds one boost."""
    s = scorer()
    assert s.score(["F1", "I1"]) == pytest.approx(0.965)


def test_f1_plus_f4_i1_reaches_target():
    """F1 + F4 + I1 reaches the >0.98 architecture target."""
    s = scorer()
    conf = s.score(["F1", "F4", "I1"])
    assert conf == pytest.approx(0.980)
    assert conf >= 0.980


def test_f1_plus_f4_i1_i2_exceeds_target():
    """F1 + F4 + I1 + I2 (three corroborating) exceeds the target."""
    s = scorer()
    conf = s.score(["F1", "F4", "I1", "I2"])
    assert conf == pytest.approx(0.995)
    assert conf >= 0.980


def test_f1_plus_f2_partial_boost():
    """F2 gives only the partial boost (NPI from raw vs entity_npi is ambiguous)."""
    s = scorer()
    assert s.score(["F1", "F2"]) == pytest.approx(0.955)


def test_f1_plus_f2_f4_i1():
    """F1 + F2 (partial) + F4 + I1 combines all boosts."""
    s = scorer()
    expected = 0.950 + 0.015 + 0.015 + 0.005  # F4 + I1 corroborating + F2 partial
    assert s.score(["F1", "F2", "F4", "I1"]) == pytest.approx(expected)


def test_f1_plus_caller_npi_sources_no_boost():
    """F3, A1, A2 (caller-supplied NPI) do not raise confidence."""
    s = scorer()
    # F3, A1, A2 together: no boost over F1 alone
    assert s.score(["F1", "F3"]) == pytest.approx(0.950)
    assert s.score(["F1", "A1"]) == pytest.approx(0.950)
    assert s.score(["F1", "A2"]) == pytest.approx(0.950)
    assert s.score(["F1", "F3", "A1", "A2"]) == pytest.approx(0.950)


def test_all_p1_sources():
    """All 8 P1 sources together gives near-max confidence."""
    s = scorer()
    sources = ["F1", "F2", "F3", "F4", "I1", "I2", "A1", "A2"]
    conf = s.score(sources)
    # F4 + I1 + I2 = 3 * 0.015 = 0.045; F2 = 0.005; total = 0.950 + 0.050 = 1.000 -> capped 0.999
    assert conf == pytest.approx(0.999)


def test_confidence_capped_at_max():
    """Confidence never exceeds max_confidence regardless of number of sources."""
    s = scorer(max_conf=0.999)
    conf = s.score(["F1", "F4", "I1", "I2", "F2"])
    assert conf <= 0.999


# ---------------------------------------------------------------------------
# F1-absent scoring
# ---------------------------------------------------------------------------

def test_no_f1_single_source():
    """Without F1, a single source gives a small incremental score."""
    s = scorer()
    conf = s.score(["F2"])
    assert conf < s._s.human_review_threshold
    assert conf <= 0.750


def test_no_f1_multiple_sources():
    """Without F1, multiple sources accumulate but stay capped at no_f1_max."""
    s = scorer()
    conf = s.score(["F2", "F4", "I1", "I2"])
    assert conf <= 0.750


def test_no_f1_requires_human_review():
    """All bundles without F1 should require human review."""
    s = scorer(human_review_threshold=0.850)
    conf = s.score(["F4", "I1"])
    assert s.requires_human_review(conf)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_duplicate_sources_not_double_counted():
    """Passing the same source twice must not raise confidence beyond once."""
    s = scorer()
    once = s.score(["F1", "F4"])
    twice = s.score(["F1", "F4", "F4"])
    assert once == pytest.approx(twice)


def test_empty_sources():
    """Empty source list returns a near-zero score without F1."""
    s = scorer()
    conf = s.score([])
    assert conf == pytest.approx(0.0)
    assert s.requires_human_review(conf)


# ---------------------------------------------------------------------------
# Human review threshold
# ---------------------------------------------------------------------------

def test_requires_human_review_below_threshold():
    s = scorer(human_review_threshold=0.850)
    assert s.requires_human_review(0.849)
    assert s.requires_human_review(0.700)
    assert s.requires_human_review(0.000)


def test_not_human_review_at_or_above_threshold():
    s = scorer(human_review_threshold=0.850)
    assert not s.requires_human_review(0.850)
    assert not s.requires_human_review(0.950)
    assert not s.requires_human_review(0.999)


def test_f1_alone_does_not_require_review():
    """F1 alone (0.950) is above the 0.850 threshold -- no human review needed."""
    s = scorer()
    conf = s.score(["F1"])
    assert not s.requires_human_review(conf)
