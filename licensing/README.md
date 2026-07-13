# Selling this as a self-hosted product

Ed25519-signed license keys, verified offline by the app itself — no
license server to run, no phone-home, works for a buyer who self-hosts on
their own infra. Stripe handles payment; a webhook mints the key.

## One-time setup (you, the seller)

1. **Generate your signing keypair** (do this once, ever):
   ```
   python licensing/generate_keypair.py
   ```
   Keep `LICENSE_PRIVATE_KEY` secret (only your deployment needs it — put it
   in your `.env`, never commit it, back it up somewhere safe: losing it
   means you can't issue new licenses without invalidating every key
   you've already sold). `LICENSE_PUBLIC_KEY` is safe to commit/ship; it can
   only verify signatures, not create them.

2. **Create a Stripe product + price**, then set in your `.env`:
   `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_SUCCESS_URL`,
   `STRIPE_CANCEL_URL`.

3. **Add a webhook endpoint** in the Stripe dashboard pointing at
   `https://<your-domain>/api/billing/webhook`, subscribed to
   `checkout.session.completed`. Copy the signing secret into
   `STRIPE_WEBHOOK_SECRET`.

4. Run this same app (`backend/`) as your storefront backend — it already
   exposes `POST /api/billing/checkout` (returns a Stripe Checkout URL) and
   the webhook. A "Buy" button on your marketing site just POSTs to
   `/api/billing/checkout` and redirects to the returned URL.

## What happens on a sale

Stripe fires `checkout.session.completed` → the webhook signs a license
(`{customer_email, plan, issued_at, expires_at}`) with `LICENSE_PRIVATE_KEY`
→ appends it to `licensing/issued_licenses.jsonl` and emails it to the buyer
(`backend/app/services/license_email.py`, SendGrid if `SENDGRID_API_KEY` is
set, else plain SMTP if `SMTP_HOST` is set). With neither configured, it's
still issued and logged/appended to that file — tail it and send the key by
hand.

Need a comp/manual license (a pilot customer, a partner)? Skip Stripe:
```
LICENSE_PRIVATE_KEY=... python licensing/issue_license.py --email x@y.com --plan pro --days 365
```

## What the buyer does

Drop the license key you send them into their `.env`:
```
LICENSE_KEY=<the key you issued them>
LICENSE_PUBLIC_KEY=<your public key, ship this with the product>
LICENSE_REQUIRED=true
```
With `LICENSE_REQUIRED=true`, `/api/leads/upload` 402s until the key
verifies. Leave it `false` (the default) for evaluation/trial use — the
whole point of shipping this as self-hosted software is that a prospect can
run it fully unlocked to evaluate before you ever collect payment.

---

## Go-to-market strategy

**Positioning**: not "another lead scoring tool" — a hybrid rule+LLM scorer
a buyer can point at their own CRM export and get ranked, rationale-backed
leads with drafted outreach in minutes, self-hosted so their lead data never
leaves their infra. That data-residency angle is the differentiator against
SaaS competitors for security-conscious B2B buyers (fintech, healthtech,
anyone who'd balk at uploading a CRM export to a third party).

**Who buys this**: a solo RevOps/sales-ops person or small GTM team at a
company with an existing CRM export and no in-house scoring model — the
"I have 5,000 rows, a HubSpot account, and no data scientist" buyer. Not
large enterprise (no SSO yet) and not hobbyists (real integrations, real
setup) — though multi-tenancy (`scripts/create_tenant.py`) now makes it
viable to run one shared instance for several customers if you're selling
it that way rather than self-hosted-per-buyer.

**Sequencing** (cheapest/fastest validation first):

1. **Direct sale via this Stripe flow, now.** Zero marketplace approval,
   fastest to first dollar. Use it to find out whether "self-hosted lead
   scorer" resonates at all before investing in channel-specific work.
2. **RapidAPI**, once the direct-sale pitch is validated. The FastAPI
   backend already is the product surface — wrapping it with API-key/quota
   auth for a metered listing is the next-cheapest channel and reaches
   buyers who want to call it, not run it.
3. **HubSpot App Marketplace / Salesforce AppExchange** — only worth it once
   you have paying customers on #1-2 validating demand; these are
   multi-week review processes and require native (OAuth) integrations, not
   the static access-token calls this app makes today.
4. **AWS Marketplace / AppSumo** — `storage.py` now supports multiple
   isolated tenants on one deployment (`backend/scripts/create_tenant.py`),
   so the technical blocker is gone; still hold until #1-2 validate demand,
   since both are their own multi-week registration/review processes.

**Pricing anchor**: price against the labor it replaces (an SDR/RevOps
hour spent manually qualifying+drafting per lead), not against per-seat SaaS
comps — a one-time or annual self-hosted license reads as "buy the tool,"
which is a different (and for this buyer, often easier) purchase decision
than "add another monthly subscription."
