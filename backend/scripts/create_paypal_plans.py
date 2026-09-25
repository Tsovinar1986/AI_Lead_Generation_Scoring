#!/usr/bin/env python3
"""Creates the PayPal product and the four subscription plans (Pro/Advanced x
monthly/annual) from the PAYPAL_* settings in .env. Run once per PayPal
environment (sandbox, then production):

    cd backend && python scripts/create_paypal_plans.py

Prints the PAYPAL_PLAN_* lines to paste into .env / your host's env vars.
Starter is free and has no plan. Running it again creates new plans rather
than reusing old ones -- PayPal plan prices can't be changed after
subscribers join, so a price change means new plans anyway.
"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import (  # noqa: E402
    PAYPAL_CURRENCY,
    PAYPAL_ENVIRONMENT,
    PAYPAL_PRICE_ADVANCED_ANNUAL,
    PAYPAL_PRICE_ADVANCED_MONTHLY,
    PAYPAL_PRICE_ANNUAL,
    PAYPAL_PRICE_MONTHLY,
)
from app.routers.billing import _paypal_api_base, _paypal_headers  # noqa: E402

PLANS = [
    ("PAYPAL_PLAN_PRO_MONTHLY", "Pro (monthly)", "MONTH", PAYPAL_PRICE_MONTHLY),
    ("PAYPAL_PLAN_PRO_ANNUAL", "Pro (annual)", "YEAR", PAYPAL_PRICE_ANNUAL),
    ("PAYPAL_PLAN_ADVANCED_MONTHLY", "Advanced (monthly)", "MONTH", PAYPAL_PRICE_ADVANCED_MONTHLY),
    ("PAYPAL_PLAN_ADVANCED_ANNUAL", "Advanced (annual)", "YEAR", PAYPAL_PRICE_ADVANCED_ANNUAL),
]


def _post(path: str, body: dict) -> dict:
    response = requests.post(f"{_paypal_api_base()}{path}", headers=_paypal_headers(), json=body, timeout=15)
    if not response.ok:
        sys.exit(f"PayPal {path} failed: {response.status_code} {response.text}")
    return response.json()


def main() -> None:
    print(f"Creating plans in PayPal {PAYPAL_ENVIRONMENT}...", file=sys.stderr)
    product = _post(
        "/v1/catalogs/products",
        {"name": "CRM Scoring", "type": "SERVICE", "category": "SOFTWARE"},
    )
    for env_key, name, unit, price in PLANS:
        plan = _post(
            "/v1/billing/plans",
            {
                "product_id": product["id"],
                "name": f"CRM Scoring {name}",
                "status": "ACTIVE",
                "billing_cycles": [
                    {
                        "frequency": {"interval_unit": unit, "interval_count": 1},
                        "tenure_type": "REGULAR",
                        "sequence": 1,
                        "total_cycles": 0,
                        "pricing_scheme": {"fixed_price": {"value": price, "currency_code": PAYPAL_CURRENCY}},
                    }
                ],
                "payment_preferences": {
                    "auto_bill_outstanding": True,
                    "setup_fee_failure_action": "CANCEL",
                    "payment_failure_threshold": 2,
                },
            },
        )
        print(f"{env_key}={plan['id']}")


if __name__ == "__main__":
    main()
