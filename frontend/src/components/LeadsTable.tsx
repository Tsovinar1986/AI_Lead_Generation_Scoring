import { downloadLeadsCsv } from "../csvExport";
import type { ScoredLead } from "../types";

interface Props {
  leads: ScoredLead[];
  selectedId: string | null;
  bucketFilter: "all" | "hot" | "warm" | "cold";
  onSelect: (lead: ScoredLead) => void;
  onBucketFilterChange: (bucket: "all" | "hot" | "warm" | "cold") => void;
}

const BUCKET_LABELS: Record<string, string> = {
  hot: "Hot",
  warm: "Warm",
  cold: "Cold",
};

export function LeadsTable({
  leads,
  selectedId,
  bucketFilter,
  onSelect,
  onBucketFilterChange,
}: Props) {
  const filtered =
    bucketFilter === "all" ? leads : leads.filter((l) => l.bucket === bucketFilter);

  const counts = leads.reduce(
    (acc, l) => {
      acc[l.bucket] = (acc[l.bucket] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="panel leads-panel">
      <div className="leads-header">
        <h2>Ranked leads ({filtered.length})</h2>
        <div className="bucket-filters">
          {(["all", "hot", "warm", "cold"] as const).map((b) => (
            <button
              key={b}
              className={`chip chip-${b} ${bucketFilter === b ? "chip-active" : ""}`}
              onClick={() => onBucketFilterChange(b)}
            >
              {b === "all" ? "All" : BUCKET_LABELS[b]}
              {b !== "all" ? ` (${counts[b] ?? 0})` : ""}
            </button>
          ))}
          <button
            className="chip"
            disabled={filtered.length === 0}
            onClick={() =>
              downloadLeadsCsv(
                filtered,
                bucketFilter === "all" ? "scored-leads.csv" : `scored-leads-${bucketFilter}.csv`
              )
            }
          >
            Download CSV
          </button>
        </div>
      </div>

      {leads.length === 0 ? (
        <p className="muted">No leads yet — upload a file to get started.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>Industry</th>
                <th>Contact</th>
                <th>Fit</th>
                <th>LLM</th>
                <th>Combined</th>
                <th>Bucket</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((lead) => (
                <tr
                  key={lead.id}
                  className={lead.id === selectedId ? "row-selected" : ""}
                  onClick={() => onSelect(lead)}
                >
                  <td>
                    <div className="company-cell">
                      <strong>{lead.company_name}</strong>
                      <span className="muted">{lead.domain}</span>
                    </div>
                  </td>
                  <td>{lead.industry}</td>
                  <td>
                    <div className="company-cell">
                      <span>{lead.contact_name ?? "—"}</span>
                      <span className="muted">{lead.contact_title}</span>
                    </div>
                  </td>
                  <td>{lead.fit_score.toFixed(0)}</td>
                  <td>{lead.conversion_likelihood.toFixed(0)}</td>
                  <td>
                    <strong>{lead.combined_score.toFixed(0)}</strong>
                  </td>
                  <td>
                    <span className={`badge badge-${lead.bucket}`}>
                      {BUCKET_LABELS[lead.bucket]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
