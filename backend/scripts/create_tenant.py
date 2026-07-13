#!/usr/bin/env python3
"""Provisions a new tenant for a multi-tenant deployment. Run by the seller,
against the same DATABASE_PATH the running app uses.

    cd backend && python scripts/create_tenant.py "Acme Corp"

Prints the API key ONCE -- only its hash is stored, there is no way to
recover it later. Give it to the customer; the frontend's TenantGate
component prompts for it once and stores it in localStorage, attaching it
as `Authorization: Bearer <key>` on every API request after that.

Single-tenant self-hosted buyers never need this at all -- requests with no
Authorization header are automatically scoped to a "default" tenant, so
this is purely for a seller running one shared instance for multiple
customers.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import storage  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Customer/tenant display name")
    args = parser.parse_args()

    tenant, api_key = storage.create_tenant(args.name)

    print(f"Created tenant '{tenant.name}' (id={tenant.id})")
    print()
    print("API key (save this now -- it cannot be recovered later):")
    print(f"  {api_key}")


if __name__ == "__main__":
    main()
