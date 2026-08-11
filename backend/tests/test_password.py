import pytest

from app.services.password import hash_password, validate_password_strength, verify_password


def test_hash_then_verify_round_trips():
    stored = hash_password("Correct-Horse9")
    assert verify_password("Correct-Horse9", stored) is True


def test_wrong_password_fails_verification():
    stored = hash_password("Correct-Horse9")
    assert verify_password("wrong-password9!", stored) is False


def test_hash_is_salted_differently_each_time():
    a = hash_password("Correct-Horse9")
    b = hash_password("Correct-Horse9")
    assert a != b
    assert verify_password("Correct-Horse9", a) is True
    assert verify_password("Correct-Horse9", b) is True


def test_verify_rejects_garbage_stored_hash():
    assert verify_password("anything", "not-a-real-hash") is False


@pytest.mark.parametrize(
    "password,expected_fragment",
    [
        ("short1!", "at least 8 characters"),
        ("nouppercase1!", "at least one uppercase letter"),
        ("NOLOWERCASE1!", "at least one lowercase letter"),
        ("NoNumberSymbol", "at least one number"),
        ("NoSymbolHere1", "at least one symbol"),
    ],
)
def test_validate_password_strength_rejects_each_missing_rule(password, expected_fragment):
    with pytest.raises(ValueError, match=expected_fragment):
        validate_password_strength(password)


def test_validate_password_strength_accepts_a_valid_password():
    validate_password_strength("Correct-Horse9")  # must not raise
