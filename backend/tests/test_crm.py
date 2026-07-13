from app.services import crm

from .conftest import make_scored_lead


def test_hubspot_falls_back_to_mock_without_token(monkeypatch):
    monkeypatch.setattr(crm, "HUBSPOT_ACCESS_TOKEN", "")
    result = crm.push_to_crm(make_scored_lead(), crm="hubspot")

    assert result.status == "simulated"
    assert "HUBSPOT_ACCESS_TOKEN" in result.detail


def test_salesforce_falls_back_to_mock_without_credentials(monkeypatch):
    monkeypatch.setattr(crm, "SALESFORCE_USERNAME", "")
    monkeypatch.setattr(crm, "SALESFORCE_PASSWORD", "")
    monkeypatch.setattr(crm, "SALESFORCE_SECURITY_TOKEN", "")
    result = crm.push_to_crm(make_scored_lead(), crm="salesforce")

    assert result.status == "simulated"
    assert "SALESFORCE" in result.detail


def test_unknown_crm_falls_back_to_mock(monkeypatch):
    result = crm.push_to_crm(make_scored_lead(), crm="not-a-real-crm")
    assert result.status == "simulated"


def test_live_push_failure_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(crm, "HUBSPOT_ACCESS_TOKEN", "fake-token")
    monkeypatch.setattr(crm, "_hubspot_push", lambda lead: (_ for _ in ()).throw(RuntimeError("boom")))

    result = crm.push_to_crm(make_scored_lead(), crm="hubspot")

    assert result.status == "simulated"
    assert "failed" in result.detail.lower()


def test_ensure_hubspot_properties_creates_missing_ones(monkeypatch):
    from unittest.mock import MagicMock

    from hubspot.crm.properties import ApiException

    fake_client = MagicMock()
    fake_client.crm.properties.core_api.get_by_name.side_effect = ApiException(status=404)

    crm._hubspot_properties_ready = False
    crm._ensure_hubspot_properties(fake_client)

    assert fake_client.crm.properties.core_api.create.call_count == len(crm._HUBSPOT_COMPANY_PROPERTIES)


def test_ensure_hubspot_properties_skips_existing(monkeypatch):
    from unittest.mock import MagicMock

    fake_client = MagicMock()  # get_by_name succeeds -> property already exists

    crm._hubspot_properties_ready = False
    crm._ensure_hubspot_properties(fake_client)

    assert fake_client.crm.properties.core_api.create.call_count == 0


def test_ensure_hubspot_properties_only_runs_once(monkeypatch):
    from unittest.mock import MagicMock

    fake_client = MagicMock()
    crm._hubspot_properties_ready = False
    crm._ensure_hubspot_properties(fake_client)
    crm._ensure_hubspot_properties(fake_client)

    assert fake_client.crm.properties.core_api.get_by_name.call_count == len(crm._HUBSPOT_COMPANY_PROPERTIES)


def test_ensure_salesforce_fields_creates_only_missing(monkeypatch):
    from unittest.mock import MagicMock

    fake_sf = MagicMock()
    fake_sf.toolingexecute.return_value = {"records": [{"DeveloperName": "Fit_Score"}]}

    crm._salesforce_fields_ready = False
    crm._ensure_salesforce_fields(fake_sf)

    create_calls = [c for c in fake_sf.toolingexecute.call_args_list if c.kwargs.get("method") == "POST"]
    assert len(create_calls) == len(crm._SALESFORCE_LEAD_FIELDS) - 1


def test_ensure_salesforce_fields_swallows_permission_errors(monkeypatch):
    from unittest.mock import MagicMock

    fake_sf = MagicMock()
    fake_sf.toolingexecute.side_effect = Exception("403 insufficient permissions")

    crm._salesforce_fields_ready = False
    crm._ensure_salesforce_fields(fake_sf)  # must not raise
