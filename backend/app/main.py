from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from loguru import logger

from .config import CORS_ALLOWED_ORIGINS
from .licensing import LicenseState, check_license, trial_days_left, verify_license
from .logging_config import configure_logging
from .routers import actions, billing, churn, leads

configure_logging()

# When frontend/dist exists (`npm run build`), this same process serves it
# too -- one process, one port, nothing else to run. See run-prod.sh. In dev
# mode (npm run dev on its own Vite server) dist won't exist, so this is
# simply skipped and only the API is served here, exactly as before.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    license_info = verify_license()
    if license_info:
        logger.info("Licensed to {} ({} plan)", license_info.customer_email, license_info.plan)
    else:
        logger.info("No valid LICENSE_KEY set — running in trial mode.")
    yield


app = FastAPI(title="AI Lead Generation & Scoring Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    # Browsers hide all response headers from JS by default except a small
    # built-in safelist -- these carry the trial upload cap so the frontend
    # can tell the user why their file got truncated.
    expose_headers=["X-Trial-Limited-Rows", "X-Trial-Total-Rows"],
)

app.include_router(leads.router)
app.include_router(actions.router)
app.include_router(actions.alerts_router)
app.include_router(billing.router)
app.include_router(churn.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/license")
def license_status():
    check = check_license()
    if check.state == LicenseState.VALID:
        return {
            "licensed": True,
            "customer_email": check.info.customer_email,
            "plan": check.info.plan,
            "expires_at": check.info.expires_at,
        }
    # INVALID/EXPIRED still carry customer_email/plan when the key at least
    # parsed, so the frontend can say "your license for X expired" instead
    # of generic trial messaging -- a buyer who already paid should never
    # see the same "buy a license" copy as someone who never did. NONE further
    # splits into "trial" vs "trial_expired" so a still-evaluating prospect
    # doesn't see the same hard-stop copy as one whose grace period is over.
    days_left = trial_days_left() if check.state == LicenseState.NONE else None
    reason = check.state.value
    if check.state == LicenseState.NONE:
        reason = "trial" if days_left > 0 else "trial_expired"
    return {
        "licensed": False,
        "reason": reason,
        "customer_email": check.info.customer_email if check.info else None,
        "plan": check.info.plan if check.info else None,
        "trial_days_left": round(days_left, 1) if days_left is not None else None,
    }


if FRONTEND_DIST.is_dir():
    # Registered last so every /api/* route above already matched first --
    # this only ever runs for paths none of those routers claimed. Serves a
    # built asset by exact path if one exists, otherwise falls back to
    # index.html so client-side routes (e.g. /purchase-complete) still work
    # on a hard refresh.
    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
