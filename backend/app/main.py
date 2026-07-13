from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import CORS_ALLOWED_ORIGINS
from .licensing import verify_license
from .routers import actions, billing, leads

app = FastAPI(title="AI Lead Generation & Scoring Agent")

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


@app.on_event("startup")
def log_license_status():
    license_info = verify_license()
    if license_info:
        logger.info("Licensed to {} ({} plan)", license_info.customer_email, license_info.plan)
    else:
        logger.info("No valid LICENSE_KEY set — running in trial mode.")


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
