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

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <button className="close-btn" onClick={onClose}>
          ×
        </button>
        <h2>{lead.company_name}</h2>
        <p className="muted">{lead.domain}</p>
        <span className={`badge badge-${lead.bucket}`}>{lead.bucket.toUpperCase()}</span>

        <section>
          <h3>Firmographics</h3>
          <dl className="kv">
            <dt>Industry</dt>
            <dd>{lead.industry}</dd>
            <dt>Employees</dt>
            <dd>{lead.employee_count?.toLocaleString()}</dd>
            <dt>Revenue</dt>
            <dd>{lead.revenue_usd ? `$${lead.revenue_usd.toLocaleString()}` : "—"}</dd>
            <dt>Geography</dt>
            <dd>{lead.geography}</dd>
            <dt>Contact</dt>
            <dd>
              {lead.contact_name} ({lead.contact_title})
            </dd>
            <dt>Tech stack</dt>
            <dd>{lead.tech_stack.join(", ") || "—"}</dd>
            <dt>Hiring</dt>
            <dd>{lead.is_hiring ? "Yes" : "No"}</dd>
          </dl>
        </section>

        <section>
          <h3>Score breakdown</h3>
          <div className="breakdown">
            {Object.entries(lead.score_breakdown).map(([key, value]) => (
              <div className="breakdown-row" key={key}>
                <span>{BREAKDOWN_LABELS[key] ?? key}</span>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ width: `${Math.min(100, (value / 20) * 100)}%` }}
                  />
                </div>
                <span className="muted">{value}</span>
              </div>
            ))}
          </div>
          <p>
            Fit score <strong>{lead.fit_score}</strong> · LLM likelihood{" "}
            <strong>{lead.conversion_likelihood}</strong> · Combined{" "}
            <strong>{lead.combined_score}</strong>
          </p>
        </section>

        <section>
          <h3>LLM rationale</h3>
          <p className="rationale">{lead.llm_rationale}</p>
        </section>

        <section>
          <h3>Outreach draft</h3>
          <div className="channel-toggle">
            <button
              className={channel === "email" ? "chip chip-active" : "chip"}
              onClick={() => setChannel("email")}
            >
              Email
            </button>
            <button
              className={channel === "linkedin" ? "chip chip-active" : "chip"}
              onClick={() => setChannel("linkedin")}
            >
              LinkedIn
            </button>
            <button className="primary" disabled={busy === "outreach"} onClick={handleDraft}>
              {busy === "outreach" ? "Drafting…" : "Generate draft"}
            </button>
          </div>
          {draft && <pre className="draft-box">{draft}</pre>}
        </section>

        <section>
          <h3>CRM</h3>
          <button className="secondary" disabled={busy === "crm"} onClick={handleCrmPush}>
            {busy === "crm" ? "Pushing…" : lead.crm_pushed ? "Push again to HubSpot" : "Push to HubSpot"}
          </button>
          {crmStatus && <p className="muted">{crmStatus}</p>}
        </section>
      </div>
    </div>
  );
}
