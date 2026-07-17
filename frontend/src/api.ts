import type { Alert, BillingConfig, LicenseStatus, ScoredLead } from "./types";

// Same-origin by default -- works unmodified both in merged production mode
// (backend serves the built frontend, so "same origin" IS the backend) and
// in dev mode (vite.config.ts proxies /api to localhost:8081). Only set
// VITE_API_BASE_URL if the API genuinely lives on a different origin than
// wherever this frontend is served from.
const BASE = `${import.meta.env.VITE_API_BASE_URL ?? ""}/api`;

const TENANT_KEY_STORAGE_KEY = "tenant_api_key";

// Only relevant for a seller running one shared instance for multiple
// customers (backend/scripts/create_tenant.py). A single self-hosted buyer
// never sets this -- every request then falls back to the backend's
// default tenant, exactly the original zero-config behavior.
export function getTenantApiKey(): string | null {
  return localStorage.getItem(TENANT_KEY_STORAGE_KEY);
}

export function setTenantApiKey(key: string): void {
  localStorage.setItem(TENANT_KEY_STORAGE_KEY, key);
}

export function clearTenantApiKey(): void {
  localStorage.removeItem(TENANT_KEY_STORAGE_KEY);
}

function authHeaders(): Record<string, string> {
  const key = getTenantApiKey();
  return key ? { Authorization: `Bearer ${key}` } : {};
}

export class LicenseRequiredError extends Error {}
export class TenantAuthError extends Error {}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const message = body.detail ?? "Request failed";
    if (res.status === 402) throw new LicenseRequiredError(message);
    if (res.status === 401) throw new TenantAuthError(message);
    throw new Error(message);
  }
  return res.json();
}

export interface UploadResult {
  leads: ScoredLead[];
  // Set when a trial upload got capped to fewer rows than the file
  // contained (see backend/app/routers/leads.py's TRIAL_MAX_LEADS_PER_UPLOAD).
  trialLimitedRows: number | null;
  trialTotalRows: number | null;
}

export async function uploadLeads(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/leads/upload`, { method: "POST", headers: authHeaders(), body: form });
  const leads = await handle<ScoredLead[]>(res);
  const limitedRows = res.headers.get("X-Trial-Limited-Rows");
  const totalRows = res.headers.get("X-Trial-Total-Rows");
  return {
    leads,
    trialLimitedRows: limitedRows ? Number(limitedRows) : null,
    trialTotalRows: totalRows ? Number(totalRows) : null,
  };
}

export async function fetchLeads(): Promise<ScoredLead[]> {
  const res = await fetch(`${BASE}/leads`, { headers: authHeaders() });
  return handle(res);
}

export async function fetchAlerts(): Promise<Alert[]> {
  const res = await fetch(`${BASE}/alerts`, { headers: authHeaders() });
  return handle(res);
}

export async function generateOutreach(
  leadId: string,
  channel: "email" | "linkedin"
): Promise<{ draft: string }> {
  const res = await fetch(`${BASE}/leads/${leadId}/outreach`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ channel }),
  });
  return handle(res);
}

export async function pushToCrm(
  leadId: string,
  crm: string
): Promise<{ status: string; detail: string }> {
  const res = await fetch(`${BASE}/leads/${leadId}/crm-push?crm=${crm}`, {
    method: "POST",
    headers: authHeaders(),
  });
  return handle(res);
}

// Deployment-wide, not tenant-scoped -- licensing gates the whole self-hosted
// instance, not an individual tenant within it, so these don't send the
// tenant Authorization header.
export async function fetchLicenseStatus(): Promise<LicenseStatus> {
  const res = await fetch(`${BASE}/license`);
  return handle(res);
}

export async function fetchBillingConfig(): Promise<BillingConfig> {
  const res = await fetch(`${BASE}/billing/config`);
  return handle(res);
}
