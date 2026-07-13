#!/usr/bin/env python3
"""Gravity AI entry point for the AI Lead Generation & Scoring algorithm.

Gravity AI invokes this as:
    python score_leads.py {input} {output}

sys.argv[1] is the input lead file (CSV/XLSX export from a CRM or cold list),
sys.argv[2] is where the ranked, scored output CSV must be written. Reuses
the same ingestion -> enrichment -> hybrid scoring -> outreach-draft pipeline
as the backend service; see app/ (bundled alongside this script at build
time by build_package.sh) for the actual logic.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.enrichment import enrich_lead
from app.services.ingestion import parse_leads_file
from app.services.outreach import generate_outreach_draft
from app.services.scoring import score_lead


def run(input_path: str, output_path: str) -> None:
    import pandas as pd

    input_file = Path(input_path)
    leads = parse_leads_file(input_file.name, input_file.read_bytes())

    rows = []
    for lead in leads:
        enriched = enrich_lead(lead)
        scored = score_lead(enriched)
        if scored.bucket in ("hot", "warm"):
            scored.outreach_draft = generate_outreach_draft(scored)
        rows.append(
            {
                "company_name": scored.company_name,
                "domain": scored.domain,
                "contact_name": scored.contact_name,
                "contact_title": scored.contact_title,
                "industry": scored.industry,
                "employee_count": scored.employee_count,
                "revenue_usd": scored.revenue_usd,
                "geography": scored.geography,
                "tech_stack": ";".join(scored.tech_stack),
                "is_hiring": scored.is_hiring,
                "fit_score": scored.fit_score,
                "conversion_likelihood": scored.conversion_likelihood,
                "combined_score": scored.combined_score,
                "bucket": scored.bucket,
                "llm_rationale": scored.llm_rationale,
                "outreach_draft": scored.outreach_draft or "",
            }
        )

    pd.DataFrame(rows).sort_values("combined_score", ascending=False).to_csv(
        output_path, index=False
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python score_leads.py <input_path> <output_path>", file=sys.stderr)
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
