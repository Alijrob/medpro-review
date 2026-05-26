# report -- C17 Report Generation Service (Phase 2-H basic)

Pure library. No network I/O, no deployed service. Transforms `CanonicalProviderProfile`
into `ProviderReport` (typed Pydantic model) and renders it to JSON or HTML.

## Files

| File | Purpose |
|------|---------|
| `config.py` | `ReportSettings` (env prefix `REPORT_`); `PATH_B_DISCLAIMER` constant |
| `models.py` | `ProviderReport` + all section sub-models |
| `builder.py` | `build_report(profile) -> ProviderReport` -- pure transform |
| `renderer.py` | `render_html(report) -> str` -- Jinja2 HTML rendering |
| `templates/provider_report.html.j2` | HTML template |

## Usage

```python
from report import build_report, render_html

report = build_report(profile)         # CanonicalProviderProfile -> ProviderReport
json_str = report.model_dump_json()    # JSON API response
html_str = render_html(report)         # HTML for display / PDF pipeline
```

## Compliance

- `disclaimer` is **always** injected from `PATH_B_DISCLAIMER` (Path B; DECISIONS.md Entry 007).
- `report_disclaimer_required` is always `True` on Path B.
- The HTML template renders the disclaimer in a distinct yellow-bordered box.
- `is_partial` propagates from the source profile; partial reports are flagged in both JSON and HTML.

## Design notes

- `build_report()` is a pure function (no side effects, no network calls).
- All list fields preserve source ordering from `CanonicalProviderProfile`.
- `render_html()` uses `jinja2.select_autoescape` -- all template variables are HTML-escaped.
- The Jinja2 `Environment` is module-level (created once, reused across calls).
- PDF rendering (WeasyPrint) is Phase 5-C, not here.

## DECISIONS.md

Entry 029 -- Report Generation Design (Phase 2-H)
