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

from . import config, storage

NO_WORKSPACE_DETAIL = "Start a free trial or log in to use this workspace."


def get_current_tenant(authorization: str | None = Header(default=None)) -> storage.Tenant:
    if authorization is None:
        if config.HOSTED_MODE:
            # The default workspace on a public deployment belongs to the
            # seller (and runs on their license) -- never hand it to visitors.
            raise HTTPException(status_code=401, detail=NO_WORKSPACE_DETAIL)
        return storage.Tenant(id=storage.DEFAULT_TENANT_ID, name="default")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <api-key>'")

    api_key = authorization.removeprefix("Bearer ").strip()
    tenant = storage.get_tenant_by_api_key(api_key)
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return tenant


def get_optional_tenant(authorization: str | None = Header(default=None)) -> storage.Tenant | None:
    """Like get_current_tenant, but None instead of 401 when there's no
    workspace key -- for endpoints that also serve anonymous visitors."""
    if authorization is None:
        return None if config.HOSTED_MODE else storage.Tenant(id=storage.DEFAULT_TENANT_ID, name="default")
    return get_current_tenant(authorization)
