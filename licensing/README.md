# Selling this as a self-hosted product

The seller storefront sells Pro and Advanced as PayPal Subscriptions, each
billed monthly or annually. Starter is free and has no PayPal plan.

When a subscription activates, the backend signs an Ed25519 license key,
logs it for idempotency and emails it to the buyer. Buying inside the app
also shows the key on screen. Every renewal payment issues and emails a
fresh key. Each key stays valid a little past the next billing date, so a
cancelled subscription simply stops receiving new keys.

## Setup

1. Generate the signing keypair once:

   ```sh
   python licensing/generate_keypair.py
   ```

   Keep `LICENSE_PRIVATE_KEY` only on the seller deployment. Ship the
   corresponding `LICENSE_PUBLIC_KEY` with buyer deployments.

2. Create a PayPal app (developer.paypal.com -> Apps & Credentials). Start
   in Sandbox and set `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` and
   `PAYPAL_ENVIRONMENT=sandbox`.

3. Create the product and the four plans:

   ```sh
   cd backend && python scripts/create_paypal_plans.py
   ```

   It uses `PAYPAL_PRICE_*` and `PAYPAL_CURRENCY` and prints the lines to
   copy into your settings:

   ```dotenv
   PAYPAL_PLAN_PRO_MONTHLY=P-...
   PAYPAL_PLAN_PRO_ANNUAL=P-...
   PAYPAL_PLAN_ADVANCED_MONTHLY=P-...
   PAYPAL_PLAN_ADVANCED_ANNUAL=P-...
   ```

   You can also create the plans by hand in the PayPal dashboard
   (Pay & Get Paid -> Subscriptions) and copy their IDs.

4. Add the webhook. It's needed so renewals issue fresh keys. In your
   PayPal app, go to Webhooks -> Add Webhook:
   - URL: `https://<your-backend>/api/billing/paypal/webhook`. It must be
     public HTTPS; `localhost` won't work.
   - Events: `Billing subscription activated` (`BILLING.SUBSCRIPTION.ACTIVATED`)
     and `Payment sale completed` (`PAYMENT.SALE.COMPLETED`).
   - Copy the Webhook ID into `PAYPAL_WEBHOOK_ID`.

   Nothing is configured on GitHub for payments.

5. Set `STOREFRONT_URL` (default `https://crmscoring.com`). Buyers using the
   storefront's redirect checkout land on its `thank-you.html`.

6. Configure SendGrid or SMTP so keys are delivered automatically. Without
   email settings, keys are still appended to
   `licensing/issued_licenses.jsonl` for you to send by hand.

7. Test a full purchase with a Sandbox buyer account. Then repeat steps 2-4
   against a live app with `PAYPAL_ENVIRONMENT=production`. Sandbox and
   live plans, credentials and webhooks are all separate.

## How checkout works

- **In the app** (React frontend): PayPal's JS SDK buttons open a PayPal
  popup. After approval the app calls
  `POST /api/billing/paypal/subscription/activate`, which checks the
  subscription with PayPal and returns the key.
- **Storefront** (`docs/index.html`): `POST /api/billing/paypal/checkout`
  creates the subscription and redirects to PayPal. PayPal sends the buyer
  back to `GET /api/billing/paypal/return`, which activates it and then
  redirects to `thank-you.html`.
- **Webhook**: covers buyers who close the tab before coming back, plus
  every renewal.

Each billing period is keyed on the subscription id plus PayPal's
`next_billing_time`. The popup, the redirect and the webhooks can therefore
all fire for the same payment and still issue only one key.

## License validity

Keys last `LICENSE_VALIDITY_DAYS_MONTHLY` (default 35) or
`LICENSE_VALIDITY_DAYS_ANNUAL` (default 380) days. That covers one billing
period plus time for PayPal's payment retries.
