"""Rule-based churn-risk scoring for individual customer/subscriber exports
(tenure, contract type, monthly charges, service add-ons) -- a different
data shape from a B2B lead (backend/app/services/scoring.py), so it's a
separate model and endpoint rather than forced into the lead-scoring shape.

The weights below reflect well-documented churn factors for this kind of
subscription data (month-to-month contracts, short tenure, high monthly
charges, no tech support/security add-ons, and electronic check payment
all correlate with higher churn in published analyses of this exact
dataset shape) -- not mock/random output, but they're a simple weighted
heuristic, not a trained model.
"""

import io

import pandas as pd

from ..models import ChurnCustomer, ChurnRiskBreakdown, ChurnScoredCustomer

COLUMN_ALIASES = {
    "contract": "contract",
    "tenure": "tenure_months",
    "tenure_months": "tenure_months",
    "monthlycharges": "monthly_charges",
    "monthly_charges": "monthly_charges",
    "internetservice": "internet_service",
    "internet_service": "internet_service",
    "techsupport": "tech_support",
    "tech_support": "tech_support",
    "onlinesecurity": "online_security",
    "online_security": "online_security",
    "paymentmethod": "payment_method",
    "payment_method": "payment_method",
}

_REQUIRED = {"contract", "tenure_months", "monthly_charges"}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={k: v for k, v in COLUMN_ALIASES.items() if k in df.columns})
    return df


def parse_churn_file(filename: str, content: bytes) -> list[ChurnCustomer]:
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    else:
        df = pd.read_csv(io.BytesIO(content))

    df = _normalize_columns(df)

    missing = _REQUIRED - set(df.columns)
    if missing:
        raise ValueError(
            "File doesn't look like a churn export -- missing column(s): "
            + ", ".join(sorted(missing))
        )

    customers = []
    for _, row in df.iterrows():
        customers.append(
            ChurnCustomer(
                contract=str(row["contract"]).strip(),
                tenure_months=int(row["tenure_months"]),
                monthly_charges=float(row["monthly_charges"]),
                internet_service=_clean(row.get("internet_service")),
                tech_support=_clean(row.get("tech_support")),
                online_security=_clean(row.get("online_security")),
                payment_method=_clean(row.get("payment_method")),
            )
        )
    return customers


def _clean(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


# Typical monthly-charges range for this kind of data -- used only to scale
# charges_risk into a 0-1 band, not a hard cutoff.
_CHARGES_LOW, _CHARGES_HIGH = 18.0, 120.0


def score_churn_customer(customer: ChurnCustomer) -> ChurnScoredCustomer:
    contract = customer.contract.lower()
    if "month-to-month" in contract:
        contract_risk = 35.0
    elif "one year" in contract:
        contract_risk = 15.0
    else:
        contract_risk = 0.0

    tenure_ratio = max(0.0, 1.0 - min(customer.tenure_months, 24) / 24)
    tenure_risk = round(tenure_ratio * 25, 1)

    charges_ratio = max(
        0.0,
        min(1.0, (customer.monthly_charges - _CHARGES_LOW) / (_CHARGES_HIGH - _CHARGES_LOW)),
    )
    charges_risk = round(charges_ratio * 15, 1)

    service_gaps_risk = 0.0
    if (customer.tech_support or "").lower() == "no":
        service_gaps_risk += 8.0
    if (customer.online_security or "").lower() == "no":
        service_gaps_risk += 7.0

    payment_method_risk = 10.0 if (customer.payment_method or "").lower() == "electronic check" else 0.0

    breakdown = ChurnRiskBreakdown(
        contract_risk=contract_risk,
        tenure_risk=tenure_risk,
        charges_risk=charges_risk,
        service_gaps_risk=service_gaps_risk,
        payment_method_risk=payment_method_risk,
    )
    risk_score = round(sum(breakdown.model_dump().values()), 1)

    bucket = "high" if risk_score >= 60 else "medium" if risk_score >= 30 else "low"

    return ChurnScoredCustomer(
        **customer.model_dump(),
        risk_score=risk_score,
        risk_breakdown=breakdown,
        bucket=bucket,
    )
