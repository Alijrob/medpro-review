# Payment Service (Phase 2-J)

FastAPI shell for Stripe Checkout integration. Port **8005**.

## Responsibility

- Accept report purchase requests, create Stripe Checkout sessions
- Receive Stripe webhook events, complete payment processing
- Backfill `user_id`, `use_agreement_id`, `stripe_payment_intent_id` on the reports row when payment completes

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /healthz | Liveness |
| GET | /readyz | Readiness (Stripe + DB config status) |
| POST | /v1/payments/checkout | Create a Stripe Checkout session |
| POST | /v1/payments/webhook | Stripe webhook receiver |

## Checkout Flow

```
1. Client: POST /v1/reports/request          → report_id
2. Client: POST /v1/payments/checkout        → checkout_url (Stripe)
3. User completes Stripe Checkout
4. Stripe: POST /v1/payments/webhook         → payment recorded
5. Client: GET  /v1/reports/{report_id}      → report result
```

### POST /v1/payments/checkout

**Request body:**
```json
{
  "report_id": "uuid",
  "npi": "1234567890",
  "success_url": "https://yoursite.com/success?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://yoursite.com/cancel",
  "certified_personal_use_only": true,
  "customer_email": "optional@example.com"
}
```

- `certified_personal_use_only` **must be `true`** -- Path B gate. A `false` value returns 422.
- `{CHECKOUT_SESSION_ID}` in `success_url` is replaced by Stripe with the actual session ID.

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/pay/cs_...",
  "session_id": "cs_...",
  "report_id": "uuid",
  "stripe_configured": true
}
```

Redirect the user to `checkout_url`. When Stripe is not configured (`PAYMENT_STRIPE_SECRET_KEY` not set), a mock URL is returned and `stripe_configured: false`.

### POST /v1/payments/webhook

Stripe sends this endpoint a raw POST. The endpoint:
1. Verifies the `Stripe-Signature` header against `PAYMENT_STRIPE_WEBHOOK_SECRET`
2. Routes `checkout.session.completed` events
3. Idempotent -- if `payment_status` is already `paid`, returns `action: "skipped"`

**Returns 400 on invalid signature.** All other errors return 200 (prevents Stripe from retrying broken DB states indefinitely).

## Configuration

All settings use the `PAYMENT_` prefix:

| Env Var | Default | Required |
|---------|---------|----------|
| `PAYMENT_STRIPE_SECRET_KEY` | `` | Yes for live payments |
| `PAYMENT_STRIPE_WEBHOOK_SECRET` | `` | Yes for webhook sig verification |
| `PAYMENT_STRIPE_PRICE_ID` | `` | Recommended (Stripe Price object ID) |
| `PAYMENT_REPORT_PRICE_USD` | `35.00` | Used if no price_id |
| `PAYMENT_TOS_VERSION` | `tos-v1.0` | Written to use_agreements |
| `PAYMENT_DATABASE_URL` | Falls back to `DATABASE_URL` | Yes for persistence |
| `PAYMENT_SENTRY_DSN` | `` | Optional observability |

## DB Tables Touched

| Table | Operations |
|-------|------------|
| `reports` | read `get_report_row/get_report_by_session`, write `set_checkout_session`, `complete_payment` |
| `users` | `upsert_user` (INSERT ON CONFLICT DO NOTHING by email) |
| `use_agreements` | `create_use_agreement` (INSERT with `certified_personal_use_only=True`) |

## Migration 0006

```
stripe_checkout_session_id  VARCHAR(200) NULL   -- Stripe cs_... session ID
payment_status              VARCHAR(20)  DEFAULT 'unpaid'  -- unpaid|pending|paid|refunded
```

Added to the `reports` table. `stripe_checkout_session_id` has a partial unique index for O(1) webhook lookup. `payment_status` has a CHECK constraint enforcing the four allowed values.

## Running Locally

```bash
# Stripe not configured -- mock checkout URL returned
make run-payment-service

# With test keys
PAYMENT_STRIPE_SECRET_KEY=sk_test_... \
PAYMENT_STRIPE_WEBHOOK_SECRET=whsec_... \
make run-payment-service
```

## Testing

```bash
make payment-test
# or
PYTHONPATH=src:. pytest tests/backend/test_payment_service.py -v
```

51 tests. All run without a live Stripe key or DB (mocked with `unittest.mock`).

## Key Design Decisions (DECISIONS.md Entry 031)

- **Stripe Checkout** (not Payment Intents): Stripe hosts the payment page, handles PCI compliance
- **Metadata on session**: `report_id` + `npi` + `certified_personal_use_only` baked in for webhook lookup
- **Idempotent webhook**: `payment_status == 'paid'` guard prevents double-processing
- **User upsert by email**: Phase 2-K links Auth0 account; Phase 2-J creates minimal row
- **Use agreement at payment time**: Path B certification captured when user completes Stripe Checkout
- **Signature verification fail = 400**: Stripe retries 400s; permanent errors should return 4xx
- **DB errors in webhook = 200**: Prevents Stripe from infinite retry; ops engineer re-processes via dashboard
