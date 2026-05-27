"""
analysis.py -- Prompt builder for the Opus analysis step (Step 2).

Claude Opus receives the Gemini research context and produces two outputs in
one coherent reasoning pass: a professional risk analysis and a consumer summary.
"""
from __future__ import annotations

import re

_SYSTEM_PREFIX = """\
You are a healthcare compliance risk analyst preparing a credential verification report.
You have been given a research context synthesized from multiple authoritative data sources.

Based on the research context below, produce TWO clearly separated outputs:

[RISK_ANALYSIS]
A professional risk assessment (3-5 paragraphs) for a healthcare administrator covering:
- Overall risk level on the first line: RISK LEVEL: LOW, MODERATE, HIGH, or CRITICAL
- Key findings requiring attention, with specific facts from the data
- Compliance and regulatory concerns (licensing gaps, exclusions, disciplinary history)
- Recommended verification steps or actions where warranted
[END_RISK_ANALYSIS]

[CONSUMER_SUMMARY]
A plain-English summary (2-3 paragraphs) for a member of the public researching this provider:
- Who the provider is: credentials, specialty, and practice history
- Any important flags the consumer should be aware of (state clearly, without alarmism)
- What the data does and does not tell them (data completeness caveat)
[END_CONSUMER_SUMMARY]

Use the exact markers shown above. Do not omit either section.
"""

_RISK_ANALYSIS_RE = re.compile(
    r"\[RISK_ANALYSIS\](.*?)\[END_RISK_ANALYSIS\]",
    re.DOTALL,
)
_CONSUMER_SUMMARY_RE = re.compile(
    r"\[CONSUMER_SUMMARY\](.*?)\[END_CONSUMER_SUMMARY\]",
    re.DOTALL,
)


def build_analysis_prompt(research_context: str) -> str:
    """
    Build the Opus analysis prompt from a Gemini research context.

    Args:
        research_context: The full text output of the Gemini research step.

    Returns:
        Full prompt string ready for Claude Opus.
    """
    return (
        f"{_SYSTEM_PREFIX}\n\n"
        f"Research Context:\n{research_context}\n\n"
        "Produce your risk analysis and consumer summary now:"
    )


def parse_analysis_response(text: str) -> tuple[str, str]:
    """
    Extract risk_analysis and consumer_summary from Opus response text.

    Returns (risk_analysis, consumer_summary). Both default to "" if the
    markers are missing (graceful fallback).

    Args:
        text: Raw response text from Claude Opus.

    Returns:
        Tuple of (risk_analysis_text, consumer_summary_text).
    """
    risk_match = _RISK_ANALYSIS_RE.search(text)
    consumer_match = _CONSUMER_SUMMARY_RE.search(text)
    risk_analysis = risk_match.group(1).strip() if risk_match else ""
    consumer_summary = consumer_match.group(1).strip() if consumer_match else ""
    return risk_analysis, consumer_summary
