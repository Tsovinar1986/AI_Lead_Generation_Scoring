import { type FormEvent, useEffect, useRef, useState } from "react";
import { fetchBraintreeClientToken, subscribeWithBraintree } from "../api";
import { type DropinInstance, loadDropin } from "../braintree";
import type { BillingConfig, BillingInterval, PaidTier, SubscriptionActivation } from "../types";

interface Props {
  config: BillingConfig;
  tier: PaidTier;
  interval: BillingInterval;
  onClose: () => void;
  // Hosted deployment: the current workspace was upgraded in place.
  onUpgraded?: () => void;
}

type Phase =
  | { kind: "loading" }
  | { kind: "ready"; error?: string }
  | { kind: "paying" }
  | { kind: "done"; result: SubscriptionActivation }
  | { kind: "failed"; message: string };

const TIER_LABEL: Record<PaidTier, string> = { pro: "Pro", advanced: "Advanced" };

function priceFor(config: BillingConfig, tier: PaidTier, interval: BillingInterval): string | null | undefined {
  if (tier === "advanced") return interval === "annual" ? config.price_advanced_annual : config.price_advanced_monthly;
  return interval === "annual" ? config.price_annual : config.price_monthly;
}

// In-page card checkout: Braintree's Drop-in renders the card fields in its
// own iframes and hands back a one-time nonce; the backend starts the
// subscription with it and returns the license key -- the buyer never leaves
// the app, and card details never touch our servers.
export function BraintreeSubscribe({ config, tier, interval, onClose, onUpgraded }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const dropinRef = useRef<DropinInstance | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!config.checkout_available) {
      setPhase({ kind: "failed", message: "Checkout isn't configured on this deployment." });
      return;
    }
    let cancelled = false;
    setPhase({ kind: "loading" });

    Promise.all([loadDropin(), fetchBraintreeClientToken()])
      .then(([dropin, authorization]) => {
        if (cancelled || !containerRef.current) return;
        return dropin
          .create({ authorization, container: containerRef.current, card: { cardholderName: { required: true } }, dataCollector: true })
          .then((instance) => {
            if (cancelled) {
              instance.teardown().catch(() => undefined);
              return;
            }
            dropinRef.current = instance;
            setPhase({ kind: "ready" });
          });
      })
      .catch((err) => {
        if (!cancelled) setPhase({ kind: "failed", message: err instanceof Error ? err.message : "Couldn't load checkout." });
      });

    return () => {
      cancelled = true;
      dropinRef.current?.teardown().catch(() => undefined);
      dropinRef.current = null;
    };
  }, [config, tier, interval]);

  async function pay(event: FormEvent) {
    event.preventDefault();
    const dropin = dropinRef.current;
    if (!dropin) return;
    let method;
    try {
      // Rejects (and Drop-in highlights the field) if the card form is incomplete.
      method = await dropin.requestPaymentMethod();
    } catch {
      setPhase({ kind: "ready", error: "Please complete your card details." });
      return;
    }
    setPhase({ kind: "paying" });
    try {
      const result = await subscribeWithBraintree({
        tier,
        interval,
        payment_method_nonce: method.nonce,
        device_data: method.deviceData,
      });
      setPhase({ kind: "done", result });
    } catch (err) {
      setPhase({ kind: "ready", error: err instanceof Error ? err.message : "Payment failed. Please try again." });
    }
  }

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
  const showForm = phase.kind === "loading" || phase.kind === "ready" || phase.kind === "paying";

  return (
    <div className="w-full rounded-lg border border-border bg-panel p-4 text-sm text-text shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-heading">
            {TIER_LABEL[tier]} — {price ? `$${Number(price)}/${period}` : interval}
          </p>
          <p className="text-xs text-text/75">
            Billed every {period} by card. Cancel anytime by emailing hello@crmscoring.com.
          </p>
        </div>
        {phase.kind !== "paying" && (
          <button className="text-xs text-text/70 underline hover:text-heading" onClick={onClose}>
            {phase.kind === "done" ? "Close" : "Cancel"}
          </button>
        )}
      </div>

      {phase.kind === "done" && (
        <div className="mt-3 space-y-2" role="status">
          {phase.result.status === "ok" && phase.result.workspace_upgraded ? (
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-heading">
                You're subscribed — this workspace is now on {TIER_LABEL[tier]} with unlimited uploads.
              </p>
              <button
                className="rounded-md bg-accent px-3 py-1 text-xs font-medium text-white"
                onClick={() => (onUpgraded ?? onClose)()}
              >
                Continue
              </button>
            </div>
          ) : phase.result.status === "ok" ? (
            <>
              <p className="text-heading">
                You're subscribed. Your license key
                {phase.result.email.includes("@") && (
                  <>
                    {" "}
                    (also emailed to <strong>{phase.result.email}</strong>)
                  </>
                )}
                :
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
                restart. Save it somewhere safe — you'll need a new key each billing period; email
                hello@crmscoring.com for it.
              </p>
            </>
          ) : (
            <p className="text-heading">You're subscribed. Email hello@crmscoring.com for your license key.</p>
          )}
        </div>
      )}

      {phase.kind === "failed" && <p className="mt-3 text-hot">{phase.message}</p>}

      {/* Stays mounted while loading/paying so Drop-in's iframes aren't torn down. */}
      <form onSubmit={pay} className={showForm ? "mt-3 max-w-sm space-y-2" : "hidden"}>
        {phase.kind === "loading" && <p className="text-text/75">Loading secure checkout…</p>}
        <div ref={containerRef} data-testid="braintree-dropin" />
        {phase.kind === "ready" && phase.error && <p className="text-hot">{phase.error}</p>}
        <button
          type="submit"
          disabled={phase.kind !== "ready"}
          className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          {phase.kind === "paying" ? "Processing…" : `Subscribe${price ? ` — $${Number(price)}/${period}` : ""}`}
        </button>
      </form>
    </div>
  );
}
