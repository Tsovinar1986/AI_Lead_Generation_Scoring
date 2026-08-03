import { useEffect, useState } from "react";
import { fetchBillingConfig, fetchLicenseStatus } from "../api";
import { openPaddleCheckout } from "../paddle";
import { openPolarCheckout } from "../polar";
import type { BillingInterval, LicenseStatus } from "../types";

type BuyKey = `${"paddle" | "polar"}-${BillingInterval}`;

const btnPrimary =
  "rounded-md bg-accent px-4 py-2 text-sm font-medium text-white shadow-sm transition-all hover:-translate-y-px hover:shadow-md active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-sm";
const btnSecondary =
  "rounded-md border border-accent/40 bg-accent-soft px-4 py-2 text-sm font-medium text-accent transition-all hover:-translate-y-px hover:bg-accent/20 active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0";

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12 8v4.5l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="M10.9 4.6 2.9 18a2 2 0 0 0 1.7 3h14.8a2 2 0 0 0 1.7-3l-8-13.4a2 2 0 0 0-3.4 0Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M12 10v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="12" cy="17" r="0.9" fill="currentColor" />
    </svg>
  );
}

function CheckBadgeIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="m9 12 2 2 4-4M12 3.5l1.9 1.1 2.2-.2 1.1 1.9 1.9 1.1-.2 2.2 1.1 1.9-1.9 1.1-1.1 1.9-2.2-.2L12 14.5l-1.9-1.1-2.2.2-1.1-1.9-1.9-1.1.2-2.2-1.1-1.9 1.9-1.1 1.1-1.9 2.2.2Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function LicenseBanner() {
  const [status, setStatus] = useState<LicenseStatus | null>(null);
  const [polarAvailable, setPolarAvailable] = useState(false);
  const [busyKey, setBusyKey] = useState<BuyKey | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLicenseStatus()
      .then(setStatus)
      .catch(() =>
        setStatus({ licensed: false, reason: "trial", customer_email: null, plan: null, trial_days_left: null })
      );
    fetchBillingConfig()
      .then((config) => setPolarAvailable(config.polar_available))
      .catch(() => setPolarAvailable(false));
  }, []);

  async function handleBuy(interval: BillingInterval) {
    setBusyKey(`paddle-${interval}`);
    setError(null);
    try {
      await openPaddleCheckout(interval);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start checkout");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleBuyWithPolar(interval: BillingInterval) {
    setBusyKey(`polar-${interval}`);
    setError(null);
    try {
      await openPolarCheckout(interval);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start checkout");
    } finally {
      setBusyKey(null);
    }
  }

  if (status === null) return null;

  if (status.licensed) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-border bg-panel px-5 py-3 text-sm shadow-sm">
        <CheckBadgeIcon className="h-4 w-4 shrink-0 text-accent" />
        <span className="text-text">
          Licensed to <strong className="text-heading">{status.customer_email}</strong> ({status.plan} plan)
          {status.expires_at && (
            <span className="text-text/75"> — renews {new Date(status.expires_at * 1000).toLocaleDateString()}</span>
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

  const isError = status.reason === "invalid" || status.reason === "trial_expired";

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border px-5 py-3 text-sm shadow-sm ${
        isError ? "border-hot/30 bg-hot-soft text-hot" : "border-warm/30 bg-warm-soft text-warm"
      }`}
    >
      <span className="flex items-center gap-2.5">
        {isError ? (
          <AlertIcon className="h-4 w-4 shrink-0" />
        ) : (
          <ClockIcon className="h-4 w-4 shrink-0" />
        )}
        {message}
      </span>
      <div className="flex flex-wrap items-center gap-2">
        {showBuyButtons && (
          <>
            <button className={btnPrimary} disabled={busyKey !== null} onClick={() => handleBuy("monthly")}>
              {busyKey === "paddle-monthly" ? "Opening checkout…" : "$30/mo"}
            </button>
            <button className={btnPrimary} disabled={busyKey !== null} onClick={() => handleBuy("annual")}>
              {busyKey === "paddle-annual" ? "Opening checkout…" : "Buy annual (save 2 months)"}
            </button>
            {polarAvailable && (
              <>
                <button
                  className={btnSecondary}
                  disabled={busyKey !== null}
                  onClick={() => handleBuyWithPolar("monthly")}
                >
                  {busyKey === "polar-monthly" ? "Opening checkout…" : "Pay with Polar — $30/mo"}
                </button>
                <button
                  className={btnSecondary}
                  disabled={busyKey !== null}
                  onClick={() => handleBuyWithPolar("annual")}
                >
                  {busyKey === "polar-annual" ? "Opening checkout…" : "Pay with Polar — annual"}
                </button>
              </>
            )}
          </>
        )}
        {error && <span className="text-hot">{error}</span>}
      </div>
    </div>
  );
}
