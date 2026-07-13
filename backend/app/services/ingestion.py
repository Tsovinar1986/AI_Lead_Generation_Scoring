import io

import pandas as pd

from ..models import Lead

# Maps common CRM export column names to our Lead fields.
COLUMN_ALIASES = {
    "company": "company_name",
    "company_name": "company_name",
    "account_name": "company_name",
    "domain": "domain",
    "website": "domain",
    "contact": "contact_name",
    "contact_name": "contact_name",
    "full_name": "contact_name",
    "title": "contact_title",
    "job_title": "contact_title",
    "contact_title": "contact_title",
    "industry": "industry",
    "employees": "employee_count",
    "employee_count": "employee_count",
    "company_size": "employee_count",
    "revenue": "revenue_usd",
    "annual_revenue": "revenue_usd",
    "revenue_usd": "revenue_usd",
    "country": "geography",
    "geography": "geography",
    "location": "geography",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={k: v for k, v in COLUMN_ALIASES.items() if k in df.columns})
    return df


def parse_leads_file(filename: str, content: bytes) -> list[Lead]:
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    else:
        df = pd.read_csv(io.BytesIO(content))

    df = _normalize_columns(df)

    if "company_name" not in df.columns or "domain" not in df.columns:
        raise ValueError(
            "File must include at least a company name and a domain/website column."
        )

    leads = []
    for _, row in df.iterrows():
        employee_count = row.get("employee_count")
        revenue_usd = row.get("revenue_usd")
        leads.append(
            Lead(
                company_name=str(row.get("company_name")).strip(),
                domain=str(row.get("domain")).strip().lower(),
                contact_name=_clean(row.get("contact_name")),
                contact_title=_clean(row.get("contact_title")),
                industry=_clean(row.get("industry")),
                employee_count=int(employee_count) if pd.notna(employee_count) else None,
                revenue_usd=int(revenue_usd) if pd.notna(revenue_usd) else None,
                geography=_clean(row.get("geography")),
            )
        )
    return leads


def _clean(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None
