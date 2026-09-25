export interface ScoreBreakdown {
  industry_match: number;
  company_size_fit: number;
  revenue_fit: number;
  tech_stack_match: number;
  geography_fit: number;
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
  account_fit_score: number;
  llm_rationale: string;
  combined_score: number;
  bucket: "hot" | "warm" | "cold";
  crm_pushed: boolean;
}

export type LicenseTier = "starter" | "pro" | "advanced";

export type LicenseStatus =
  | {
      licensed: false;
      reason: "trial" | "trial_expired" | "invalid" | "expired";
      customer_email: string | null;
      plan: string | null;
      tier: LicenseTier;
      trial_uploads_left: number | null;
    }
  | { licensed: true; customer_email: string; plan: string; tier: LicenseTier; expires_at: number | null };

export type BillingInterval = "monthly" | "annual";
export type PlanTier = "starter" | "pro" | "advanced";

export type PaidTier = "pro" | "advanced";
export type PlanKey = `${PaidTier}_${BillingInterval}`;

export interface BillingConfig {
  checkout_available: boolean;
  // Braintree plan id per paid tier/interval. Starter is free.
  plans?: Partial<Record<PlanKey, string | null>>;
  currency?: string;
  environment: "sandbox" | "production";
  price_monthly?: string | null;
  price_annual?: string | null;
  price_advanced_monthly?: string | null;
  price_advanced_annual?: string | null;
}

export interface SubscribeRequest {
  tier: PaidTier;
  interval: BillingInterval;
  // Optional -- checkout doesn't ask for it; renewal keys are emailed only if set.
  email?: string;
  // From Braintree Drop-in's requestPaymentMethod() -- a one-time token for
  // the card, never the card details themselves.
  payment_method_nonce: string;
  device_data?: string;
}

export type SubscriptionActivation =
  | { status: "ok"; email: string; tier: PaidTier; plan: BillingInterval; license_key: string }
  | { status: "duplicate" };

export interface TenantAuth {
  tenant_id: string;
  name: string;
  api_key: string;
}
