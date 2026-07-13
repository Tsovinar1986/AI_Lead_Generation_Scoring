"""Tenant resolution for multi-tenant deployments.

No Authorization header -> DEFAULT_TENANT_ID, so a single self-hosted buyer
(the common case) never has to think about auth at all -- this preserves
the zero-config behavior the whole app is built around. A seller running
one shared instance for several customers provisions each one a real
tenant + API key (backend/scripts/create_tenant.py) and requires it via
`Authorization: Bearer <key>`; an invalid key is rejected rather than
silently falling back to the default tenant, so a typo'd key can't
accidentally leak into (or read) someone else's data.
"""

from fastapi import Header, HTTPException

from . import storage


def get_current_tenant(authorization: str | None = Header(default=None)) -> storage.Tenant:
    if authorization is None:
        return storage.Tenant(id=storage.DEFAULT_TENANT_ID, name="default")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <api-key>'")

    api_key = authorization.removeprefix("Bearer ").strip()
    tenant = storage.get_tenant_by_api_key(api_key)
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return tenant
