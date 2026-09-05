import type { ScoreBreakdown, ScoredLead } from "../types";

// Matches backend/app/config.py's SCORING_WEIGHTS -- each dimension's raw
// score_breakdown value is out of this max, not out of 100, so a bar's fill
// is normalized to percent-of-its-own-max rather than compared on a shared
// 0-100 scale it was never scored on.
const DIMENSION_MAX: Record<keyof ScoreBreakdown, number> = {
  industry_match: 20,
  company_size_fit: 20,
  revenue_fit: 15,
  tech_stack_match: 15,
  geography_fit: 10,
  title_seniority: 10,
  hiring_signal: 10,
};

const DIMENSION_LABELS: Record<keyof ScoreBreakdown, string> = {
  industry_match: "Industry fit",
  company_size_fit: "Company size fit",
  revenue_fit: "Revenue fit",
  tech_stack_match: "Tech stack match",
  geography_fit: "Geography fit",
  title_seniority: "Title seniority",
  hiring_signal: "Hiring signal",
};

const DIMENSION_ORDER = Object.keys(DIMENSION_MAX) as (keyof ScoreBreakdown)[];

function pct(part: number, whole: number): number {
  return whole === 0 ? 0 : Math.round((part / whole) * 100);
}

interface KpiTileProps {
  label: string;
  value: string;
  sub?: string;
  accentVar?: string;
}

function KpiTile({ label, value, sub, accentVar }: KpiTileProps) {
  return (
    <div className="rounded-lg border border-border bg-bg px-3 py-2.5">
      <div className="text-xs text-text/75">{label}</div>
      <div className="mt-0.5 flex items-baseline gap-1.5">
        <span
          className="font-display text-xl font-semibold text-heading"
          style={accentVar ? { color: accentVar } : undefined}
        >
          {value}
        </span>
        {sub && <span className="text-xs text-text/60">{sub}</span>}
      </div>
    </div>
  );
}

interface BarRowProps {
  label: string;
  fillPct: number;
  valueLabel: string;
  colorVar: string;
  labelWidthClass: string;
  tooltip: string;
}

// A single labeled magnitude bar -- always paired with its category name and
// exact value as visible text (never color-alone), since Hot/Warm/Cold here
// reuse this app's existing status palette, which two adjacent hues (warm
// red/amber) don't clear on their own for every color-vision type.
function BarRow({ label, fillPct, valueLabel, colorVar, labelWidthClass, tooltip }: BarRowProps) {
  return (
    <div className="flex items-center gap-3" title={tooltip}>
      <span className={`shrink-0 text-xs font-medium text-text ${labelWidthClass}`}>{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full transition-[width] duration-500 ease-out"
          style={{ width: `${fillPct}%`, backgroundColor: colorVar }}
        />
      </div>
      <span className="w-20 shrink-0 text-right text-xs tabular-nums text-text/75">{valueLabel}</span>
    </div>
  );
}

interface Props {
  leads: ScoredLead[];
}

// Shown right after scoring (App.tsx, between UploadPanel and LeadsTable) --
// KPI tiles for the headline numbers, plus two small bar charts (bucket
// distribution, average score breakdown) so a seller can read the shape of a
// batch at a glance instead of scrolling the full per-lead table first.
export function ScoreDashboard({ leads }: Props) {
  if (leads.length === 0) return null;

  const total = leads.length;
  const hot = leads.filter((l) => l.bucket === "hot").length;
  const warm = leads.filter((l) => l.bucket === "warm").length;
  const cold = leads.filter((l) => l.bucket === "cold").length;
  const avgCombined = leads.reduce((sum, l) => sum + l.combined_score, 0) / total;
  const avgConversion = leads.reduce((sum, l) => sum + l.conversion_likelihood, 0) / total;

  const buckets: { key: string; label: string; count: number; colorVar: string }[] = [
    { key: "hot", label: "Hot", count: hot, colorVar: "var(--color-hot)" },
    { key: "warm", label: "Warm", count: warm, colorVar: "var(--color-warm)" },
    { key: "cold", label: "Cold", count: cold, colorVar: "var(--color-cold)" },
  ];
  const maxBucketCount = Math.max(hot, warm, cold, 1);

  const dimensionAverages = DIMENSION_ORDER.map((key) => {
    const avg = leads.reduce((sum, l) => sum + l.score_breakdown[key], 0) / total;
    return { key, label: DIMENSION_LABELS[key], avg, max: DIMENSION_MAX[key] };
  });

  return (
    <div className="rounded-xl border border-border bg-panel p-5 shadow-sm">
      <h2 className="font-display text-lg font-semibold text-heading">Scoring overview</h2>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <KpiTile label="Total leads" value={String(total)} />
        <KpiTile label="Hot" value={String(hot)} sub={`${pct(hot, total)}%`} accentVar="var(--color-hot)" />
        <KpiTile label="Warm" value={String(warm)} sub={`${pct(warm, total)}%`} accentVar="var(--color-warm)" />
        <KpiTile label="Cold" value={String(cold)} sub={`${pct(cold, total)}%`} accentVar="var(--color-cold)" />
        <KpiTile label="Avg score" value={avgCombined.toFixed(0)} sub="/ 100" />
        <KpiTile label="Avg conversion" value={`${avgConversion.toFixed(0)}%`} sub="likelihood" />
      </div>

      <div className="mt-6 grid gap-x-8 gap-y-6 lg:grid-cols-2">
        <div>
          <h3 className="text-sm font-medium text-heading">Bucket distribution</h3>
          <div className="mt-3 flex flex-col gap-2.5">
            {buckets.map((b) => (
              <BarRow
                key={b.key}
                label={b.label}
                fillPct={pct(b.count, maxBucketCount)}
                valueLabel={`${b.count} (${pct(b.count, total)}%)`}
                colorVar={b.colorVar}
                labelWidthClass="w-12"
                tooltip={`${b.label}: ${b.count} of ${total} leads (${pct(b.count, total)}%)`}
              />
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-sm font-medium text-heading">Average score breakdown</h3>
          <div className="mt-3 flex flex-col gap-2.5">
            {dimensionAverages.map((d) => (
              <BarRow
                key={d.key}
                label={d.label}
                fillPct={pct(d.avg, d.max)}
                valueLabel={`${d.avg.toFixed(1)}/${d.max}`}
                colorVar="var(--color-accent)"
                labelWidthClass="w-32"
                tooltip={`${d.label}: averages ${d.avg.toFixed(1)} of ${d.max} points across ${total} leads`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
