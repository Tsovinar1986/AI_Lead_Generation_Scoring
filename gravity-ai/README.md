# Gravity AI submission package

Packages the lead-scoring pipeline as a batch algorithm for the
[Gravity AI](https://gravity-ai.com) marketplace, per their
[build configuration](https://docs.gravity-ai.com/buildProcess/) and
[input/output handling](https://docs.gravity-ai.com/input-output) docs.

## What this is

Gravity AI runs algorithms as: `python <entry script> {input} {output}` inside
a Debian-based container it builds for you from an uploaded project. It is
**not** the same as the interactive FastAPI app in `backend/` — no live
endpoints to write, no Docker Compose to hand-roll. You provide an entry
script + `gravityai-build.json` + `requirements.txt`; Gravity AI builds the
container, exposes its own REST API (`/health`, `/data/add-job`, etc.), and
lists it on the marketplace after review.

`src/score_leads.py` reads a lead CSV/XLSX, runs it through the same
ingestion → enrichment → hybrid (rule + Claude) scoring → outreach-draft
pipeline as the web app, and writes a ranked CSV. It imports directly from
`backend/app/services/*` — no logic is duplicated.

## Building the submission zip

```
./build_package.sh
```

This copies `score_leads.py` plus the specific `backend/app` modules it
depends on (`config.py`, `models.py`, `llm/`, and the ingestion/enrichment/
scoring/outreach services — deliberately **not** `routers/`, `main.py`,
`storage.py`, `services/crm.py`, or `services/alerts.py`, which are specific
to the interactive web app and irrelevant to a batch algorithm run) into
`dist/package/`, then zips it to `dist/gravity-ai-lead-scoring.zip`. That zip
is what you upload to Gravity AI.

## Before uploading, verify against the live Gravity AI dashboard

Docs were correct as fetched, but two things are configured through Gravity
AI's upload wizard rather than a file in this repo, so confirm them there at
submission time:

- **Command line arguments**: set to `{input} {output}` (their docs describe
  this as a build-setting field, not a `gravityai-build.json` key).
- **Docker memory allocation**: size it for a pandas + Anthropic-SDK
  workload; their docs ask sellers to document this for buyers.

## Environment / credentials

Same auto-detecting pattern as the web app (see root `.env.example`) — set
whichever are available in the container's environment, the algorithm uses
live calls for those and falls back to deterministic mock data for the rest:

| Variable | Effect if set |
|---|---|
| `ANTHROPIC_API_KEY` | Real Claude scoring rationale + outreach drafts (else mock) |
| `APOLLO_API_KEY` | Real Apollo.io firmographic enrichment (else deterministic mock) |

(`HUBSPOT_*`, `SALESFORCE_*`, `SLACK_*` aren't used by this batch entry
point — CRM push and Slack alerts are interactive-app-only actions.)

## Local test before submitting

```
cd dist/package
pip install -r requirements.txt
python src/score_leads.py test_input.csv test_output.csv
cat test_output.csv
```

This is exactly the invocation Gravity AI's build system runs against
`test_input.csv` (per `gravityai-build.json`'s `Tests` entry) to validate the
algorithm before listing it.
