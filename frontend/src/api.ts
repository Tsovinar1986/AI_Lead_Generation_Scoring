import type { Alert, LicenseStatus, ScoredLead } from "./types";

const BASE = `${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}/api`;

export class LicenseRequiredError extends Error {}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const message = body.detail ?? "Request failed";
    if (res.status === 402) throw new LicenseRequiredError(message);
    throw new Error(message);
  }
  return res.json();
}

export async function uploadLeads(file: File): Promise<ScoredLead[]> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/leads/upload`, { method: "POST", body: form });
  return handle(res);
}

export async function fetchLeads(): Promise<ScoredLead[]> {
  const res = await fetch(`${BASE}/leads`);
  return handle(res);
}

export async function fetchAlerts(): Promise<Alert[]> {
  const res = await fetch(`${BASE}/alerts`);
  return handle(res);
}

export async function generateOutreach(
  leadId: string,
  channel: "email" | "linkedin"
): Promise<{ draft: string }> {
  const res = await fetch(`${BASE}/leads/${leadId}/outreach`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  });
  return handle(res);
}

export async function fetchLicenseStatus(): Promise<LicenseStatus> {
  const res = await fetch(`${BASE}/license`);
  return handle(res);
}

export async function startCheckout(): Promise<{ checkout_url: string }> {
  const res = await fetch(`${BASE}/billing/checkout`, { method: "POST" });
  return handle(res);
}
