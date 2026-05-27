"""
ai -- Phase 4-H: Multi-model AI report intelligence layer.

3-step sequential pipeline:
    1. Gemini 2.5 Pro  (research):  full-profile context sweep -> research_context
    2. Claude Opus     (analysis):  risk analysis + consumer summary (single coherent call)
    3. Claude Haiku    (format):    format analysis/summary text -> clean HTML block

All providers use injectable clients for testing (no live API calls in unit tests).
When an API key is absent, the provider silently returns "" -- pipeline degrades gracefully.

Public API::

    from ai import generate_narrative, NarrativeResult, AISettings

    result = await generate_narrative(npi, profile_dict, settings)

DECISIONS.md Entry 040 (Phase 4-H).
"""
from .config import AISettings, get_ai_settings
from .models import NarrativeResult, NarrativeSection
from .narrative import NarrativeGenerator
from .router import generate_narrative

__all__ = [
    "AISettings",
    "get_ai_settings",
    "NarrativeResult",
    "NarrativeSection",
    "NarrativeGenerator",
    "generate_narrative",
]
