"""Security headers + rate limiting, applied in main.py.

Not a Node/Express app, so there's no literal "helmet" package to reach
for -- SecurityHeadersMiddleware below sets the same class of headers
helmet does, by hand, since that's a handful of lines and avoids pulling
in a dependency for something this small.

Rate limiting is slowapi (a FastAPI-oriented wrapper around `limits`) --
the de facto choice here, same as Flask-Limiter is for Flask. `limiter`
is a single shared instance imported by main.py (to register the
exception handler + default limit) and by any router that wants a
stricter limit than the default on a specific route.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import RATE_LIMIT_DEFAULT

limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT_DEFAULT])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # HSTS only means anything (and is only honored by browsers) over
        # an actually-secure connection -- request.url.scheme reflects the
        # real client-facing scheme once TRUST_PROXY_HEADERS is on behind a
        # TLS-terminating proxy; sending it over plain HTTP otherwise would
        # just be noise.
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            # Braintree Drop-in (in-page card checkout) loads its script from
            # js.braintreegateway.com, renders the card fields in iframes from
            # assets.braintreegateway.com, and tokenizes via Braintree's APIs.
            "script-src 'self' https://js.braintreegateway.com https://assets.braintreegateway.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://assets.braintreegateway.com; "
            "connect-src 'self' https://api.braintreegateway.com https://api.sandbox.braintreegateway.com "
            "https://client-analytics.braintreegateway.com https://client-analytics.sandbox.braintreegateway.com "
            "https://payments.braintree-api.com https://payments.sandbox.braintree-api.com; "
            "frame-src https://assets.braintreegateway.com; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
        return response
