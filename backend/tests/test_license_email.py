from unittest.mock import MagicMock

from app.services import license_email


def test_no_provider_configured_returns_false(monkeypatch):
    monkeypatch.setattr(license_email, "SENDGRID_API_KEY", "")
    monkeypatch.setattr(license_email, "SMTP_HOST", "")

    assert license_email.send_license_email("buyer@example.com", "KEY", "pro") is False


def test_prefers_sendgrid_when_both_configured(monkeypatch):
    monkeypatch.setattr(license_email, "SENDGRID_API_KEY", "sg-key")
    monkeypatch.setattr(license_email, "SENDGRID_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setattr(license_email, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(license_email, "SMTP_FROM_EMAIL", "noreply@example.com")

    sendgrid_mock = MagicMock()
    smtp_mock = MagicMock()
    monkeypatch.setattr(license_email, "_send_via_sendgrid", sendgrid_mock)
    monkeypatch.setattr(license_email, "_send_via_smtp", smtp_mock)

    result = license_email.send_license_email("buyer@example.com", "KEY", "pro")

    assert result is True
    assert sendgrid_mock.called
    assert not smtp_mock.called


def test_falls_back_to_smtp_when_sendgrid_not_configured(monkeypatch):
    monkeypatch.setattr(license_email, "SENDGRID_API_KEY", "")
    monkeypatch.setattr(license_email, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(license_email, "SMTP_FROM_EMAIL", "noreply@example.com")

    smtp_mock = MagicMock()
    monkeypatch.setattr(license_email, "_send_via_smtp", smtp_mock)

    result = license_email.send_license_email("buyer@example.com", "KEY", "pro")

    assert result is True
    assert smtp_mock.called


def test_sendgrid_failure_returns_false_without_raising(monkeypatch):
    monkeypatch.setattr(license_email, "SENDGRID_API_KEY", "sg-key")
    monkeypatch.setattr(license_email, "SENDGRID_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setattr(license_email, "SMTP_HOST", "")

    def raise_error(*a, **k):
        raise RuntimeError("SendGrid returned status 401")

    monkeypatch.setattr(license_email, "_send_via_sendgrid", raise_error)

    assert license_email.send_license_email("buyer@example.com", "KEY", "pro") is False
