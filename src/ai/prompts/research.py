"""
research.py -- Prompt builder for the Gemini research step (Step 1).

Gemini 2.5 Pro receives the full scrubbed provider profile JSON and produces
a comprehensive research context used as input to the Opus analysis step.
"""
from __future__ import annotations

import json
from typing import Any

_SYSTEM_PREFIX = """\
You are a medical credentialing research assistant for a healthcare provider intelligence
platform. You receive structured provider profile data and synthesize it into a
comprehensive research context for a clinical compliance analyst.

Analyze all available data and produce a detailed research summary covering:
1. Identity confidence and data completeness score
2. Licensing status across all states (active, expired, revoked, suspended)
3. Federal exclusions (OIG LEIE, SAM.gov) - severity, dates, and basis if available
4. State board disciplinary actions - nature, severity, and resolution status
5. Education and training background
6. Medicare and Medicaid participation status
7. Data source coverage and any notable gaps
8. Any patterns, anomalies, or items warranting clinical compliance attention

Be factual and precise. Cite specific dates and states where relevant.
Do not speculate beyond what the data contains.
"""


def build_research_prompt(npi: str, scrubbed_profile: dict[str, Any]) -> str:
    """
    Build the Gemini research prompt for a given provider profile.

    Args:
        npi:              The provider NPI (10-digit string).
        scrubbed_profile: PII-scrubbed profile dict (from scrub_pii()).

    Returns:
        Full prompt string ready for Gemini.
    """
    profile_json = json.dumps(scrubbed_profile, indent=2, default=str)
    return (
        f"{_SYSTEM_PREFIX}\n\n"
        f"Provider NPI: {npi}\n\n"
        f"Profile Data:\n```json\n{profile_json}\n```\n\n"
        "Produce your research context summary now:"
    )
