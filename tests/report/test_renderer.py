"""
test_renderer.py -- Unit tests for report.renderer.render_html() (C17 basic).

20 tests covering:
    - HTML structure basics (doctype, html, body tags)
    - Provider name and NPI in output
    - Partial vs full report badge
    - Exclusion alert banner presence/absence
    - Disciplinary alert banner presence/absence
    - Disclaimer block always rendered
    - License status pills
    - No address / no licenses / empty exclusions graceful rendering
    - Report ID in footer
    - HTML escaping (XSS protection via Jinja2 autoescape)
"""
from __future__ import annotations

import pytest

from report import build_report, render_html

from ._fixtures import (
    make_disciplined_profile,
    make_excluded_active_profile,
    make_full_profile,
    make_licensed_profile,
    make_minimal_profile,
    make_no_address_profile,
    make_org_profile,
    make_partial_profile,
)


def _render(profile) -> str:
    return render_html(build_report(profile))


# ---------------------------------------------------------------------------
# HTML structure
# ---------------------------------------------------------------------------


def test_render_returns_string():
    html = _render(make_minimal_profile())
    assert isinstance(html, str)


def test_render_has_doctype():
    html = _render(make_minimal_profile())
    assert "<!DOCTYPE html>" in html


def test_render_has_html_tag():
    html = _render(make_minimal_profile())
    assert "<html" in html
    assert "</html>" in html


def test_render_has_body_tag():
    html = _render(make_minimal_profile())
    assert "<body>" in html
    assert "</body>" in html


def test_render_nonempty():
    html = _render(make_minimal_profile())
    assert len(html) > 500


# ---------------------------------------------------------------------------
# Provider identity in output
# ---------------------------------------------------------------------------


def test_render_contains_npi():
    html = _render(make_full_profile())
    assert "1234567890" in html


def test_render_contains_provider_name():
    html = _render(make_full_profile())
    assert "Alice" in html
    assert "Smith" in html


def test_render_contains_org_name():
    html = _render(make_org_profile())
    assert "Acme Medical Group" in html


def test_render_contains_specialty():
    html = _render(make_full_profile())
    assert "Family Medicine" in html


# ---------------------------------------------------------------------------
# Partial / full badge
# ---------------------------------------------------------------------------


def test_render_partial_badge_when_partial():
    html = _render(make_partial_profile())
    assert "Partial Report" in html


def test_render_full_badge_when_complete():
    html = _render(make_full_profile())
    assert "Full Report" in html


def test_render_partial_alert_when_partial():
    html = _render(make_partial_profile())
    assert "Partial Report" in html
    assert "still in progress" in html


# ---------------------------------------------------------------------------
# Critical flag banners
# ---------------------------------------------------------------------------


def test_render_exclusion_alert_when_excluded():
    html = _render(make_excluded_active_profile())
    assert "FEDERAL EXCLUSION ACTIVE" in html


def test_render_no_exclusion_alert_when_clean():
    html = _render(make_full_profile())
    assert "FEDERAL EXCLUSION ACTIVE" not in html


def test_render_disciplinary_alert_when_active():
    html = _render(make_disciplined_profile())
    assert "Active Disciplinary Action" in html


def test_render_no_disciplinary_alert_when_clean():
    html = _render(make_full_profile())
    assert "Active Disciplinary Action" not in html


# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------


def test_render_disclaimer_present():
    html = _render(make_minimal_profile())
    assert "IMPORTANT NOTICE" in html


def test_render_disclaimer_contains_fcra_text():
    html = _render(make_minimal_profile())
    assert "Fair Credit Reporting Act" in html or "FCRA" in html


def test_render_disclaimer_path_b_text():
    html = _render(make_minimal_profile())
    assert "personal research" in html.lower()


# ---------------------------------------------------------------------------
# License section
# ---------------------------------------------------------------------------


def test_render_license_active_pill():
    html = _render(make_licensed_profile())
    assert "Active" in html


def test_render_no_licenses_empty_state():
    html = _render(make_minimal_profile())
    assert "No license records found" in html


# ---------------------------------------------------------------------------
# Exclusion section
# ---------------------------------------------------------------------------


def test_render_no_exclusions_empty_state():
    html = _render(make_minimal_profile())
    assert "No exclusion records found" in html


def test_render_exclusion_authority():
    html = _render(make_excluded_active_profile())
    assert "OIG LEIE" in html
    assert "SAM.gov" in html


# ---------------------------------------------------------------------------
# Disciplinary section
# ---------------------------------------------------------------------------


def test_render_no_disciplinary_empty_state():
    html = _render(make_minimal_profile())
    assert "No disciplinary actions found" in html


def test_render_disciplinary_action_type():
    html = _render(make_disciplined_profile())
    assert "License Revocation" in html


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


def test_render_report_id_in_footer():
    report = build_report(make_full_profile())
    html = render_html(report)
    assert str(report.report_id) in html


def test_render_site_name_in_footer():
    html = _render(make_minimal_profile())
    assert "ResearchYourDoctor" in html


# ---------------------------------------------------------------------------
# XSS / escaping
# ---------------------------------------------------------------------------


def test_render_escapes_html_in_name():
    """Jinja2 autoescape must prevent injection via provider name."""
    from schema.v1.common import EntityType, ProviderName
    from schema.v1.profile import CanonicalProviderProfile
    from ._fixtures import BUNDLE_ALICE, FIXED_DT

    profile = CanonicalProviderProfile(
        npi="1234567890",
        bundle_id=BUNDLE_ALICE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(
            first="<script>alert('xss')</script>",
            last="Smith",
        ),
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )
    html = render_html(build_report(profile))
    # Raw script tag must not appear in output
    assert "<script>alert" not in html
    # But the escaped version should be present
    assert "&lt;script&gt;" in html
