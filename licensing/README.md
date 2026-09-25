# Selling this as a self-hosted product

The seller storefront sells Pro and Advanced as Braintree subscriptions,
each billed monthly or annually by card. Starter is free and has no plan.

At checkout the backend starts the subscription, signs an Ed25519 license
key, logs it for idempotency, emails it to the buyer and shows it on screen.
Every renewal charge issues and emails a fresh key. Each key stays valid a
little past the next billing date, so a cancelled subscription simply stops
receiving new keys.

## Setup

1. Generate the signing keypair once:

   ```sh
   python licensing/generate_keypair.py
   ```

   Keep `LICENSE_PRIVATE_KEY` only on the seller deployment. Ship the
   corresponding `LICENSE_PUBLIC_KEY` with buyer deployments.

2. Get your Braintree API keys (Control Panel -> Settings (gear) -> API ->
   API Keys). Start with a sandbox account (sandbox.braintreegateway.com)
   and set `BRAINTREE_ENVIRONMENT=sandbox`, `BRAINTREE_MERCHANT_ID`,
   `BRAINTREE_PUBLIC_KEY` and `BRAINTREE_PRIVATE_KEY`.

3. Create the four plans:

   ```sh
   cd backend && python scripts/create_braintree_plans.py
   ```

   It uses `PRICE_*` and `BILLING_CURRENCY`, creates the plans with the ids
   the backend expects by default (`crm-scoring-pro-monthly`, ...), and
   skips any that already exist. If you create plans by hand in the Control
   Panel (Subscriptions -> Plans) instead, either use those ids or set
   `BRAINTREE_PLAN_*` to yours.

4. Add the webhook. It's needed so renewals issue fresh keys. In the
   Control Panel, go to Settings -> Webhooks -> Create new webhook:
   - URL: `https://<your-backend>/api/billing/braintree/webhook`. It must
     be public HTTPS; `localhost` won't work.
   - Notifications: `Subscription Charged Successfully` and
     `Subscription Went Active`.
   - Use "Check URL" to confirm it answers. Signatures are verified with
     your API keys, so there's no separate webhook secret.

5. Configure SendGrid or SMTP so keys are delivered automatically. Without
   email settings, keys are still appended to
   `licensing/issued_licenses.jsonl` for you to send by hand.

6. Test a full purchase in sandbox with card `4111 1111 1111 1111`, any
   future expiry and any CVV. Then repeat steps 2-4 with your production
   account and `BRAINTREE_ENVIRONMENT=production`. Sandbox and production
   keys, plans and webhooks are all separate.

## How checkout works

Both the app (React frontend) and the storefront (`docs/index.html`) render
Braintree's Drop-in card form in-page:

1. `GET /api/billing/braintree/client-token` gives Drop-in a short-lived
   token. Drop-in tokenizes the card in Braintree's own iframes, so card
   details never reach this backend.
2. `POST /api/billing/braintree/subscribe` sends the one-time nonce, the
   buyer's email and the chosen plan. The backend creates a customer
   (verifying the card), starts the subscription and returns the key.
3. **Webhook**: every renewal, plus a fallback if the checkout response
   never reached the buyer.

Each billing period is keyed on the subscription id plus Braintree's
`paid_through_date`. Checkout and the first charge's webhook therefore
share a period and issue only one key.

## License validity

Keys last `LICENSE_VALIDITY_DAYS_MONTHLY` (default 35) or
`LICENSE_VALIDITY_DAYS_ANNUAL` (default 380) days. That covers one billing
period plus time for Braintree's payment retries.
