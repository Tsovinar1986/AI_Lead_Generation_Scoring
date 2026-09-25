import { useEffect, useRef, useState } from "react";
import { activatePayPalSubscription } from "../api";
import { loadPayPalSdk, openPayPalCheckout } from "../paypal";
import type { BillingConfig, BillingInterval, PaidTier, SubscriptionActivation } from "../types";

interface Props {
  config: BillingConfig;
  tier: PaidTier;
  interval: BillingInterval;
  onClose: () => void;
}

type Phase =
  | { kind: "loading" }
  | { kind: "ready" }
  | { kind: "activating" }
  | { kind: "done"; result: SubscriptionActivation }
  | { kind: "error"; message: string; sdkFailed?: boolean };

const TIER_LABEL: Record<PaidTier, string> = { pro: "Pro", advanced: "Advanced" };

function priceFor(config: BillingConfig, tier: PaidTier, interval: BillingInterval): string | null | undefined {
  if (tier === "advanced") return interval === "annual" ? config.price_advanced_annual : config.price_advanced_monthly;
  return interval === "annual" ? config.price_annual : config.price_monthly;
}

// In-page PayPal subscription checkout: PayPal's own buttons open a PayPal
// popup, and on approval the backend verifies the subscription and hands the
// license key straight back -- the buyer never leaves the app.
export function PayPalSubscribe({ config, tier, interval, onClose }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [copied, setCopied] = useState(false);
  const planId = config.plans?.[`${tier}_${interval}`];

  useEffect(() => {
    if (!config.paypal_available || !config.client_id || !planId) {
      setPhase({ kind: "error", message: "PayPal isn't configured on this deployment." });
      return;
    }
    let cancelled = false;
    let buttons: { close(): Promise<void> } | null = null;
    setPhase({ kind: "loading" });

    loadPayPalSdk(config.client_id, config.currency ?? "USD")
      .then((paypal) => {
        if (cancelled || !containerRef.current) return;
        const instance = paypal.Buttons({
          style: { layout: "vertical", shape: "rect", label: "subscribe" },
          createSubscription: (_data, actions) => actions.subscription.create({ plan_id: planId }),
          onApprove: async (data) => {
            if (!data.subscriptionID) {
              setPhase({ kind: "error", message: "PayPal didn't return a subscription." });
              return;
            }
            setPhase({ kind: "activating" });
            try {
              const result = await activatePayPalSubscription(data.subscriptionID);
              setPhase({ kind: "done", result });
            } catch (err) {
              setPhase({
                kind: "error",
                message:
                  (err instanceof Error ? err.message : "Couldn't confirm your subscription.") +
                  " Your license key will be emailed as soon as PayPal confirms the payment.",
              });
            }
          },
          onError: () => setPhase({ kind: "error", message: "PayPal checkout failed. Please try again." }),
        });
        buttons = instance;
        return instance.render(containerRef.current).then(() => {
          if (!cancelled) setPhase({ kind: "ready" });
        });
      })
      .catch((err) => {
        if (!cancelled) {
          setPhase({ kind: "error", message: err instanceof Error ? err.message : "Couldn't load PayPal.", sdkFailed: true });
        }
      });

    return () => {
      cancelled = true;
      buttons?.close().catch(() => undefined);
    };
  }, [config, tier, interval, planId]);

  async function copyKey(key: string) {
    try {
      await navigator.clipboard.writeText(key);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const price = priceFor(config, tier, interval);
  const period = interval === "annual" ? "year" : "month";

  return (
    <div className="w-full rounded-lg border border-border bg-panel p-4 text-sm text-text shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-heading">
            {TIER_LABEL[tier]} — {price ? `$${Number(price)}/${period}` : interval}
          </p>
          <p className="text-xs text-text/75">Billed every {period} through PayPal. Cancel anytime from your PayPal account.</p>
        </div>
        {phase.kind !== "activating" && (
          <button className="text-xs text-text/70 underline hover:text-heading" onClick={onClose}>
            {phase.kind === "done" ? "Close" : "Cancel"}
          </button>
        )}
      </div>

      {phase.kind === "done" ? (
        <div className="mt-3 space-y-2" role="status">
          {phase.result.status === "ok" ? (
            <>
              <p className="text-heading">
                You're subscribed. Your license key (also emailed to <strong>{phase.result.email}</strong>):
              </p>
              <div className="flex items-center gap-2">
                <code className="block flex-1 truncate rounded bg-accent-soft px-2 py-1 font-mono text-xs text-heading">
                  {phase.result.license_key}
                </code>
                <button
                  className="rounded-md border border-accent/40 px-3 py-1 text-xs font-medium text-accent hover:bg-accent-soft"
                  onClick={() => copyKey((phase.result as { license_key: string }).license_key)}
                >
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <p className="text-xs text-text/75">
                Set it as <code className="font-mono">LICENSE_KEY</code> in your <code className="font-mono">.env</code> and
                restart. A fresh key is emailed on every renewal.
              </p>
            </>
          ) : (
            <p className="text-heading">You're subscribed. Your license key has been emailed to you.</p>
          )}
        </div>
      ) : (
        <>
          {phase.kind === "loading" && <p className="mt-3 text-text/75">Loading PayPal…</p>}
          {phase.kind === "activating" && <p className="mt-3 text-text/75">Confirming your subscription…</p>}
          {phase.kind === "error" && (
            <div className="mt-3 space-y-2">
              <p className="text-hot">{phase.message}</p>
              {phase.sdkFailed && (
                <button
                  className="text-xs font-medium text-accent underline"
                  onClick={() =>
                    openPayPalCheckout(interval, tier).catch((err) =>
                      setPhase({ kind: "error", message: err instanceof Error ? err.message : "Couldn't start checkout" })
                    )
                  }
                >
                  Continue on PayPal's website instead
                </button>
              )}
            </div>
          )}
          <div
            ref={containerRef}
            className={phase.kind === "ready" || phase.kind === "loading" ? "mt-3 max-w-sm" : "hidden"}
            data-testid="paypal-buttons"
          />
        </>
      )}
    </div>
  );
}
