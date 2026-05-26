"""
index.py -- index_profile_activity: index CanonicalProviderProfile in OpenSearch (C14 wrapper).
"""
from __future__ import annotations

import logging

from temporalio import activity

from schema.v1.profile import CanonicalProviderProfile
from search import OpenSearchClient, ProviderIndexer
from search.config import get_settings as get_search_settings

from ..models import IndexProfileInput, IndexProfileOutput

log = logging.getLogger(__name__)


@activity.defn(name="index_profile")
def index_profile_activity(inp: IndexProfileInput) -> IndexProfileOutput:
    """
    Index a CanonicalProviderProfile into OpenSearch.

    If OpenSearch is not configured (SEARCH_OPENSEARCH_URL not set), the activity
    returns indexed=False without raising. This is expected in dev/test environments.
    """
    search_settings = get_search_settings()

    if not search_settings.is_configured:
        activity.logger.info(
            "index_profile_activity: OpenSearch not configured -- skipping index for npi=%s",
            inp.npi,
        )
        return IndexProfileOutput(
            indexed=False,
            doc_id=None,
            error_message="OpenSearch not configured (SEARCH_OPENSEARCH_URL not set)",
        )

    try:
        profile = CanonicalProviderProfile.model_validate(inp.profile)
    except Exception as exc:  # noqa: BLE001
        activity.logger.error("index_profile_activity: invalid profile: %s", exc)
        return IndexProfileOutput(
            indexed=False,
            error_message=f"Profile deserialisation failed: {exc}",
        )

    client = OpenSearchClient(settings=search_settings)
    indexer = ProviderIndexer(index_name=search_settings.index_name)

    try:
        result = indexer.index_profile(profile, client)
        activity.logger.info(
            "index_profile_activity: npi=%s success=%s result=%s",
            inp.npi, result.success, result.result,
        )
        return IndexProfileOutput(
            indexed=result.success,
            doc_id=inp.npi if result.success else None,
            error_message=result.error if not result.success else None,
        )
    except Exception as exc:  # noqa: BLE001
        activity.logger.error(
            "index_profile_activity: unexpected error npi=%s: %s", inp.npi, exc
        )
        return IndexProfileOutput(
            indexed=False,
            error_message=f"Index failed: {exc}",
        )
