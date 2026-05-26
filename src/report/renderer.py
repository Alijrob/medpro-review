"""
renderer.py -- HTML rendering for ProviderReport (C17 basic).

Uses Jinja2 to render provider_report.html.j2. Returns a UTF-8 HTML string.
No network I/O. No WeasyPrint (PDF is Phase 5-C). This is the basic HTML shell.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import ProviderReport

# Template directory is adjacent to this file.
_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


# Module-level env (created once, shared across calls)
_ENV: Environment | None = None


def _get_env() -> Environment:
    global _ENV
    if _ENV is None:
        _ENV = _make_env()
    return _ENV


def render_html(report: ProviderReport, *, template_name: str = "provider_report.html.j2") -> str:
    """
    Render a ProviderReport to an HTML string.

    Args:
        report: The structured report produced by build_report().
        template_name: Jinja2 template file name (default: provider_report.html.j2).

    Returns:
        UTF-8 HTML string.
    """
    env = _get_env()
    template = env.get_template(template_name)
    return template.render(report=report)
