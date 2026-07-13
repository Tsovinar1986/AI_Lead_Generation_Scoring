#!/usr/bin/env python3
"""Seller-side license issuance. Never shipped to buyers.

Called by backend/app/routers/billing.py's Stripe webhook when a payment
succeeds; also runnable by hand for manual/comp licenses:

    LICENSE_PRIVATE_KEY=... python issue_license.py \\
        --email buyer@example.com --plan pro --days 365

Prints the LICENSE_KEY string the buyer puts in their .env as LICENSE_KEY.
Requires LICENSE_PRIVATE_KEY in the environment (see generate_keypair.py --
run that once, first).
"""

import argparse
import base64
import json
import os
import time

from nacl.signing import SigningKey


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded)


def issue_license(email: str, plan: str, private_key_b64: str, days: int | None) -> str:
    signing_key = SigningKey(_b64decode(private_key_b64))

    payload = {
        "customer_email": email,
        "plan": plan,
        "issued_at": time.time(),
        "expires_at": (time.time() + days * 86400) if days else None,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    signature = signing_key.sign(payload_bytes).signature

    return f"{_b64encode(payload_bytes)}.{_b64encode(signature)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--plan", default="standard")
    parser.add_argument("--days", type=int, default=None, help="omit for a perpetual license")
    args = parser.parse_args()

    private_key_b64 = os.environ.get("LICENSE_PRIVATE_KEY", "")
    if not private_key_b64:
        raise SystemExit(
            "LICENSE_PRIVATE_KEY not set. Run generate_keypair.py once and export it."
        )

    print(issue_license(args.email, args.plan, private_key_b64, args.days))


if __name__ == "__main__":
    main()
