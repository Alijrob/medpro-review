"""
format.py -- Prompt builder for the Haiku HTML formatting step (Step 3).

Claude Haiku receives the risk analysis and consumer summary text and formats
them into a clean, self-contained HTML block suitable for injection into the
provider report template.
"""
from __future__ import annotations

_SYSTEM_PREFIX = """\
You are an HTML formatter for a healthcare provider credentialing report.
Convert the following text sections into clean, semantic HTML.

Requirements:
- Use only: <p>, <strong>, <em>, <ul>, <li>, <h3>, <div>, <span> tags
- Do NOT include: <html>, <head>, <body>, <style>, <script> tags
- Wrap the entire output in a single <div class="ai-narrative">
- Add a <div class="risk-analysis"> block for the risk analysis section
- Add a <div class="consumer-summary"> block for the consumer summary section
- For the risk level line (e.g., "RISK LEVEL: HIGH"), add a <span> with CSS class
  one of: narrative-risk-low, narrative-risk-moderate, narrative-risk-high, narrative-risk-critical
  (match the level word to the class suffix, lowercase)
- Preserve all factual content -- do not summarise or omit anything
- Output only the HTML, no preamble or explanation
"""


def build_format_prompt(risk_analysis: str, consumer_summary: str) -> str:
    """
    Build the Haiku formatting prompt from analysis and summary texts.

    Args:
        risk_analysis:    Text output from parse_analysis_response()[0].
        consumer_summary: Text output from parse_analysis_response()[1].

    Returns:
        Full prompt string ready for Claude Haiku.
    """
    return (
        f"{_SYSTEM_PREFIX}\n\n"
        f"RISK ANALYSIS:\n{risk_analysis}\n\n"
        f"CONSUMER SUMMARY:\n{consumer_summary}\n\n"
        "Format the above into HTML now:"
    )
