from unittest.mock import MagicMock

from slack_sdk.errors import SlackApiError

from app import storage
from app.services import alerts

from .conftest import make_scored_lead


TENANT = "tenant-a"


def test_warm_or_cold_leads_never_alert():
    assert alerts.maybe_alert(TENANT, make_scored_lead(bucket="warm")) is None
    assert alerts.maybe_alert(TENANT, make_scored_lead(bucket="cold")) is None


def test_hot_lead_without_slack_config_stores_locally(monkeypatch):
    monkeypatch.setattr(alerts, "SLACK_BOT_TOKEN", "")
    monkeypatch.setattr(alerts, "SLACK_CHANNEL_ID", "")

    alert = alerts.maybe_alert(TENANT, make_scored_lead(bucket="hot"))

    assert alert is not None
    assert len(storage.list_alerts(TENANT)) == 1


def test_hot_lead_slack_failure_still_stores_locally(monkeypatch):
    monkeypatch.setattr(alerts, "SLACK_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(alerts, "SLACK_CHANNEL_ID", "C123")

    def raise_error(message):
        resp = MagicMock()
        resp.__getitem__ = lambda self, k: "channel_not_found"
        raise SlackApiError("channel_not_found", response=resp)

    monkeypatch.setattr(alerts, "_post_to_slack", raise_error)

    alert = alerts.maybe_alert(TENANT, make_scored_lead(bucket="hot"))

    assert alert is not None
    assert len(storage.list_alerts(TENANT)) == 1


def _fake_error(code: str) -> SlackApiError:
    resp = MagicMock()
    resp.__getitem__ = lambda self, k: code
    return SlackApiError(code, response=resp)


def test_preflight_happy_path_logs_no_warning():
    client = MagicMock()
    client.auth_test.return_value = {"team": "Acme", "user": "leadbot"}
    client.conversations_info.return_value = {"channel": {"is_member": True}}

    alerts._slack_preflight_done = False
    alerts._preflight_check_slack(client)  # must not raise

    assert client.auth_test.called
    assert client.conversations_info.called


def test_preflight_invalid_token_skips_channel_check():
    client = MagicMock()
    client.auth_test.side_effect = _fake_error("invalid_auth")

    alerts._slack_preflight_done = False
    alerts._preflight_check_slack(client)

    assert not client.conversations_info.called


def test_preflight_runs_only_once():
    client = MagicMock()
    client.auth_test.return_value = {"team": "Acme", "user": "leadbot"}
    client.conversations_info.return_value = {"channel": {"is_member": True}}

    alerts._slack_preflight_done = False
    alerts._preflight_check_slack(client)
    alerts._preflight_check_slack(client)

    assert client.auth_test.call_count == 1
