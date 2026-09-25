# Selling this as a self-hosted product

The seller storefront uses PayPal's Orders API to take one-time payments.
After PayPal redirects the buyer back to `thank-you.html`, the backend
captures the order, signs an Ed25519 license key, records the order id for
idempotency, and emails the key when email delivery is configured.

## Setup

1. Generate the signing keypair once:

   ```sh
   python licensing/generate_keypair.py
   ```

   Keep `LICENSE_PRIVATE_KEY` only on the seller deployment. Ship the
   corresponding `LICENSE_PUBLIC_KEY` with buyer deployments.

2. Create a PayPal developer application. Start with Sandbox, then switch
   `PAYPAL_ENVIRONMENT=production` after a complete test purchase.

3. Configure the seller deployment:

   ```dotenv
   LICENSE_PRIVATE_KEY=
   PAYPAL_CLIENT_ID=
   PAYPAL_CLIENT_SECRET=
   PAYPAL_ENVIRONMENT=sandbox
   PAYPAL_CURRENCY=USD
   PAYPAL_PRICE_MONTHLY=20.00
   PAYPAL_PRICE_ANNUAL=192.00
   PAYPAL_PRICE_ADVANCED_MONTHLY=40.00
   PAYPAL_PRICE_ADVANCED_ANNUAL=384.00
   APP_BASE_URL=https://www.example.com
   ```

   Prices are decimal amounts in the configured currency. PayPal credentials
   remain server-side; only the approval URL is sent to the browser.

4. Run the storefront backend and frontend. The purchase buttons call
   `POST /api/billing/paypal/checkout`, redirect the buyer to PayPal, and the
   return page calls `POST /api/billing/paypal/capture`.

5. Configure SendGrid or SMTP if license keys should be delivered
   automatically. Without email settings, keys are still appended to
   `licensing/issued_licenses.jsonl` for manual delivery.

## License validity

Monthly and annual captures issue keys with the windows configured by
`LICENSE_VALIDITY_DAYS_MONTHLY` and `LICENSE_VALIDITY_DAYS_ANNUAL`. Captures
are idempotent by PayPal order id, so refreshing the return page cannot issue
another key for the same payment.
