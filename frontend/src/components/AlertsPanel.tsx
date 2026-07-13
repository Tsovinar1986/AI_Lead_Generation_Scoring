import type { Alert } from "../types";

interface Props {
  alerts: Alert[];
}

export function AlertsPanel({ alerts }: Props) {
  return (
    <div className="panel alerts-panel">
      <h2>Slack alerts ({alerts.length})</h2>
      {alerts.length === 0 ? (
        <p className="muted">No hot leads yet.</p>
      ) : (
        <ul className="alerts-list">
          {alerts.map((a) => (
            <li key={a.id}>
              <p>{a.message}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
