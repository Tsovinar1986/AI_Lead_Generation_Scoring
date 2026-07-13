"""Offline Ed25519 license verification (buyer side).

A self-hosted deployment sets LICENSE_KEY (issued after purchase, see
../licensing/issue_license.py) and LICENSE_PUBLIC_KEY (shipped with the app,
safe to commit -- it can only verify signatures, never create them). No
network call is made: the key is checked against the embedded public key,
so this works fully offline/air-gapped.

With no LICENSE_KEY set, verify_license() returns None and the app runs in
trial mode -- callers decide what that means (main.py only enforces it on
paid endpoints when LICENSE_REQUIRED=true), mirroring the
ANTHROPIC_API_KEY/APOLLO_API_KEY "degrade, don't crash" pattern used
elsewhere in this app.
"""

import base64
import json
import time
from dataclasses import dataclass

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from .config import LICENSE_KEY, LICENSE_PUBLIC_KEY


@dataclass
class LicenseInfo:
    customer_email: str
    plan: str
    expires_at: float | None


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded)


def verify_license() -> LicenseInfo | None:
    if not LICENSE_KEY or not LICENSE_PUBLIC_KEY:
        return None

    try:
        payload_b64, signature_b64 = LICENSE_KEY.split(".", 1)
        payload = _b64decode(payload_b64)
        signature = _b64decode(signature_b64)
        VerifyKey(_b64decode(LICENSE_PUBLIC_KEY)).verify(payload, signature)
        data = json.loads(payload)
    except (ValueError, BadSignatureError, KeyError, json.JSONDecodeError):
        return None

    expires_at = data.get("expires_at")
    if expires_at and time.time() > expires_at:
        return None

    return LicenseInfo(
        customer_email=data["customer_email"],
        plan=data.get("plan", "standard"),
        expires_at=expires_at,
    )
