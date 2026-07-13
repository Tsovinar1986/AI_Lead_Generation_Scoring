# What's left

Updated after wiring live integrations, the Gravity AI package, Stripe
licensing (with subscription renewal + email delivery), and a full frontend
+ manual QA pass. Nothing here blocks local use/eval — these matter before
selling to a real, unknown buyer.

## Verify against real accounts before going live

Implemented against each provider's documented API shape and exercised with
mocked clients (unit-level), but none were tested against a live
account/sandbox (no credentials available in this session):

- **Apollo.io** ([enrichment.py](backend/app/services/enrichment.py)) —
  confirm the `organizations/enrich` endpoint/response fields against a real
  API key; Apollo's API has changed shape before.
- **HubSpot** ([crm.py](backend/app/services/crm.py)) — custom company
  properties are now auto-created via the Properties API on first push
  (verified against the real installed SDK's method signatures), but the
  actual create call itself hasn't hit a live portal.
- **Salesforce** (same file) — custom Lead fields are best-effort
  auto-created via the Tooling API. This is the shakiest of the four:
  Tooling API field creation is asynchronous/eventually-consistent and
  needs "Customize Application" on the API user; a failure here is caught
  and logged, never blocks the push, but treat as "usually works."
- **Slack** ([alerts.py](backend/app/services/alerts.py)) — now runs an
  `auth.test`/`conversations.info` preflight that logs a specific diagnostic
  (bad token vs. bot not invited to the channel) instead of a generic error;
  the diagnostic logic itself is unit-tested, the real Slack API isn't.

## Licensing/billing

- **No email delivery provider beyond raw SMTP.** `services/license_email.py`
  sends via `smtplib` when `SMTP_*` is set; fine for low volume, but there's
  no SendGrid/SES integration (better deliverability/analytics at scale).
- **Subscription renewal is now handled** — `invoice.paid` reissues a license
  each billing cycle, `customer.subscription.deleted`/`invoice.payment_failed`
  are logged (no new key issued, so the last-issued key simply expires at its
  `LICENSE_VALIDITY_DAYS` window). This is inherent to offline-verified
  licenses, not a bug: an already-issued key can't be actively revoked
  on refund/cancellation without a phone-home check, which defeats the
  point of offline verification. Documented in `licensing/README.md`.
- **CORS is now configurable** (`CORS_ALLOWED_ORIGINS`) — still defaults to
  `localhost:5173`, a production deploy must set it.

## Gravity AI — one manual step before submitting

- The **"Command line arguments" field** (`{input} {output}`) is set in
  Gravity AI's upload wizard, not in `gravityai-build.json` — their docs
  describe it as a UI build setting. Confirm this in the live dashboard when
  you actually submit; see the caveat in [gravity-ai/README.md](gravity-ai/README.md).

## Testing / ops — still nothing automated

- No automated test suite (no `pytest`, no Vitest/RTL) — everything verified
  in this session was manual (TestClient smoke tests, mocked-client unit
  checks, and a real Playwright click-through of the running app).
- No CI (lint/test/build on push).
- No persistent DB — `storage.py` is in-memory, resets on every restart;
  fine for a single-tenant self-hosted buyer, not fine for anything
  multi-user (already called out as v1 scope in `DESCRIPTION.md`).
- No structured logging/monitoring beyond `loguru` to stdout.

## Fixed during this pass (for reference, not still open)

- Duplicate leads on re-upload — `storage.upsert_leads` now dedupes by
  domain instead of by the freshly-generated `Lead.id` each parse mints.
  Found via an actual browser click-through, not inferred.
- Stripe SDK v15's `StripeObject` dropped `.get()` — the webhook handler now
  parses the raw verified payload with `json.loads` instead of relying on
  the SDK's wrapper object, so it doesn't break on the next stripe-python bump.
- `hubspot-api-client`'s discovery module imports the deprecated
  `pkg_resources`, which modern `setuptools` no longer ships by default —
  pinned `setuptools<81` in `requirements.txt`.
- Frontend: configurable `VITE_API_BASE_URL`, a license-status banner with a
  working "Buy a license" button, a `/purchase-complete` page, a distinct
  402 ("trial expired, buy a license") UI state instead of a generic upload
  error, and a real button-link style fix caught only by screenshotting it.

## Not worth doing yet

Multi-tenancy, SSO, AWS Marketplace/AppExchange packaging — hold per the
sequencing in [licensing/README.md](licensing/README.md#go-to-market-strategy)
until there's a paying customer from the direct-sale channel validating
demand.
