import pytest

from app.services.ingestion import parse_leads_file


def test_parses_csv_with_standard_headers():
    csv = (
        b"company_name,domain,contact_name,contact_title,industry,employees,revenue,country\n"
        b"Acme Inc,acme.com,Jane Doe,VP of Sales,SaaS,200,20000000,United States\n"
    )
    leads = parse_leads_file("leads.csv", csv)

    assert len(leads) == 1
    lead = leads[0]
    assert lead.company_name == "Acme Inc"
    assert lead.domain == "acme.com"
    assert lead.employee_count == 200
    assert lead.revenue_usd == 20_000_000
    assert lead.geography == "United States"


def test_column_aliases_normalize_to_canonical_fields():
    csv = b"Company,Website,Full Name,Job Title,Employees\nAcme,acme.com,Jane,CTO,50\n"
    leads = parse_leads_file("leads.csv", csv)

    assert leads[0].company_name == "Acme"
    assert leads[0].domain == "acme.com"
    assert leads[0].contact_name == "Jane"
    assert leads[0].contact_title == "CTO"
    assert leads[0].employee_count == 50


def test_missing_required_columns_raises_value_error():
    csv = b"industry,employees\nSaaS,200\n"
    with pytest.raises(ValueError):
        parse_leads_file("leads.csv", csv)


def test_missing_optional_fields_become_none():
    csv = b"company_name,domain\nAcme,acme.com\n"
    lead = parse_leads_file("leads.csv", csv)[0]

    assert lead.contact_name is None
    assert lead.employee_count is None
    assert lead.revenue_usd is None


def test_domain_lowercased_and_trimmed():
    csv = b"company_name,domain\nAcme, ACME.COM \n"
    lead = parse_leads_file("leads.csv", csv)[0]

    assert lead.domain == "acme.com"
