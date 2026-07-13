"""Offline Ed25519 license verification (buyer side).

A self-hosted deployment sets LICENSE_KEY (issued after purchase, see
../licensing/issue_license.py) and LICENSE_PUBLIC_KEY (shipped with the app,
safe to commit -- it can only verify signatures, never create them). No
network call is made: the key is checked against the embedded public key,
so this works fully offline/air-gapped.

With no LICENSE_KEY set, check_license() reports NONE and the app runs in
trial mode -- callers decide what that means (main.py only enforces it on
paid endpoints when LICENSE_REQUIRED=true), mirroring the
ANTHROPIC_API_KEY/APOLLO_API_KEY "degrade, don't crash" pattern used
elsewhere in this app.

NONE is deliberately distinguished from INVALID/EXPIRED: a buyer who already
paid but has a stale or malformed key should never see the same "you're on
a trial, buy a license" messaging as someone who's never purchased --
that reads as "your payment didn't go through" and risks a double-charge.
"""

import base64
import json
import time
from dataclasses import dataclass
from enum import Enum

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from .config import LICENSE_KEY, LICENSE_PUBLIC_KEY


class LicenseState(Enum):
    NONE = "none"        # no LICENSE_KEY configured at all -- genuine trial
    INVALID = "invalid"  # LICENSE_KEY set but malformed or fails signature check
    EXPIRED = "expired"  # valid signature, past its expires_at
    VALID = "valid"


@dataclass
class LicenseInfo:
    customer_email: str
    plan: str
    expires_at: float | None


@dataclass
class LicenseCheck:
    state: LicenseState
    info: LicenseInfo | None = None


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded)


def check_license() -> LicenseCheck:
    if not LICENSE_KEY:
        return LicenseCheck(LicenseState.NONE)
    if not LICENSE_PUBLIC_KEY:
        return LicenseCheck(LicenseState.INVALID)

    try:
        payload_b64, signature_b64 = LICENSE_KEY.split(".", 1)
        payload = _b64decode(payload_b64)
        signature = _b64decode(signature_b64)
        VerifyKey(_b64decode(LICENSE_PUBLIC_KEY)).verify(payload, signature)
        data = json.loads(payload)
        info = LicenseInfo(
            customer_email=data["customer_email"],
            plan=data.get("plan", "standard"),
            expires_at=data.get("expires_at"),
        )
    except (ValueError, BadSignatureError, KeyError, json.JSONDecodeError):
        return LicenseCheck(LicenseState.INVALID)

    if info.expires_at and time.time() > info.expires_at:
        return LicenseCheck(LicenseState.EXPIRED, info)

    return LicenseCheck(LicenseState.VALID, info)


def verify_license() -> LicenseInfo | None:
    """Pass/fail helper for callers that only care whether to gate a feature
    (the 402 check in routers/leads.py). Use check_license() directly when
    the caller needs to explain *why* -- e.g. the frontend's license banner.
    """
    check = check_license()
    return check.info if check.state == LicenseState.VALID else None
