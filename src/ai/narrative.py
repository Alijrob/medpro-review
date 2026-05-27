"""
narrative.py -- NarrativeGenerator: 3-step multi-model pipeline.

Pipeline:
    Step 1 (Gemini):    build_research_prompt -> complete -> research_context
    Step 2 (Opus):      build_analysis_prompt -> complete -> parse -> risk_analysis + consumer_summary
    Step 3 (Haiku):     build_format_prompt -> complete -> formatted_html

If any step returns "" (provider fallback), subsequent steps receive empty
context and also return ""; the result is marked fallback=True.
"""
from __future__ import annotations

import logging
from typing import Any

from .config import AISettings
from .models import NarrativeResult, NarrativeSection
from .pii import scrub_pii
from .prompts import (
    build_analysis_prompt,
    build_format_prompt,
    build_research_prompt,
    parse_analysis_response,
)
from .providers import AnthropicProvider, GeminiProvider

log = logging.getLogger(__name__)


class NarrativeGenerator:
    """
    Orchestrates the 3-step AI narrative pipeline.

    All providers are injectable for testing. When constructed with defaults,
    providers are built from the AISettings API keys.

    Args:
        settings:   AISettings instance.
        gemini:     Optional GeminiProvider override (for tests).
        anthropic:  Optional AnthropicProvider override (for tests).
    """

    def __init__(
        self,
        settings: AISettings,
        *,
        gemini: GeminiProvider | None = None,
        anthropic: AnthropicProvider | None = None,
    ) -> None:
        self._settings = settings
        self._gemini = gemini if gemini is not None else GeminiProvider(settings.gemini_api_key)
        self._anthropic = (
            anthropic if anthropic is not None else AnthropicProvider(settings.anthropic_api_key)
        )

    async def generate(self, npi: str, profile: dict[str, Any]) -> NarrativeResult:
        """
        Run the full 3-step narrative pipeline.

        Args:
            npi:     Provider NPI.
            profile: Provider profile dict (will be PII-scrubbed internally).

        Returns:
            NarrativeResult with all sections populated (or empty strings on fallback).
        """
        scrubbed = scrub_pii(profile)
        errors: list[str] = []
        model_versions: dict[str, str] = {
            "research": self._settings.research_model,
            "analysis": self._settings.analysis_model,
            "format": self._settings.format_model,
        }

        # ------------------------------------------------------------------
        # Step 1: Research (Gemini)
        # ------------------------------------------------------------------
        research_context = ""
        if self._gemini.is_available:
            try:
                prompt = build_research_prompt(npi, scrubbed)
                research_context = await self._gemini.complete(
                    prompt,
                    max_tokens=self._settings.research_max_tokens,
                    model=self._settings.research_model,
                )
            except Exception as exc:  # noqa: BLE001
                msg = f"Step 1 (research) error: {exc}"
                log.warning("NarrativeGenerator npi=%s %s", npi, msg)
                errors.append(msg)
        else:
            log.info("NarrativeGenerator npi=%s: Gemini unavailable, skipping research step", npi)

        # ------------------------------------------------------------------
        # Step 2: Analysis (Opus)
        # ------------------------------------------------------------------
        risk_analysis = ""
        consumer_summary = ""
        if research_context and self._anthropic.is_available:
            try:
                prompt = build_analysis_prompt(research_context)
                raw_analysis = await self._anthropic.complete(
                    prompt,
                    max_tokens=self._settings.analysis_max_tokens,
                    model=self._settings.analysis_model,
                )
                risk_analysis, consumer_summary = parse_analysis_response(raw_analysis)
            except Exception as exc:  # noqa: BLE001
                msg = f"Step 2 (analysis) error: {exc}"
                log.warning("NarrativeGenerator npi=%s %s", npi, msg)
                errors.append(msg)
        elif not research_context:
            log.info(
                "NarrativeGenerator npi=%s: no research context, skipping analysis step", npi
            )
        else:
            log.info(
                "NarrativeGenerator npi=%s: Anthropic unavailable, skipping analysis step", npi
            )

        # ------------------------------------------------------------------
        # Step 3: Format (Haiku)
        # ------------------------------------------------------------------
        formatted_html = ""
        if (risk_analysis or consumer_summary) and self._anthropic.is_available:
            try:
                prompt = build_format_prompt(risk_analysis, consumer_summary)
                formatted_html = await self._anthropic.complete(
                    prompt,
                    max_tokens=self._settings.format_max_tokens,
                    model=self._settings.format_model,
                )
            except Exception as exc:  # noqa: BLE001
                msg = f"Step 3 (format) error: {exc}"
                log.warning("NarrativeGenerator npi=%s %s", npi, msg)
                errors.append(msg)
        elif not (risk_analysis or consumer_summary):
            log.info(
                "NarrativeGenerator npi=%s: no analysis content, skipping format step", npi
            )

        # Any empty output from an available provider = fallback
        fallback = bool(
            (self._gemini.is_available and not research_context)
            or (self._anthropic.is_available and research_context and not risk_analysis)
            or (self._anthropic.is_available and (risk_analysis or consumer_summary) and not formatted_html)
        )

        return NarrativeResult(
            npi=npi,
            sections=NarrativeSection(
                research_context=research_context,
                risk_analysis=risk_analysis,
                consumer_summary=consumer_summary,
                formatted_html=formatted_html,
            ),
            model_versions=model_versions,
            fallback=fallback,
            errors=errors,
        )
