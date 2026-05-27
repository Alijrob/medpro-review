"""
models.py -- NarrativeResult and supporting types for the AI narrative layer.

NarrativeResult is JSON-serialisable (plain str/bool fields only) so it can
travel through Temporal's JSON envelope as a dict.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class NarrativeSection(BaseModel):
    """Text outputs from each step of the 3-model pipeline."""

    research_context: str = ""
    """Gemini's full-profile research sweep."""

    risk_analysis: str = ""
    """Opus's professional risk assessment (3-5 paragraphs)."""

    consumer_summary: str = ""
    """Opus's plain-English summary for end consumers (2-3 paragraphs)."""

    formatted_html: str = ""
    """Haiku's HTML-formatted version of risk_analysis + consumer_summary."""


class NarrativeResult(BaseModel):
    """Complete output of one NarrativeGenerator.generate() call."""

    npi: str
    sections: NarrativeSection = Field(default_factory=NarrativeSection)
    model_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Maps step name to the model ID used: 'research', 'analysis', 'format'.",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    fallback: bool = False
    """True when one or more providers returned '' (key absent or API error)."""

    errors: list[str] = Field(default_factory=list)
    """Non-fatal error messages collected during generation."""

    def to_serialisable(self) -> dict[str, Any]:
        """Return a JSON-safe dict (datetime -> ISO string)."""
        return self.model_dump(mode="json")
