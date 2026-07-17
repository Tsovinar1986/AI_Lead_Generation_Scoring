import { initializePaddle, type Paddle } from "@paddle/paddle-js";
import { fetchBillingConfig } from "./api";
import type { BillingInterval } from "./types";

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
export async function openPaddleCheckout(interval: BillingInterval): Promise<void> {
  const config = await fetchBillingConfig();
  const priceId = interval === "annual" ? config.price_id_annual : config.price_id_monthly;
  if (!priceId) {
    throw new Error(`Paddle isn't configured for the ${interval} plan on this deployment.`);
  }

  const paddle = await getPaddle();
  if (!paddle) {
    throw new Error("Paddle isn't configured on this deployment.");
  }

  paddle.Checkout.open({ items: [{ priceId, quantity: 1 }] });
}
