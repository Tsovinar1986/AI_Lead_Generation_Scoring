import { createPolarCheckout, fetchBillingConfig } from "./api";
import type { BillingInterval } from "./types";

// Polar has no client-side SDK/overlay like Paddle.js -- it's a redirect
// checkout, so this just asks the backend for a session URL and navigates
// there. An alternative processor to Paddle (not a fallback for it), for
// sellers Paddle can't serve either -- see backend/app/routers/billing.py.
export async function openPolarCheckout(interval: BillingInterval): Promise<void> {
  const config = await fetchBillingConfig();
  if (!config.polar_available) {
    throw new Error("Polar isn't configured on this deployment.");
  }

  const { url } = await createPolarCheckout(interval);
  window.location.href = url;
}
