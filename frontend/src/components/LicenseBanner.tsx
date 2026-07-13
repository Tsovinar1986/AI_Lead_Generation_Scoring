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
      .catch(() => setStatus({ licensed: false, reason: "none", customer_email: null, plan: null }));
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

  // A buyer who already paid but has a stale/expired key must never see the
  // same "you're on a trial" copy as someone who's never purchased -- that
  // reads as "your payment didn't go through" and risks a double-charge.
  const { message, showBuyButton, buyLabel } =
    status.reason === "expired"
      ? {
          message: `Your license${status.customer_email ? ` for ${status.customer_email}` : ""} has expired — renew to keep syncing to your CRM/Slack.`,
          showBuyButton: true,
          buyLabel: "Renew license",
        }
      : status.reason === "invalid"
        ? {
            message: "Your license key couldn't be verified — double-check LICENSE_KEY in your .env, or contact support if you believe this is a mistake.",
            showBuyButton: false,
            buyLabel: "",
          }
        : {
            message: "Running in trial mode — full functionality for evaluation.",
            showBuyButton: true,
            buyLabel: "Buy a license",
          };

  return (
    <div className={`panel license-banner license-banner-${status.reason === "invalid" ? "error" : "trial"}`}>
      <span>{message}</span>
      <div className="license-banner-actions">
        {showBuyButton && (
          <button className="primary" disabled={busy} onClick={handleBuy}>
            {busy ? "Redirecting…" : buyLabel}
          </button>
        )}
        {error && <span className="error">{error}</span>}
      </div>
    </div>
  );
}
