# AI Lead Generation & Scoring Agent (B2B)

An agent pipeline that takes B2B leads from multiple sources, enriches them with
firmographic and behavioral signals, scores them using a hybrid rule-based + LLM
model, and acts on the top-ranked leads (outreach drafts, CRM sync, alerts).

## Running it

`./run.sh` (or `run.bat` on Windows) starts backend + frontend as two dev
servers with hot reload; `./run-prod.sh` (`run-prod.bat`) builds the
frontend once and runs a single merged process on one port — see the root
[README.md](README.md#running-it-two-modes) for both, and how to tell it's
actually working versus just "a server started."

```
# backend (from repo root)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000

# frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173, upload `backend/data/sample_leads.csv` (or your
own CRM export), and the ranked/scored leads appear immediately — no API
keys required. Enrichment (Apollo), CRM push (HubSpot/Salesforce), and Slack
alerts each auto-detect their credentials at startup: with none set they run
on deterministic mock data/logging by default; drop real keys into a `.env`
(see `.env.example`) and the exact same code path calls the live APIs
instead — no code changes needed either way, and a failed live call falls
back to the mock for that lead rather than breaking the run.

## Pipeline

**1. Ingestion**
- Bulk lead import from CRM exports (CSV/XLSX).
- Live pull from HubSpot/Salesforce via API for existing pipeline records.
- Company/domain lists submitted directly for cold enrichment.

**2. Enrichment**
- Third-party firmographic APIs (Apollo-style: company size, industry, revenue,
  tech stack, contact/title data).
- Company website scraping for signals not available via API (careers page
  activity/hiring signal, product pages, tech stack fingerprinting, about-page
  positioning).
- Results normalized into a single `EnrichedLead` record (pydantic model).

**3. Scoring (hybrid)**
- **Rule-based layer:** weighted scoring across configurable firmographic fit
  criteria (industry match, company size band, revenue band, tech stack match,
  geography, title seniority of contact). Produces a transparent numeric
  `fit_score` (0–100) with a per-criterion breakdown.
- **LLM layer:** Claude reads the enriched profile + rule-based breakdown and
  produces a qualitative assessment — a `conversion_likelihood` rating and a
  short rationale, catching context the rules can't (e.g. recent funding news,
  hiring surges, competitor mentions).
- Final `combined_score` blends both layers; leads are ranked and bucketed
  (Hot / Warm / Cold).

**4. Output / Actions**
- **Ranked report:** Streamlit dashboard + CSV export of all scored leads,
  sortable/filterable by score, bucket, industry, source.
- **Auto-drafted outreach:** for Hot/Warm leads, Claude drafts a personalized
  first-touch email or LinkedIn message referencing the specific fit signals
  found during enrichment.
- **CRM push:** scores, bucket, rationale, and draft outreach get written back
  to HubSpot/Salesforce as custom fields/tasks so sales has full context
  in-platform.
- **Alerts:** Slack (and/or email) notification the moment a lead crosses the
  "Hot" threshold, so sales can act while the signal is fresh.

## Required configuration (`.env`)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | LLM scoring layer + outreach drafting |
| `APOLLO_API_KEY` (or chosen enrichment provider) | Firmographic/contact enrichment |
| `HUBSPOT_ACCESS_TOKEN` / `SALESFORCE_*` | CRM read/write |
| `SLACK_BOT_TOKEN` + channel ID | Hot-lead alerts |
| `SMTP_*` (optional) | Email alerts if Slack isn't used |

## Scheduling

APScheduler drives recurring runs (e.g. nightly re-enrichment of active
pipeline, hourly scoring pass on newly added leads) so the dashboard stays
current without manual re-triggering.

## Architecture

- **backend/** — FastAPI app (`app/main.py`). Ingestion (`services/ingestion.py`),
  enrichment (`services/enrichment.py`, Apollo with mock fallback), hybrid
  scoring (`services/scoring.py`), outreach drafting (`services/outreach.py`),
  and CRM/Slack integrations (`services/crm.py`, `services/alerts.py`) are
  each isolated behind a single function that auto-switches between the live
  API and a mock based on which keys are present in `.env`. Leads/alerts
  persist to SQLite (`storage.py`, path set by `DATABASE_PATH`) — single-file,
  single-tenant, fine for one self-hosted buyer, not a multi-user setup.
  `backend/tests/` has the pytest suite (`pytest -q` from `backend/`).
- **frontend/** — React + Vite + TypeScript SPA. Upload panel, a ranked/
  filterable leads table, a detail drawer (firmographics, score breakdown,
  LLM rationale, outreach draft generation, CRM push button), a live
  Slack-alerts panel, and a license/billing banner. `npm test` runs the
  Vitest suite.
- **`.github/workflows/ci.yml`** — runs both suites (and the frontend build)
  on every push/PR.

## Selling this

Two sale paths are built out on top of the same pipeline:

- **`gravity-ai/`** — packages the pipeline as a batch algorithm for the
  Gravity AI marketplace (`gravity-ai/README.md`).
- **`licensing/`** — Stripe checkout + an offline-verifiable Ed25519 license
  key, for selling this app directly as self-hosted software from your own
  site (`licensing/README.md`, which also has the go-to-market sequencing:
  direct sale → RapidAPI → Gravity AI → HubSpot/Salesforce marketplaces →
  AWS Marketplace/AppSumo, roughly cheapest/fastest to most involved).

## Not in scope (v1)

- Training a custom ML conversion-prediction model (would need labeled
  historical won/lost data — can be added later as a third scoring layer).
- Outbound sending automation (drafts are generated for human review/send,
  not auto-sent, to avoid compliance/spam risk).
