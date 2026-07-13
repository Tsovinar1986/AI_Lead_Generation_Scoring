from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from loguru import logger

from .config import CORS_ALLOWED_ORIGINS
from .licensing import verify_license
from .logging_config import configure_logging
from .routers import actions, billing, leads

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
)

app.include_router(leads.router)
app.include_router(actions.router)
app.include_router(actions.alerts_router)
app.include_router(billing.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/license")
def license_status():
    license_info = verify_license()
    if license_info is None:
        return {"licensed": False}
    return {
        "licensed": True,
        "customer_email": license_info.customer_email,
        "plan": license_info.plan,
        "expires_at": license_info.expires_at,
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
