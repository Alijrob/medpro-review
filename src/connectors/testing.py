"""
testing.py — reusable contract-test harness for connectors (component C9).

The *test* facet of "contract testing": C10 adapters get framework-conformance
coverage for free by driving a stub transport through these helpers, and the
framework self-tests with them. Kept in the package (not under tests/) so adapter
suites in any location can import it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .base import SourceConnector
from .models import FetchStatus

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass
class StubResponse:
    """A minimal httpx.Response stand-in for tests."""

    status_code: int = 200
    json_body: Any = None
    text_body: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return self.json_body

    @property
    def text(self) -> str:
        return self.text_body


def stub_transport(*items: Any):
    """An async transport that returns/raises queued items in order, per request.

    Each item is either a StubResponse (returned) or an Exception (raised, to
    simulate a transport-level fault). The last item repeats once the queue drains.
    """
    queue = list(items)

    async def _transport(method: str, url: str, **kwargs: Any) -> Any:
        item = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else StubResponse())
        if isinstance(item, BaseException):
            raise item
        return item

    return _transport


def recording_sleep() -> tuple[Any, list[float]]:
    """An async sleep that records delays instead of waiting. Returns (sleep, delays)."""
    delays: list[float] = []

    async def _sleep(seconds: float) -> None:
        delays.append(seconds)

    return _sleep, delays


def fixed_clock(step: float = 1.0):
    """A monotonic clock that advances by `step` on each call (deterministic timing)."""
    state = {"t": 0.0}

    def _clock() -> float:
        state["t"] += step
        return state["t"]

    return _clock


async def assert_connector_contract(connector: SourceConnector, *, min_records: int = 1) -> None:
    """Assert a connector conforms to the framework contract.

    Adapters call this from their own test suite with a stub transport:
        await assert_connector_contract(MyAdapter(cfg, transport=stub_transport(...)))
    """
    result = await connector.run()

    assert result.source_id == connector.source_id
    assert result.status in {FetchStatus.SUCCESS, FetchStatus.PARTIAL}, result.errors
    assert result.record_count == len(result.records)
    assert result.record_count >= min_records

    for rec in result.records:
        assert rec.source_id == connector.source_id
        assert _SHA256.match(rec.raw_record_hash), f"bad hash: {rec.raw_record_hash}"
        # Hash is deterministic: recomputing from the same raw payload reproduces it.
        from .models import RawRecord

        assert RawRecord.from_raw(rec.source_id, rec.raw).raw_record_hash == rec.raw_record_hash

    # Health snapshot is always populated and consistent with the run.
    assert result.health.source_id == connector.source_id
    assert result.health.source_category == connector.source_category
    assert result.health.last_checked_at is not None
