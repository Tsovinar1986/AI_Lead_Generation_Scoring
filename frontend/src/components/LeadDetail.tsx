import { useState } from "react";
import { generateOutreach, pushToCrm } from "../api";
import type { ScoredLead } from "../types";

interface Props {
  lead: ScoredLead;
  onClose: () => void;
  onUpdate: (lead: ScoredLead) => void;
}

const BREAKDOWN_LABELS: Record<string, string> = {
  industry_match: "Industry match",
  company_size_fit: "Company size fit",
  revenue_fit: "Revenue fit",
  tech_stack_match: "Tech stack match",
  geography_fit: "Geography fit",
  title_seniority: "Title seniority",
  hiring_signal: "Hiring signal",
};

export function LeadDetail({ lead, onClose, onUpdate }: Props) {
  const [channel, setChannel] = useState<"email" | "linkedin">("email");
  const [draft, setDraft] = useState(lead.outreach_draft ?? "");
  const [busy, setBusy] = useState<"outreach" | "crm" | null>(null);
  const [crmStatus, setCrmStatus] = useState<string | null>(null);

  async function handleDraft() {
    setBusy("outreach");
    try {
      const res = await generateOutreach(lead.id, channel);
      setDraft(res.draft);
      onUpdate({ ...lead, outreach_draft: res.draft });
    } finally {
      setBusy(null);
    }
  }

  async function handleCrmPush() {
    setBusy("crm");
    try {
      const res = await pushToCrm(lead.id, "hubspot");
      setCrmStatus(res.detail);
      onUpdate({ ...lead, crm_pushed: true });
    } finally {
      setBusy(null);
    }
  }

  const badgeClass =
    lead.bucket === "hot" ? "bg-hot-soft text-hot" : lead.bucket === "warm" ? "bg-warm-soft text-warm" : "bg-cold-soft text-cold";

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="relative h-full w-full max-w-[480px] overflow-y-auto bg-panel p-7 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="absolute right-6 top-6 rounded-md p-1 text-2xl leading-none text-text/75 transition-colors hover:bg-border/60 hover:text-heading"
          onClick={onClose}
        >
          ×
        </button>
        <h2 className="text-xl font-semibold text-heading">{lead.company_name}</h2>
        <p className="mt-0.5 text-sm text-text/75">{lead.domain}</p>
        <span className={`mt-3 inline-block rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${badgeClass}`}>
          {lead.bucket.toUpperCase()}
        </span>

        <section>
          <h3 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wide text-text/70">Firmographics</h3>
          <dl className="grid grid-cols-[110px_1fr] gap-y-1.5 gap-x-2.5 text-sm">
            <dt className="text-text/75">Industry</dt>
            <dd className="text-heading">{lead.industry}</dd>
            <dt className="text-text/75">Employees</dt>
            <dd className="text-heading">{lead.employee_count?.toLocaleString()}</dd>
            <dt className="text-text/75">Revenue</dt>
            <dd className="text-heading">{lead.revenue_usd ? `$${lead.revenue_usd.toLocaleString()}` : "—"}</dd>
            <dt className="text-text/75">Geography</dt>
            <dd className="text-heading">{lead.geography}</dd>
            <dt className="text-text/75">Contact</dt>
            <dd className="text-heading">
              {lead.contact_name} ({lead.contact_title})
            </dd>
            <dt className="text-text/75">Tech stack</dt>
            <dd className="text-heading">{lead.tech_stack.join(", ") || "—"}</dd>
            <dt className="text-text/75">Hiring</dt>
            <dd className="text-heading">{lead.is_hiring ? "Yes" : "No"}</dd>
          </dl>
        </section>

        <section>
          <h3 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wide text-text/70">Score breakdown</h3>
          <div className="flex flex-col gap-1.5">
            {Object.entries(lead.score_breakdown).map(([key, value]) => (
              <div className="grid grid-cols-[130px_1fr_30px] items-center gap-2 text-xs" key={key}>
                <span className="text-text">{BREAKDOWN_LABELS[key] ?? key}</span>
                <div className="h-1.5 overflow-hidden rounded-full bg-border">
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{ width: `${Math.min(100, (value / 20) * 100)}%` }}
                  />
                </div>
                <span className="tabular-nums text-text/75">{value}</span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-sm text-text">
            Fit score <strong className="text-heading">{lead.fit_score}</strong> · LLM likelihood{" "}
            <strong className="text-heading">{lead.conversion_likelihood}</strong> · Combined{" "}
            <strong className="text-heading">{lead.combined_score}</strong>
          </p>
        </section>

        <section>
          <h3 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wide text-text/70">LLM rationale</h3>
          <p className="text-sm leading-relaxed text-text">{lead.llm_rationale}</p>
        </section>

        <section>
          <h3 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wide text-text/70">Outreach draft</h3>
          <div className="flex flex-wrap items-center gap-2">
            <button
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                channel === "email" ? "border-accent bg-accent-soft text-accent" : "border-border text-text hover:border-accent/40"
              }`}
              onClick={() => setChannel("email")}
            >
              Email
            </button>
            <button
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                channel === "linkedin" ? "border-accent bg-accent-soft text-accent" : "border-border text-text hover:border-accent/40"
              }`}
              onClick={() => setChannel("linkedin")}
            >
              LinkedIn
            </button>
            <button
              className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={busy === "outreach"}
              onClick={handleDraft}
            >
              {busy === "outreach" ? "Drafting…" : "Generate draft"}
            </button>
          </div>
          {draft && (
            <pre className="mt-2.5 whitespace-pre-wrap rounded-lg bg-accent-soft p-3 font-mono text-xs text-heading">
              {draft}
            </pre>
          )}
        </section>

        <section>
          <h3 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wide text-text/70">CRM</h3>
          <button
            className="rounded-md border border-accent/40 bg-accent-soft px-3 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={busy === "crm"}
            onClick={handleCrmPush}
          >
            {busy === "crm" ? "Pushing…" : lead.crm_pushed ? "Push again to HubSpot" : "Push to HubSpot"}
          </button>
          {crmStatus && <p className="mt-2 text-sm text-text/75">{crmStatus}</p>}
        </section>
      </div>
    </div>
  );
}
