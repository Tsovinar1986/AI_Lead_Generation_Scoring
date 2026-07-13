import { useEffect, useState } from "react";
import { fetchLicenseStatus, startCheckout } from "../api";
import type { LicenseStatus } from "../types";

export function LicenseBanner() {
  const [status, setStatus] = useState<LicenseStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLicenseStatus()
      .then(setStatus)
      .catch(() => setStatus({ licensed: false }));
  }, []);

  async function handleBuy() {
    setBusy(true);
    setError(null);
    try {
      const { checkout_url } = await startCheckout();
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start checkout");
      setBusy(false);
    }
  }

  if (status === null) return null;

  if (status.licensed) {
    return (
      <div className="panel license-banner license-banner-active">
        <span>
          Licensed to <strong>{status.customer_email}</strong> ({status.plan} plan)
          {status.expires_at && (
            <span className="muted"> — renews {new Date(status.expires_at * 1000).toLocaleDateString()}</span>
          )}
        </span>
      </div>
    );
  }

  return (
    <div className="panel license-banner license-banner-trial">
      <span>Running in trial mode — full functionality, nothing saved beyond this session.</span>
      <div className="license-banner-actions">
        <button className="primary" disabled={busy} onClick={handleBuy}>
          {busy ? "Redirecting…" : "Buy a license"}
        </button>
        {error && <span className="error">{error}</span>}
      </div>
    </div>
  );
}
