import io


def _upload(client, content: bytes, filename="churn.csv"):
    return client.post(
        "/api/churn/upload",
        files={"file": (filename, io.BytesIO(content), "text/csv")},
    )


CHURN_HEADER = b"Contract,tenure,MonthlyCharges,InternetService,TechSupport,OnlineSecurity,PaymentMethod\n"


def test_upload_rejects_lead_shaped_file(client):
    resp = _upload(client, b"company_name,domain\nAcme,acme.com\n")
    assert resp.status_code == 400
    assert "missing column" in resp.json()["detail"].lower()


def test_month_to_month_short_tenure_scores_high_risk(client):
    row = b"Month-to-month,1,95.5,Fiber optic,No,No,Electronic check\n"
    resp = _upload(client, CHURN_HEADER + row)

    assert resp.status_code == 200
    [customer] = resp.json()
    assert customer["bucket"] == "high"
    assert customer["risk_score"] > 60


def test_two_year_long_tenure_scores_low_risk(client):
    row = b"Two year,72,64.8,DSL,Yes,Yes,Bank transfer (automatic)\n"
    resp = _upload(client, CHURN_HEADER + row)

    assert resp.status_code == 200
    [customer] = resp.json()
    assert customer["bucket"] == "low"
    assert customer["risk_score"] < 30


def test_risk_breakdown_sums_to_risk_score(client):
    row = b"Month-to-month,10,70.0,Fiber optic,No,Yes,Mailed check\n"
    resp = _upload(client, CHURN_HEADER + row)

    assert resp.status_code == 200
    [customer] = resp.json()
    assert round(sum(customer["risk_breakdown"].values()), 1) == customer["risk_score"]


def test_no_rows_returns_400(client):
    resp = _upload(client, CHURN_HEADER)
    assert resp.status_code == 400
