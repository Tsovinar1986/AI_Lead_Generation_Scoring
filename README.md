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

## Running it: two modes

**Dev mode** — backend and frontend as two separate servers with hot reload.
This is what you want while making changes.

```
./run.sh          # macOS/Linux — installs deps, starts both, Ctrl+C stops both
run.bat           # Windows    — same, opens two windows
```

or by hand:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd backend && uvicorn app.main:app --reload --port 8081

# separate terminal
cd frontend && npm install && npm run dev
```

Open **http://localhost:5000** (the Vite dev server; it proxies `/api/*`
calls to the backend on :8081, see `frontend/vite.config.ts`).

**Merged/production mode** — one process, one port. This is what a
self-hosted buyer actually runs: FastAPI builds+serves the frontend itself
(`backend/app/main.py`'s `FRONTEND_DIST` handling), so there's no separate
frontend server at all.

```
./run-prod.sh      # macOS/Linux
run-prod.bat       # Windows
```

Open **http://localhost:8081** — same origin serves both the UI and the API.

**Docker** — same merged mode, containerized:

```
docker build -t ai-lead-scoring .
docker run --rm -p 8081:8081 --env-file .env -v $(pwd)/backend/data:/app/backend/data ai-lead-scoring
```

The volume mount matters: `backend/data/app.db` is where leads/alerts/trial
state persist, and without mounting it a removed container loses everything
(including the trial clock, which would otherwise just restart itself, one
free trial per container recreation).

**How to tell it's actually working**: hit `/api/health` (`{"status":"ok"}`)
directly, then in the browser upload `backend/data/sample_leads.csv` and
confirm ranked leads + Slack-alert cards appear — that exercises the full
upload → enrich → score → store round trip, not just that a server is up.
Leads/alerts persist to a local SQLite file (`DATABASE_PATH`, default
`backend/data/app.db`) so they survive a restart in either mode.

## What's in here

- **`backend/`** — FastAPI app: ingestion, enrichment, hybrid scoring,
  outreach drafting, CRM push, Slack alerts, and Paddle-based licensing.
- **`frontend/`** — React SPA: upload panel, ranked/filterable leads table,
  a detail drawer (firmographics, score breakdown, LLM rationale, outreach
  draft, CRM push), a live Slack-alerts panel, and a license/billing banner.
- **`licensing/`** — Paddle Checkout + an offline-verifiable Ed25519 license
  key, for selling this app directly as self-hosted software.

See **[DESCRIPTION.md](DESCRIPTION.md)** for the full pipeline architecture
and scoring model, and **[licensing/README.md](licensing/README.md)** for
the go-to-market sequencing across sale channels.

## Testing

```
pip install -r requirements-dev.txt
cd backend && pytest -q

cd frontend && npm test        # Vitest
npm run build                  # tsc + production build
```

`.github/workflows/ci.yml` runs both suites plus the frontend build on every
push/PR.

## Deploying (from this GitHub repo)

`render.yaml` is a Render Blueprint — Render builds the `Dockerfile` above
directly from this repo and redeploys automatically on every push to
`main`, so there's no separate CI/CD step to maintain. One-time setup:

1. Create a free account at [render.com](https://render.com) and connect
   your GitHub account.
2. **New +** → **Blueprint** → pick this repo. Render reads `render.yaml`
   and shows every env var it needs.
3. Fill in the secrets it prompts for (Paddle keys, `LICENSE_PRIVATE_KEY`,
   any of the optional integration keys you have) — these are entered once
   in Render's dashboard and never touch git. Leave any of the optional
   integration keys blank to keep that feature on mock data for now.
4. Deploy. Render gives you a `https://crm-scoring-xxxx.onrender.com` URL —
   confirm `/api/health` responds, then update `CORS_ALLOWED_ORIGINS` (in
   Render's dashboard) and the landing page's demo widget
   (`docs/index.html`'s `TRY_UPLOAD_API_BASE`) to point at it instead of any
   temporary tunnel.

**Free tier caveats**: the instance spins down after 15 minutes idle (first
request after that takes ~30-50s to wake it back up), and there's no
persistent disk — the SQLite file resets on every redeploy/periodic
restart, so leads/trial state won't survive across deploys. Both are
one-click upgrades in Render's dashboard once there's a paying customer to
justify it; fine as-is for a public demo/beta.

## Configuration

Copy `.env.example` to `.env` (and `frontend/.env.example` to
`frontend/.env` if the backend isn't on `localhost:8081`) and fill in
whichever keys are available. Every integration degrades gracefully without
one — see `.env.example` for what each variable unlocks.
