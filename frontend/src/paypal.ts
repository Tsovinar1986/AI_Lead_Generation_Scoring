import { createPayPalCheckout } from "./api";
import type { BillingInterval, PaidTier } from "./types";

export type { PaidTier };

// Just the slice of PayPal's JS SDK (https://developer.paypal.com/sdk/js/)
// this app uses: subscription buttons.
export interface PayPalButtonsInstance {
  render(container: HTMLElement): Promise<void>;
  close(): Promise<void>;
}

export interface PayPalButtonsOptions {
  style?: Record<string, string>;
  createSubscription: (data: unknown, actions: { subscription: { create(o: { plan_id: string }): Promise<string> } }) => Promise<string>;
  onApprove: (data: { subscriptionID?: string | null }) => Promise<void>;
  onCancel?: () => void;
  onError?: (err: unknown) => void;
}

export interface PayPalNamespace {
  Buttons(options: PayPalButtonsOptions): PayPalButtonsInstance;
}

declare global {
  interface Window {
    paypal?: PayPalNamespace;
  }
}

let sdkPromise: Promise<PayPalNamespace> | null = null;

// Loads the SDK once per page, configured for subscriptions
// (vault=true&intent=subscription is required for createSubscription).
export function loadPayPalSdk(clientId: string, currency = "USD"): Promise<PayPalNamespace> {
  if (sdkPromise) return sdkPromise;
  sdkPromise = new Promise<PayPalNamespace>((resolve, reject) => {
    const params = new URLSearchParams({
      "client-id": clientId,
      currency,
      vault: "true",
      intent: "subscription",
      components: "buttons",
    });
    const script = document.createElement("script");
    script.src = `https://www.paypal.com/sdk/js?${params}`;
    script.async = true;
    script.onload = () => (window.paypal ? resolve(window.paypal) : reject(new Error("PayPal failed to load.")));
    script.onerror = () => reject(new Error("Couldn't load PayPal. Check your connection or ad blocker."));
    document.head.appendChild(script);
  }).catch((err) => {
    sdkPromise = null; // allow a retry
    throw err;
  });
  return sdkPromise;
}

// Fallback when the SDK can't load: full-page redirect to PayPal's hosted
// approval page. The backend handles activation on the way back.
export async function openPayPalCheckout(interval: BillingInterval, tier: PaidTier = "pro"): Promise<void> {
  const { url } = await createPayPalCheckout(interval, tier);
  window.location.href = url;
}
