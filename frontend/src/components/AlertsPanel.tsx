import type { Alert } from "../types";

interface Props {
  alerts: Alert[];
}

export function AlertsPanel({ alerts }: Props) {
  return (
    <div className="min-h-[120px] rounded-xl border border-border bg-panel p-5 shadow-sm">
      <h2 className="text-base font-semibold text-heading">Slack alerts ({alerts.length})</h2>
      {alerts.length === 0 ? (
        <p className="mt-3 text-sm text-text/75">No hot leads yet.</p>
      ) : (
        <ul className="mt-3 flex max-h-[70vh] flex-col gap-2.5 overflow-y-auto">
          {alerts.map((a) => (
            <li key={a.id} className="rounded-lg bg-hot-soft px-3 py-2.5 text-xs leading-relaxed text-text">
              <p>{a.message}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
