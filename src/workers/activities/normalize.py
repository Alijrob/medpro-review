"""
normalize.py -- normalize_records_activity: RawRecords -> NormalizedRecords (C11 wrapper).
"""
from __future__ import annotations

import logging

from temporalio import activity

from connectors.models import RawRecord
from normalizers import NormalizationError, normalize

from ..models import NormalizeRecordsInput, NormalizeRecordsOutput

log = logging.getLogger(__name__)


@activity.defn(name="normalize_records")
def normalize_records_activity(inp: NormalizeRecordsInput) -> NormalizeRecordsOutput:
    """
    Normalize a list of raw record dicts into NormalizedRecord dicts.

    Records that fail normalization are logged and skipped (error collected).
    Returns NormalizeRecordsOutput with both the successful records and the
    error messages for failed ones.
    """
    normalized = []
    errors = []

    for raw_dict in inp.raw_records:
        try:
            raw = RawRecord.model_validate(raw_dict)
            record = normalize(raw, entity_npi=inp.entity_npi)
            normalized.append(record.model_dump(mode="json"))
        except NormalizationError as exc:
            msg = f"NormalizationError source={raw_dict.get('source_id','?')}: {exc}"
            activity.logger.warning(msg)
            errors.append(msg)
        except Exception as exc:  # noqa: BLE001
            msg = f"Unexpected normalization error source={raw_dict.get('source_id','?')}: {exc}"
            activity.logger.error(msg)
            errors.append(msg)

    activity.logger.info(
        "normalize_records_activity: in=%d out=%d errors=%d",
        len(inp.raw_records), len(normalized), len(errors),
    )

    return NormalizeRecordsOutput(
        normalized_records=normalized,
        normalization_errors=errors,
        records_count=len(normalized),
    )
