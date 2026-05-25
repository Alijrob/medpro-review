# Source Connector Framework (C9) — Phase 2-A

The base classes, error handling, throttling, retry/backoff, and contract-testing that
every source adapter (C10, Phase 2-B+) builds on. **Framework only** — it fetches no live
source. Real ingestion lives in the adapters and is governed by the **Phase 0 legal gate**.

Async-first (`httpx`), per the locked stack. Retry/backoff is in-house (no `tenacity`).

---

## Layout

| File | Purpose |
|------|---------|
| `base.py` | `SourceConnector` ABC. Adapters implement `fetch_raw`; `run()` orchestrates fetch → contract check → provenance hashing → `FetchResult` + `SourceHealthRecord`. |
| `config.py` | `ConnectorConfig` — per-source identity + operational knobs (timeout, retries, rate limit, expected min records). |
| `models.py` | `RawRecord` (payload + provenance, pre-normalization), `FetchResult`, `FetchStatus`, `IntegrationMethod`. |
| `errors.py` | Error taxonomy — each carries `retryable` + a `SourceStatus`. |
| `retry.py` | `retry_with_backoff` — exponential backoff + full jitter; retries only retryable errors; honors `Retry-After`. |
| `throttle.py` | `RateLimiter` — client-side min-interval spacing; injectable clock/sleep. |
| `contract.py` | `SchemaContract` — runtime schema-drift guard (risk R6). |
| `testing.py` | Reusable contract-test harness (`assert_connector_contract`, `stub_transport`, …). |

---

## Built adapters (`sources/`)

Concrete C10 adapters live in `src/connectors/sources/` (one module per source). Each
subclasses `SourceConnector`, declares a `SchemaContract`, and is contract-tested against
a stubbed transport. **Live ingestion is governed by the Phase 0 legal gate** — these are
built and tested with no network I/O.

| Source | Module | Mode | Phase |
|--------|--------|------|-------|
| F1 — NPPES / NPI Registry | `sources/nppes.py` | API lookup (paginated via `skip`); bulk-DL deferred | 2-B.1 ✅ |
| F2 — OIG LEIE | `sources/oig_leie.py` | monthly bulk CSV; API spot-check deferred | 2-B.2 ✅ |
| F3 — SAM.gov Exclusions | `sources/sam_gov.py` | paginated REST API (api_key); delta-sync deferred | 2-B.3 ✅ |
| F4 — CMS Care Compare | `sources/cms_care_compare.py` | SODA paginated JSON ($limit/$offset/$order=:id); no key | 2-B.4 ✅ |
| I1 — CMS Medicare Enrollment  | `sources/cms_medicare_enrollment.py`  | Two SODA datasets in one run: enrollment + opt-out; `_record_type` tag; no key | 2-B.5 ✅ |
| I2 — CMS Medicaid Enrollment  | `sources/cms_medicaid_enrollment.py`  | Single SODA dataset; `$limit/$offset/$order=:id`; 5-field contract; no key     | 2-B.6 ✅ |

## Writing an adapter (C10, Phase 2-B)

```python
class NppesConnector(SourceConnector):
    contract = SchemaContract(
        required_fields=frozenset({"number", "enumeration_type", "basic", "addresses", "taxonomies"}),
    )

    async def fetch_raw(self):
        resp = await self.request("GET", "/api/", params={"version": "2.1", "limit": 200})
        for item in resp.json().get("results", []):
            yield item
```

`self.request(...)` gives throttling, retry/backoff, and HTTP→error classification for free
(429 → `RateLimitedError`, 401/403 → `AuthenticationError`, 5xx/timeouts → retryable
`SourceUnavailableError`, other 4xx → `PermanentError`). `run()` wraps each yielded dict in a
`RawRecord` (content-addressed SHA-256 hash via `DataProvenance.hash_raw`), validates it
against `contract`, and returns a `FetchResult` whose `health` is a `SourceHealthRecord` the
Source Health Monitor (C24) consumes.

The adapter's output is a **RawRecord** (pre-normalization). Turning it into a typed
`NormalizedRecord` is C11 (Normalization Layer, Phase 2-D).

---

## Contract testing

Adapters get framework-conformance coverage by reusing the harness:

```python
from connectors.testing import assert_connector_contract, stub_transport, StubResponse

async def test_nppes_contract():
    conn = NppesConnector(cfg, transport=stub_transport(StubResponse(json_body={"results": [{...}]})))
    await assert_connector_contract(conn)
```

---

## Validate locally

```bash
make connectors-test                 # or: PYTHONPATH=src pytest tests/connectors/ -v
```

CI: `.github/workflows/connectors-validate.yml`. Tests are sync (drive the async code with
`asyncio.run`), so no `pytest-asyncio` is needed and transports are always stubbed (no network).
