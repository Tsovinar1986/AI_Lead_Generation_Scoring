"""Thin wrapper around the Anthropic client.

Returns None from get_client() when no ANTHROPIC_API_KEY is configured, so
callers can fall back to a deterministic mock instead of crashing. This lets
the app run end-to-end with zero external accounts, and start using real
Claude calls the moment a key is added to .env.
"""

from functools import lru_cache

from anthropic import Anthropic

from ..config import ANTHROPIC_API_KEY


@lru_cache(maxsize=1)
def get_client() -> Anthropic | None:
    if not ANTHROPIC_API_KEY:
        return None
    return Anthropic(api_key=ANTHROPIC_API_KEY)
