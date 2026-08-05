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

# --- Transport/network security (app/middleware.py, app/main.py) ---
# Redirects plain HTTP to HTTPS at the app level. Leave false for local dev
# (no TLS cert to redirect to) and for deployments where a proxy already
# handles this (Render does). Turn on only for a self-hosted deployment
# that terminates its own TLS with no proxy in front doing the redirect.
FORCE_HTTPS = os.getenv("FORCE_HTTPS", "false").lower() == "true"
# Trusts X-Forwarded-For/X-Forwarded-Proto from the immediate connecting
# peer -- required for rate limiting and HTTPS-detection to see the real
# client IP/scheme when running behind a reverse proxy (Render, nginx,
# Caddy...), since otherwise every request appears to come from the proxy
# itself. Only enable this when you control what's in front of this
# process -- an internet-facing uvicorn with this on lets any client spoof
# their own IP/scheme via those headers, defeating rate limiting entirely.
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"

# --- Rate limiting (app/middleware.py) ---
# slowapi/limits syntax: "<count>/<second|minute|hour|day>".
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
# Tighter limit for the expensive parse+enrich+score endpoints.
RATE_LIMIT_UPLOAD = os.getenv("RATE_LIMIT_UPLOAD", "10/minute")

# --- Upload limits (routers/leads.py, routers/churn.py) ---
# Rejected before parsing -- bounds worst-case memory/CPU from one upload,
# independent of the trial row cap below (which only applies unlicensed).
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
MAX_UPLOAD_ROWS = int(os.getenv("MAX_UPLOAD_ROWS", "50000"))

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
# Caps each /api/leads/upload call to at most this many rows while
# unlicensed (whether still within TRIAL_DAYS or not) -- lets a prospect
# judge scoring quality on a real sample of their own data without getting
# full free use of a large list. Licensed deployments have no cap.
TRIAL_MAX_LEADS_PER_UPLOAD = int(os.getenv("TRIAL_MAX_LEADS_PER_UPLOAD", "10"))

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
# Client-side token (Paddle dashboard: Developer Tools > Authentication >
# Client-side tokens tab -- a different, non-secret credential from
# PADDLE_API_KEY above). Only used to serve GET /api/billing/config, which
# the frontend reads to initialize Paddle.js's overlay checkout. Safe to
# expose to the browser; it can't create charges or read account data.
PADDLE_CLIENT_TOKEN = os.getenv("PADDLE_CLIENT_TOKEN", "")
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

# --- Polar (seller side, alternative to Paddle) ---
# Polar is also a merchant-of-record, added alongside Paddle (not instead of
# it) specifically for sellers Paddle can't serve either -- Polar pays out
# via Stripe Connect Express, whose supported *recipient* countries are
# broader than the countries Stripe itself supports for a direct merchant
# account (confirmed: Armenia is a supported Polar/Connect payout country
# even though it isn't a Stripe merchant country). See licensing/README.md.
POLAR_ACCESS_TOKEN = os.getenv("POLAR_ACCESS_TOKEN", "")
POLAR_WEBHOOK_SECRET = os.getenv("POLAR_WEBHOOK_SECRET", "")
# "sandbox" (default -- sandbox-api.polar.sh, a separate test org) or
# "production" (api.polar.sh).
POLAR_ENVIRONMENT = os.getenv("POLAR_ENVIRONMENT", "sandbox")
# Polar models each plan as its own Product (rather than one product with
# multiple Prices, as Paddle does) -- two Product ids here, one per plan.
POLAR_PRODUCT_ID_MONTHLY = os.getenv("POLAR_PRODUCT_ID_MONTHLY", "")
POLAR_PRODUCT_ID_ANNUAL = os.getenv("POLAR_PRODUCT_ID_ANNUAL", "")

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
