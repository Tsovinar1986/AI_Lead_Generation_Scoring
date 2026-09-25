import { createPayPalCheckout, fetchBillingConfig } from "./api";
import type { BillingInterval } from "./types";

export type PaidTier = "pro" | "advanced";

export async function openPayPalCheckout(interval: BillingInterval, tier: PaidTier = "pro"): Promise<void> {
  const config = await fetchBillingConfig();
  if (!config.paypal_available) {
    throw new Error("PayPal isn't configured on this deployment.");
  }
  const { url } = await createPayPalCheckout(interval, tier);
  window.location.href = url;
}
