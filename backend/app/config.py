import os

from dotenv import load_dotenv

load_dotenv()

# SQLite file leads/alerts persist to, relative to the backend/ working
# directory by default. Single-file, single-tenant -- fine for one
# self-hosted buyer's data, not a multi-user setup.
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/app.db")

# "text" (human-readable, for local dev) or "json" (one JSON object per line
# on stdout, for log aggregators like CloudWatch/Datadog/Loki when this runs
# in a container).
LOG_FORMAT = os.getenv("LOG_FORMAT", "text")

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
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5000").split(",")
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
# When true, endpoints that do real work (lead upload/scoring) 402 immediately
# without a valid LICENSE_KEY -- skips the TRIAL_DAYS grace period entirely.
# Leave false (default) so a fresh deployment gets TRIAL_DAYS of unlicensed
# use before it starts enforcing (see TRIAL_DAYS below).
LICENSE_REQUIRED = os.getenv("LICENSE_REQUIRED", "false").lower() == "true"
# How many days a deployment with no LICENSE_KEY may keep using paid
# endpoints before it starts 402ing. The clock starts on this deployment's
# first request that checks it (storage.get_or_start_trial), not on install,
# and persists in the same SQLite file as everything else -- so it survives
# restarts and can't be reset by just restarting the process.
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "3"))

# --- Licensing (seller side) ---
# Only used by routers/billing.py, which the seller runs on their own
# storefront deployment -- buyers' self-hosted instances never need these.
# Paddle (not Stripe): Paddle is a merchant-of-record, so it also handles
# global sales tax/VAT, and its seller-eligibility list is broader than
# Stripe's -- notably it works for sellers Stripe doesn't support. Card,
# PayPal, Apple Pay, and Google Pay all show up automatically on Paddle's
# hosted checkout for eligible buyers; PayPal specifically may need enabling
# once in Paddle's dashboard (Checkout > Payment methods) -- see
# licensing/README.md.
LICENSE_PRIVATE_KEY = os.getenv("LICENSE_PRIVATE_KEY", "")
PADDLE_API_KEY = os.getenv("PADDLE_API_KEY", "")
PADDLE_WEBHOOK_SECRET = os.getenv("PADDLE_WEBHOOK_SECRET", "")
# "sandbox" (default, for testing against a Paddle sandbox account -- a
# completely separate account/API host from production) or "production".
PADDLE_ENVIRONMENT = os.getenv("PADDLE_ENVIRONMENT", "sandbox")
# Two recurring Paddle Prices (format pri_...) on the same product -- see
# licensing/README.md for suggested amounts ($30/mo, discounted annual) and
# how to create them.
PADDLE_PRICE_ID_MONTHLY = os.getenv("PADDLE_PRICE_ID_MONTHLY", "")
PADDLE_PRICE_ID_ANNUAL = os.getenv("PADDLE_PRICE_ID_ANNUAL", "")
# Licenses are issued with an expiry this many days out, not a perpetual
# one -- since an already-issued offline key can't be revoked if a payment
# fails or a subscription is cancelled, this bounds how long a lapsed
# subscriber keeps working. Every transaction.completed webhook (fired for
# both the first payment and every renewal) re-issues a fresh one, so an
# active subscriber never notices; comfortably longer than one billing
# period to tolerate retry/dunning delays. Separate windows for monthly vs.
# annual since "comfortably longer than one billing period" means something
# very different for each.
LICENSE_VALIDITY_DAYS_MONTHLY = int(os.getenv("LICENSE_VALIDITY_DAYS_MONTHLY", "35"))
LICENSE_VALIDITY_DAYS_ANNUAL = int(os.getenv("LICENSE_VALIDITY_DAYS_ANNUAL", "380"))

# --- Email delivery (seller side) ---
# Sends issued license keys to buyers automatically. Without either of these
# set, keys are still issued and logged/appended to
# licensing/issued_licenses.jsonl -- just not emailed, so send them by hand.
# SendGrid is tried first if configured (better deliverability/analytics at
# scale); SMTP is the zero-third-party-account fallback.
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "")

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
