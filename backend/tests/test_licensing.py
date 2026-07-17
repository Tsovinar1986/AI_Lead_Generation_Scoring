import base64
import time

from nacl.signing import SigningKey

from app import licensing


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _make_keypair():
    signing_key = SigningKey.generate()
    return signing_key, _b64(bytes(signing_key.verify_key))


def _sign_license(signing_key: SigningKey, payload: dict) -> str:
    import json

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    signature = signing_key.sign(payload_bytes).signature
    return f"{_b64(payload_bytes)}.{_b64(signature)}"


def test_no_license_key_returns_none(monkeypatch):
    monkeypatch.setattr(licensing, "LICENSE_KEY", "")
    monkeypatch.setattr(licensing, "LICENSE_PUBLIC_KEY", "pub")
    assert licensing.verify_license() is None


def test_valid_license_verifies(monkeypatch):
    signing_key, public_b64 = _make_keypair()
    key = _sign_license(signing_key, {
        "customer_email": "buyer@example.com", "plan": "pro",
        "issued_at": time.time(), "expires_at": None,
    })

    monkeypatch.setattr(licensing, "LICENSE_KEY", key)
    monkeypatch.setattr(licensing, "LICENSE_PUBLIC_KEY", public_b64)

    info = licensing.verify_license()
    assert info is not None
    assert info.customer_email == "buyer@example.com"
    assert info.plan == "pro"


def test_license_signed_with_wrong_key_rejected(monkeypatch):
    signing_key, _ = _make_keypair()
    _, other_public_b64 = _make_keypair()
    key = _sign_license(signing_key, {
        "customer_email": "buyer@example.com", "plan": "pro",
        "issued_at": time.time(), "expires_at": None,
    })

    monkeypatch.setattr(licensing, "LICENSE_KEY", key)
    monkeypatch.setattr(licensing, "LICENSE_PUBLIC_KEY", other_public_b64)

    assert licensing.verify_license() is None


def test_expired_license_rejected(monkeypatch):
    signing_key, public_b64 = _make_keypair()
    key = _sign_license(signing_key, {
        "customer_email": "buyer@example.com", "plan": "pro",
        "issued_at": time.time() - 1000, "expires_at": time.time() - 1,
    })

    monkeypatch.setattr(licensing, "LICENSE_KEY", key)
    monkeypatch.setattr(licensing, "LICENSE_PUBLIC_KEY", public_b64)

    assert licensing.verify_license() is None


def test_malformed_license_string_rejected(monkeypatch):
    monkeypatch.setattr(licensing, "LICENSE_KEY", "not-a-valid-license")
    monkeypatch.setattr(licensing, "LICENSE_PUBLIC_KEY", "pub")

    assert licensing.verify_license() is None


def test_check_license_state_none_when_no_key_set(monkeypatch):
    monkeypatch.setattr(licensing, "LICENSE_KEY", "")
    monkeypatch.setattr(licensing, "LICENSE_PUBLIC_KEY", "pub")

    check = licensing.check_license()
    assert check.state == licensing.LicenseState.NONE
    assert check.info is None


def test_check_license_state_invalid_for_malformed_key(monkeypatch):
    monkeypatch.setattr(licensing, "LICENSE_KEY", "not-a-valid-license")
    monkeypatch.setattr(licensing, "LICENSE_PUBLIC_KEY", "pub")

    check = licensing.check_license()
    assert check.state == licensing.LicenseState.INVALID
    assert check.info is None


def test_check_license_state_invalid_for_wrong_signing_key(monkeypatch):
    signing_key, _ = _make_keypair()
    _, other_public_b64 = _make_keypair()
    key = _sign_license(signing_key, {
        "customer_email": "buyer@example.com", "plan": "pro",
        "issued_at": time.time(), "expires_at": None,
    })
    monkeypatch.setattr(licensing, "LICENSE_KEY", key)
    monkeypatch.setattr(licensing, "LICENSE_PUBLIC_KEY", other_public_b64)

    check = licensing.check_license()
    assert check.state == licensing.LicenseState.INVALID


def test_check_license_state_expired_still_exposes_customer_email(monkeypatch):
    signing_key, public_b64 = _make_keypair()
    key = _sign_license(signing_key, {
        "customer_email": "buyer@example.com", "plan": "pro",
        "issued_at": time.time() - 1000, "expires_at": time.time() - 1,
    })
    monkeypatch.setattr(licensing, "LICENSE_KEY", key)
    monkeypatch.setattr(licensing, "LICENSE_PUBLIC_KEY", public_b64)

    check = licensing.check_license()
    assert check.state == licensing.LicenseState.EXPIRED
    assert check.info is not None
    assert check.info.customer_email == "buyer@example.com"


def test_trial_days_left_starts_at_full_window(monkeypatch):
    monkeypatch.setattr(licensing, "TRIAL_DAYS", 3)
    monkeypatch.setattr(licensing.storage, "get_or_start_trial", lambda: time.time())

    assert licensing.trial_days_left() == 3.0


def test_trial_days_left_counts_down(monkeypatch):
    monkeypatch.setattr(licensing, "TRIAL_DAYS", 3)
    monkeypatch.setattr(licensing.storage, "get_or_start_trial", lambda: time.time() - 86400)

    assert round(licensing.trial_days_left(), 2) == 2.0


def test_trial_days_left_floors_at_zero_once_expired(monkeypatch):
    monkeypatch.setattr(licensing, "TRIAL_DAYS", 3)
    monkeypatch.setattr(licensing.storage, "get_or_start_trial", lambda: time.time() - 10 * 86400)

    assert licensing.trial_days_left() == 0.0


def test_check_license_state_valid(monkeypatch):
    signing_key, public_b64 = _make_keypair()
    key = _sign_license(signing_key, {
        "customer_email": "buyer@example.com", "plan": "pro",
        "issued_at": time.time(), "expires_at": None,
    })
    monkeypatch.setattr(licensing, "LICENSE_KEY", key)
    monkeypatch.setattr(licensing, "LICENSE_PUBLIC_KEY", public_b64)

    check = licensing.check_license()
    assert check.state == licensing.LicenseState.VALID
    assert check.info.customer_email == "buyer@example.com"
