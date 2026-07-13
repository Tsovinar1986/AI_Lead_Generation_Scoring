# AI Lead Generation & Scoring Agent

A B2B lead-scoring pipeline: upload a CRM export, get every lead enriched
with firmographic/behavioral signals, scored by a hybrid rule-based + Claude
model, ranked into Hot/Warm/Cold, and (for the hot ones) a drafted outreach
message and a CRM push — all from one screen.

FastAPI backend, React + Vite + TypeScript frontend. Every third-party
integration (Claude, Apollo enrichment, HubSpot/Salesforce push, Slack
alerts) auto-detects its credentials: set the key and it makes the real
call, leave it unset and it runs on deterministic mock data — so the whole
thing works end to end with zero API keys for local eval, and flips to
live behavior with zero code changes once keys are added.

## Quickstart

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000

# separate terminal
cd frontend && npm install && npm run dev
```

Open http://localhost:5173, upload `backend/data/sample_leads.csv` (or your
own CRM export), and ranked/scored leads appear immediately.

## What's in here

- **`backend/`** — FastAPI app: ingestion, enrichment, hybrid scoring,
  outreach drafting, CRM push, Slack alerts, and Stripe-based licensing.
- **`frontend/`** — React SPA: upload panel, ranked/filterable leads table,
  a detail drawer (firmographics, score breakdown, LLM rationale, outreach
  draft, CRM push), a live Slack-alerts panel, and a license/billing banner.
- **`gravity-ai/`** — packages the scoring pipeline as a batch algorithm for
  the [Gravity AI](https://gravity-ai.com) marketplace.
- **`licensing/`** — Stripe Checkout + an offline-verifiable Ed25519 license
  key, for selling this app directly as self-hosted software.

See **[DESCRIPTION.md](DESCRIPTION.md)** for the full pipeline architecture
and scoring model, **[TODO.md](TODO.md)** for what's verified vs. what still
needs testing against live accounts before going to production, and
**[licensing/README.md](licensing/README.md)** for the go-to-market
sequencing across sale channels.

## Configuration

Copy `.env.example` to `.env` (and `frontend/.env.example` to
`frontend/.env` if the backend isn't on `localhost:8000`) and fill in
whichever keys are available. Every integration degrades gracefully without
one — see `.env.example` for what each variable unlocks.
