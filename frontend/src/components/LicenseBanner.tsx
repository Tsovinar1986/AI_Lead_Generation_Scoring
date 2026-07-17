import { useEffect, useState } from "react";
import { fetchLicenseStatus } from "../api";
import { openPaddleCheckout } from "../paddle";
import type { BillingInterval, LicenseStatus } from "../types";

export function LicenseBanner() {
  const [status, setStatus] = useState<LicenseStatus | null>(null);
  const [busyInterval, setBusyInterval] = useState<BillingInterval | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLicenseStatus()
      .then(setStatus)
      .catch(() =>
        setStatus({ licensed: false, reason: "trial", customer_email: null, plan: null, trial_days_left: null })
      );
  }, []);

  async function handleBuy(interval: BillingInterval) {
    setBusyInterval(interval);
    setError(null);
    try {
      await openPaddleCheckout(interval);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start checkout");
    } finally {
      setBusyInterval(null);
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
  // Someone whose free trial window has simply run out (never paid) also
  // needs its own copy, distinct from "still evaluating."
  const { message, showBuyButtons } =
    status.reason === "expired"
      ? {
          message: `Your license${status.customer_email ? ` for ${status.customer_email}` : ""} has expired — renew to keep syncing to your CRM/Slack.`,
          showBuyButtons: true,
        }
      : status.reason === "invalid"
        ? {
            message: "Your license key couldn't be verified — double-check LICENSE_KEY in your .env, or contact support if you believe this is a mistake.",
            showBuyButtons: false,
          }
        : status.reason === "trial_expired"
          ? {
              message: "Your 3-day trial has ended — buy a license to keep scoring leads.",
              showBuyButtons: true,
            }
          : {
              message:
                status.trial_days_left != null
                  ? `Trial mode — full functionality for evaluation, ${status.trial_days_left} day${status.trial_days_left === 1 ? "" : "s"} left.`
                  : "Running in trial mode — full functionality for evaluation.",
              showBuyButtons: true,
            };

  const bannerVariant = status.reason === "invalid" || status.reason === "trial_expired" ? "error" : "trial";

  return (
    <div className={`panel license-banner license-banner-${bannerVariant}`}>
      <span>{message}</span>
      <div className="license-banner-actions">
        {showBuyButtons && (
          <>
            <button className="primary" disabled={busyInterval !== null} onClick={() => handleBuy("monthly")}>
              {busyInterval === "monthly" ? "Opening checkout…" : "$30/mo"}
            </button>
            <button className="primary" disabled={busyInterval !== null} onClick={() => handleBuy("annual")}>
              {busyInterval === "annual" ? "Opening checkout…" : "Buy annual (save 2 months)"}
            </button>
          </>
        )}
        {error && <span className="error">{error}</span>}
      </div>
    </div>
  );
}
