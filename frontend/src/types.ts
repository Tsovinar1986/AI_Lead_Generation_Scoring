export interface ScoreBreakdown {
  industry_match: number;
  company_size_fit: number;
  revenue_fit: number;
  tech_stack_match: number;
  geography_fit: number;
  title_seniority: number;
  hiring_signal: number;
}

export interface ScoredLead {
  id: string;
  company_name: string;
  domain: string;
  contact_name: string | null;
  contact_title: string | null;
  industry: string | null;
  employee_count: number | null;
  revenue_usd: number | null;
  geography: string | null;
  source: string;
  tech_stack: string[];
  is_hiring: boolean;
  enrichment_source: string;
  fit_score: number;
  score_breakdown: ScoreBreakdown;
  conversion_likelihood: number;
  llm_rationale: string;
  combined_score: number;
  bucket: "hot" | "warm" | "cold";
  outreach_draft: string | null;
  crm_pushed: boolean;
}

export interface Alert {
  id: string;
  lead_id: string;
  company_name: string;
  combined_score: number;
  message: string;
  channel: string;
}

export type LicenseStatus =
  | { licensed: false; reason: "none" | "invalid" | "expired"; customer_email: string | null; plan: string | null }
  | { licensed: true; customer_email: string; plan: string; expires_at: number | null };
