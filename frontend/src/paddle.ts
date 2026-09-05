import { initializePaddle, type Paddle } from "@paddle/paddle-js";
import { fetchBillingConfig } from "./api";
import type { BillingConfig, BillingInterval } from "./types";

// Starter has no Paddle price -- it's the unlicensed default, never reaches
// checkout. Only "pro" and "advanced" resolve to a real price id here.
export type PaidTier = "pro" | "advanced";

function priceIdFor(config: BillingConfig, tier: PaidTier, interval: BillingInterval): string | null {
  if (tier === "advanced") {
    return interval === "annual" ? config.price_id_advanced_annual : config.price_id_advanced_monthly;
  }
  return interval === "annual" ? config.price_id_annual : config.price_id_monthly;
}

// Lazily initialized once per page load and cached -- every buy button
// (LicenseBanner, UploadPanel) shares the same Paddle instance instead of
// each re-fetching config and re-loading Paddle.js.
let paddlePromise: Promise<Paddle | null> | null = null;

function getPaddle(): Promise<Paddle | null> {
  if (!paddlePromise) {
    paddlePromise = fetchBillingConfig().then((config) => {
      if (!config.client_token) return null;
      return initializePaddle({
        token: config.client_token,
        environment: config.environment,
      }).then((paddle) => paddle ?? null);
    });
  }
  return paddlePromise;
}

// Opens Paddle's hosted overlay checkout directly from the browser -- no
// backend call to start it, no redirect, works the same on localhost as in
// production (unlike a backend-generated checkout link, which requires a
// real HTTPS "Default Payment Link" domain approved in the Paddle
// dashboard).
export async function openPaddleCheckout(interval: BillingInterval, tier: PaidTier = "pro"): Promise<void> {
  const config = await fetchBillingConfig();
  const priceId = priceIdFor(config, tier, interval);
  if (!priceId) {
    throw new Error(`Paddle isn't configured for the ${tier} ${interval} plan on this deployment.`);
  }

  const paddle = await getPaddle();
  if (!paddle) {
    throw new Error("Paddle isn't configured on this deployment.");
  }

  paddle.Checkout.open({ items: [{ priceId, quantity: 1 }] });
}
