import type { DropinCreateOptions, DropinNamespace, DropinPaymentMethod } from "../braintree";
import type { BillingConfig } from "../types";

export const configured: BillingConfig = {
  checkout_available: true,
  currency: "USD",
  environment: "sandbox",
  plans: { pro_monthly: "pro-m", pro_annual: "pro-a", advanced_monthly: "adv-m", advanced_annual: "adv-a" },
  price_monthly: "20.00",
  price_annual: "192.00",
  price_advanced_monthly: "40.00",
  price_advanced_annual: "384.00",
};

// Stands in for Braintree's Drop-in: records create() options and lets a test
// decide what requestPaymentMethod() resolves with, the way a filled-in (or
// incomplete) card form would.
export function fakeDropin(method: DropinPaymentMethod | Error = { nonce: "nonce-1", deviceData: "dd" }) {
  let options: DropinCreateOptions | undefined;
  const teardown = { count: 0 };
  const namespace: DropinNamespace = {
    create(opts) {
      options = opts;
      return Promise.resolve({
        requestPaymentMethod: () => (method instanceof Error ? Promise.reject(method) : Promise.resolve(method)),
        teardown: () => {
          teardown.count += 1;
          return Promise.resolve();
        },
      });
    },
  };
  return { namespace, options: () => options, teardown };
}
