import { act } from "@testing-library/react";
import type { PayPalButtonsOptions, PayPalNamespace } from "../paypal";
import type { BillingConfig } from "../types";

export const configured: BillingConfig = {
  paypal_available: true,
  client_id: "client-123",
  currency: "USD",
  environment: "sandbox",
  plans: { pro_monthly: "P-PRO-M", pro_annual: "P-PRO-A", advanced_monthly: "P-ADV-M", advanced_annual: "P-ADV-A" },
  price_monthly: "20.00",
  price_annual: "192.00",
  price_advanced_monthly: "40.00",
  price_advanced_annual: "384.00",
};

// Stands in for PayPal's JS SDK: records the Buttons() options so a test can
// drive createSubscription/onApprove the way PayPal's popup would.
export function fakePayPal() {
  let options: PayPalButtonsOptions | undefined;
  let created: { plan_id: string } | undefined;
  const namespace: PayPalNamespace = {
    Buttons(opts) {
      options = opts;
      return { render: () => Promise.resolve(), close: () => Promise.resolve() };
    },
  };
  return {
    namespace,
    options: () => options,
    createdWith: () => created,
    createSubscription: () =>
      options!.createSubscription(
        {},
        {
          subscription: {
            create: (o) => {
              created = o;
              return Promise.resolve("I-NEW");
            },
          },
        }
      ),
    approve: (subscriptionID: string) => act(() => options!.onApprove({ subscriptionID })),
  };
}
