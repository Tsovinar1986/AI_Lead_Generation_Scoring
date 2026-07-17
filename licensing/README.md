# Selling this as a self-hosted product

Ed25519-signed license keys, verified offline by the app itself — no
license server to run, no phone-home, works for a buyer who self-hosts on
their own infra. Paddle handles payment; a webhook mints the key.

Paddle (not Stripe) is deliberate: Paddle is a merchant-of-record, so it
also handles sales tax/VAT globally for you, and its seller-eligibility
list is broader than Stripe's — notably it works for sellers in countries
Stripe doesn't support directly. Card, PayPal, Apple Pay, and Google Pay all
show up automatically on Paddle's hosted checkout for eligible buyers —
PayPal specifically may need enabling once under Paddle dashboard →
Checkout → Payment methods if it isn't already on.

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

2. **Create a Paddle account** at paddle.com — you'll land in **Sandbox**
   mode by default (a fully separate test account/API host, no real money),
   which is what you want first. Production is a separate application/
   approval step once you're ready to take real payments.

3. **Create a product with two recurring prices** — monthly and annual, e.g.
   $30/mo and ~$300/yr (a "2 months free" discount is a standard anchor and
   reads better than an arbitrary percentage off). In the Paddle dashboard:
   Catalog → Products → your product → Add price, once for each interval —
   each price ID looks like `pri_...`. Then set in your `.env`:
   `PADDLE_API_KEY` (Developer Tools → Authentication), `PADDLE_PRICE_ID_MONTHLY`,
   `PADDLE_PRICE_ID_ANNUAL`, and `PADDLE_ENVIRONMENT=sandbox` while testing.
   `POST /api/billing/checkout?interval=monthly` (or `annual`) picks which
   price a given "Buy" button uses and returns a hosted Paddle checkout URL.

4. **Add a notification destination** in Paddle (Developer Tools →
   Notifications → + New destination) pointing at
   `https://www.crmscoring.com/api/billing/webhook` (or wherever this
   backend ends up hosted), subscribed to
   `transaction.completed` (fires for both the first payment and every
   renewal — there's only one event to subscribe to, unlike Stripe's
   separate checkout/invoice events). Copy the destination's signing secret
   into `PADDLE_WEBHOOK_SECRET`.

5. Run this same app (`backend/`) as your storefront backend — it already
   exposes `POST /api/billing/checkout` (returns a Paddle checkout URL) and
   the webhook. A "Buy" button on your marketing site just POSTs to
   `/api/billing/checkout?interval=monthly|annual` and redirects to the
   returned URL. Once a full sandbox purchase works end-to-end, switch
   `PADDLE_ENVIRONMENT=production` and swap in your live API key/prices.

## What happens on a sale

Paddle fires `transaction.completed` → the webhook looks up the buyer's
email via Paddle's customer API (the webhook payload only carries a
`customer_id`), signs a license (`{customer_email, plan, issued_at,
expires_at}`) with `LICENSE_PRIVATE_KEY` → appends it to
`licensing/issued_licenses.jsonl` and emails it to the buyer
(`backend/app/services/license_email.py`, SendGrid if `SENDGRID_API_KEY` is
set, else plain SMTP if `SMTP_HOST` is set). With neither configured, it's
still issued and logged/appended to that file — tail it and send the key by
hand.

Need a comp/manual license (a pilot customer, a partner)? Skip Paddle:
```
LICENSE_PRIVATE_KEY=... python licensing/issue_license.py --email x@y.com --plan pro --days 365
```

## What the buyer does

Drop the license key you send them into their `.env`:
```
LICENSE_KEY=<the key you issued them>
LICENSE_PUBLIC_KEY=<your public key, ship this with the product>
```
A fresh deployment gets `TRIAL_DAYS` (default 3) of full-functionality
evaluation with no `LICENSE_KEY` set at all — the whole point of shipping
this as self-hosted software is that a prospect can run it unlocked to
evaluate before you ever collect payment. Once those days are up,
`/api/leads/upload` 402s until a valid `LICENSE_KEY` is set. Set
`LICENSE_REQUIRED=true` instead to skip the trial and require a key from
the first request (useful for your own storefront/demo instance, not
typical for a buyer's copy).

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

1. **Direct sale via this Paddle flow, now.** Zero marketplace approval,
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

**Current pricing**: $30/mo, or an annual plan priced at roughly 2 months
free (~$300/yr) to reward the lower-churn commitment — both set up as
separate recurring Paddle prices (`PADDLE_PRICE_ID_MONTHLY`/`_ANNUAL`),
selected via `/api/billing/checkout?interval=monthly|annual`. A 3-day
unlicensed trial (`TRIAL_DAYS`) runs automatically before either plan is
required, so a prospect always gets a no-card-required look before buying.
