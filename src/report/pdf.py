"""
pdf.py -- PDF rendering for ProviderReport (Phase 2-N).

Uses WeasyPrint to render an HTML string to PDF bytes.
WeasyPrint requires system-level libraries (Pango, Cairo, GLib) that are
installed in the production container image but are NOT required for the
local Python dev environment.

If WeasyPrint is unavailable the report service PDF endpoint returns HTTP 501
with a diagnostic message so dev/CI flows continue to work without system deps.

Public API::

    from report.pdf import render_pdf, WEASYPRINT_AVAILABLE

    if WEASYPRINT_AVAILABLE:
        pdf_bytes = render_pdf(html_string)
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Soft import -- fails gracefully when system deps are missing
# ---------------------------------------------------------------------------

WEASYPRINT_AVAILABLE: bool = False
_import_error: str | None = None

try:
    from weasyprint import HTML as _WeasyprintHTML  # type: ignore[import-untyped]

    WEASYPRINT_AVAILABLE = True
except Exception as _exc:  # noqa: BLE001
    _import_error = str(_exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_pdf(html: str) -> bytes:
    """
    Render an HTML string to PDF bytes via WeasyPrint.

    Args:
        html: UTF-8 HTML string (e.g. output of ``render_html()``).

    Returns:
        Raw PDF bytes suitable for serving as ``application/pdf``.

    Raises:
        ValueError: if *html* is empty.
        RuntimeError: if WeasyPrint is not available (missing system deps).
        Exception: any WeasyPrint rendering failure is propagated as-is.
    """
    if not html:
        raise ValueError("render_pdf: html must not be empty.")
    if not WEASYPRINT_AVAILABLE:
        raise RuntimeError(
            f"WeasyPrint is not available in this environment: {_import_error}. "
            "Install system dependencies (Pango, Cairo, GLib) then re-install "
            "the weasyprint package."
        )
    # WeasyPrint HTML.write_pdf() returns bytes
    return _WeasyprintHTML(string=html).write_pdf()  # type: ignore[return-value]
