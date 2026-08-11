"""Password hashing/verification and the complexity rule for self-serve
signup (routers/accounts.py).

PBKDF2-HMAC-SHA256, stdlib `hashlib` only -- no bcrypt/argon2/passlib
dependency for something this small, consistent with this project's
pattern elsewhere (e.g. the hand-rolled Paddle/Polar webhook HMAC
verification instead of pulling in either SDK). 600,000 iterations is
OWASP's 2023 minimum recommendation for PBKDF2-SHA256.
"""

import hashlib
import hmac
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False
    computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    return hmac.compare_digest(computed, expected)


def validate_password_strength(password: str) -> None:
    """Raises ValueError with a specific, user-facing message for the first
    unmet rule -- not a generic "invalid password" -- so the signup/reset
    form can show exactly what's missing.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(password) > 200:
        raise ValueError("Password is too long.")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must include at least one uppercase letter.")
    if not any(c.islower() for c in password):
        raise ValueError("Password must include at least one lowercase letter.")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must include at least one number.")
    if not any(not c.isalnum() for c in password):
        raise ValueError("Password must include at least one symbol (e.g. !@#$%).")
