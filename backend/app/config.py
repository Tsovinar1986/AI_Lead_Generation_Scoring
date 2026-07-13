import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
SALESFORCE_USERNAME = os.getenv("SALESFORCE_USERNAME", "")
SALESFORCE_PASSWORD = os.getenv("SALESFORCE_PASSWORD", "")
SALESFORCE_SECURITY_TOKEN = os.getenv("SALESFORCE_SECURITY_TOKEN", "")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")

# Comma-separated list of frontend origins allowed to call this API. Defaults
# to the local Vite dev server; a production deploy must set this to its
# real frontend origin(s) or the browser will block every request with CORS.
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# --- Licensing (buyer side) ---
# A signed key issued after purchase (see licensing/issue_license.py). Set by
# whoever self-hosts this app. Verified offline against LICENSE_PUBLIC_KEY --
# no phone-home required.
LICENSE_KEY = os.getenv("LICENSE_KEY", "")
# The seller's Ed25519 public key (base64), baked in at ship time so a buyer's
# instance can verify a license without contacting anything. Safe to commit;
# it can only verify signatures, not create them.
LICENSE_PUBLIC_KEY = os.getenv("LICENSE_PUBLIC_KEY", "")
# When true, endpoints that do real work (lead upload/scoring) 402 until a
# valid LICENSE_KEY is present. Leave false for local dev/eval.
LICENSE_REQUIRED = os.getenv("LICENSE_REQUIRED", "false").lower() == "true"

# --- Licensing (seller side) ---
# Only used by routers/billing.py, which the seller runs on their own
# storefront deployment -- buyers' self-hosted instances never need these.
LICENSE_PRIVATE_KEY = os.getenv("LICENSE_PRIVATE_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:5173/purchase-complete")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "http://localhost:5173/")
# "subscription" (recurring price, license auto-renews via the invoice.paid
# webhook each billing cycle) or "payment" (one-time price, perpetual license
# issued once). Must match how STRIPE_PRICE_ID was created in the Stripe
# dashboard.
STRIPE_BILLING_MODE = os.getenv("STRIPE_BILLING_MODE", "subscription")
# Subscription licenses are issued with an expiry this many days out, not a
# perpetual one -- since an already-issued offline key can't be revoked if a
# payment fails or a subscription is cancelled, this bounds how long a lapsed
# subscriber keeps working. invoice.paid re-issues a fresh one every cycle,
# so an active subscriber never notices; comfortably longer than one billing
# period to tolerate Stripe retry/dunning delays.
LICENSE_VALIDITY_DAYS = int(os.getenv("LICENSE_VALIDITY_DAYS", "35"))

# --- Email delivery (seller side) ---
# Sends issued license keys to buyers automatically. Without these set, keys
# are still issued and logged/appended to licensing/issued_licenses.jsonl --
# just not emailed, so send them by hand.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")

# Ideal Customer Profile used by the rule-based scorer. Edit to match the
# business this instance is generating leads for.
ICP = {
    "target_industries": ["SaaS", "Fintech", "Healthcare Tech", "E-commerce"],
    "employee_range": (50, 1500),
    "revenue_range_usd": (5_000_000, 250_000_000),
    "target_tech_stack": ["Salesforce", "HubSpot", "AWS", "Snowflake", "Stripe"],
    "target_geographies": ["United States", "Canada", "United Kingdom"],
    "decision_maker_titles": [
        "ceo", "cfo", "coo", "cto", "cmo", "chief",
        "vp", "vice president", "head of", "director",
    ],
}

# Rule-based scoring weights, must sum to 100.
SCORING_WEIGHTS = {
    "industry_match": 20,
    "company_size_fit": 20,
    "revenue_fit": 15,
    "tech_stack_match": 15,
    "geography_fit": 10,
    "title_seniority": 10,
    "hiring_signal": 10,
}

# Blend of rule-based fit_score vs LLM conversion_likelihood into combined_score.
RULE_WEIGHT = 0.6
LLM_WEIGHT = 0.4

BUCKET_THRESHOLDS = {"hot": 75, "warm": 50}
