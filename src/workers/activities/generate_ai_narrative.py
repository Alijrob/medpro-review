"""
generate_ai_narrative.py -- generate_ai_narrative_activity: CanonicalProviderProfile -> NarrativeResult (Phase 4-H).

Async Temporal activity. Runs the 3-step multi-model AI pipeline:
    1. Gemini 2.5 Pro  (research context)
    2. Claude Opus     (risk analysis + consumer summary)
    3. Claude Haiku    (HTML formatting)

This activity is BEST-EFFORT: a failure or missing API keys results in a
GenerateNarrativeOutput with narrative=None (or fallback=True), never a
pipeline abort. The generate_report_activity handles a missing narrative
gracefully (renders the report without the AI section).
"""
from __future__ import annotations

import logging

from temporalio import activity

from ai import generate_narrative
from ai.config import get_ai_settings

from ..models import GenerateNarrativeInput, GenerateNarrativeOutput

log = logging.getLogger(__name__)


@activity.defn(name="generate_ai_narrative")
async def generate_ai_narrative_activity(inp: GenerateNarrativeInput) -> GenerateNarrativeOutput:
    """
    Generate an AI narrative for a provider profile.

    Args:
        inp: GenerateNarrativeInput with profile dict and npi.

    Returns:
        GenerateNarrativeOutput with serialised NarrativeResult (or None on failure).
    """
    settings = get_ai_settings()

    if not settings.narrative_enabled:
        activity.logger.info(
            "generate_ai_narrative_activity: narrative disabled via AI_NARRATIVE_ENABLED, "
            "skipping npi=%s",
            inp.npi,
        )
        return GenerateNarrativeOutput(narrative=None, fallback=True)

    try:
        result = await generate_narrative(inp.npi, inp.profile, settings)

        activity.logger.info(
            "generate_ai_narrative_activity: npi=%s fallback=%s errors=%s",
            inp.npi,
            result.fallback,
            result.errors,
        )

        return GenerateNarrativeOutput(
            narrative=result.to_serialisable(),
            fallback=result.fallback,
        )

    except Exception as exc:  # noqa: BLE001
        # Log and return empty output -- never raise (best-effort)
        activity.logger.warning(
            "generate_ai_narrative_activity: npi=%s unexpected error: %s",
            inp.npi,
            exc,
        )
        return GenerateNarrativeOutput(
            narrative=None,
            fallback=True,
            error_message=str(exc),
        )
