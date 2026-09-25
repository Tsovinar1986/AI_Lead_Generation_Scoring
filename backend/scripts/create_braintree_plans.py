#!/usr/bin/env python3
"""Creates the four Braintree subscription plans (Pro/Advanced x
monthly/annual) from the BRAINTREE_* and PRICE_* settings in .env. Run once
per Braintree environment (sandbox, then production):

    cd backend && python scripts/create_braintree_plans.py

Plans that already exist (same id) are left alone, so it's safe to re-run.
Starter is free and has no plan. Braintree plan prices can be edited in the
Control Panel, but existing subscriptions keep the price they started on.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import (  # noqa: E402
    BILLING_CURRENCY,
    BRAINTREE_ENVIRONMENT,
    BRAINTREE_PLAN_ADVANCED_ANNUAL,
    BRAINTREE_PLAN_ADVANCED_MONTHLY,
    BRAINTREE_PLAN_PRO_ANNUAL,
    BRAINTREE_PLAN_PRO_MONTHLY,
    PRICE_ADVANCED_ANNUAL,
    PRICE_ADVANCED_MONTHLY,
    PRICE_PRO_ANNUAL,
    PRICE_PRO_MONTHLY,
)
from app.routers.billing import _gateway  # noqa: E402

# (plan id, display name, billing frequency in months, price)
PLANS = [
    (BRAINTREE_PLAN_PRO_MONTHLY, "Pro (monthly)", 1, PRICE_PRO_MONTHLY),
    (BRAINTREE_PLAN_PRO_ANNUAL, "Pro (annual)", 12, PRICE_PRO_ANNUAL),
    (BRAINTREE_PLAN_ADVANCED_MONTHLY, "Advanced (monthly)", 1, PRICE_ADVANCED_MONTHLY),
    (BRAINTREE_PLAN_ADVANCED_ANNUAL, "Advanced (annual)", 12, PRICE_ADVANCED_ANNUAL),
]


def main() -> None:
    gateway = _gateway()
    print(f"Creating plans in Braintree {BRAINTREE_ENVIRONMENT}...", file=sys.stderr)
    existing = {plan.id for plan in gateway.plan.all()}
    for plan_id, name, months, price in PLANS:
        if plan_id in existing:
            print(f"  {plan_id}: already exists, skipped", file=sys.stderr)
            continue
        result = gateway.plan.create(
            {
                "id": plan_id,
                "name": f"CRM Scoring {name}",
                "price": price,
                "billing_frequency": months,
                "currency_iso_code": BILLING_CURRENCY,
                # No number_of_billing_cycles: bills until cancelled.
            }
        )
        if not result.is_success:
            sys.exit(f"Couldn't create {plan_id}: {result.message}")
        print(f"  {plan_id}: created ({BILLING_CURRENCY} {price} every {months} month(s))", file=sys.stderr)


if __name__ == "__main__":
    main()
