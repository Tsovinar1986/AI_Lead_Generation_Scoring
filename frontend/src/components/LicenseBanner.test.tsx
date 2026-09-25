import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LicenseBanner } from "./LicenseBanner";
import * as api from "../api";
import * as paypal from "../paypal";

vi.mock("../api", async (importActual) => {
  const actual = await importActual<typeof api>();
  return { ...actual, fetchLicenseStatus: vi.fn(), fetchBillingConfig: vi.fn() };
});

vi.mock("../paypal", () => ({ openPayPalCheckout: vi.fn() }));

describe("LicenseBanner", () => {
  beforeEach(() => {
    // Most tests don't care about PayPal -- default it "off" so the extra
    // buttons don't show up unless a test explicitly opts in.
    vi.mocked(api.fetchBillingConfig).mockResolvedValue({
      client_token: null, environment: "sandbox", price_id_monthly: null, price_id_annual: null,
      price_id_advanced_monthly: null, price_id_advanced_annual: null, paypal_available: false,
    });
  });

  it("renders nothing until the license status has loaded", () => {
    vi.mocked(api.fetchLicenseStatus).mockReturnValue(new Promise(() => {}));
    const { container } = render(<LicenseBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows Starter messaging with uploads left and Pro/Advanced buy buttons when no license was ever set", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, tier: "starter", trial_uploads_left: 6,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/starter \(free\)/i)).toBeInTheDocument();
    expect(screen.getByText(/6 of 10 uploads left/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /pro — \$20\/mo/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /pro annual/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /advanced — \$40\/mo/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /advanced annual/i })).toBeInTheDocument();
  });

  it("shows the customer/tier when licensed", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: true, customer_email: "buyer@example.com", plan: "monthly", tier: "pro", expires_at: null,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/buyer@example.com/)).toBeInTheDocument();
    expect(screen.getByText(/pro plan/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /\$20\/mo/i })).not.toBeInTheDocument();
  });

  it("shows a distinct message once Starter's upload allowance runs out with no purchase", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial_expired", customer_email: null, plan: null, tier: "starter", trial_uploads_left: 0,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/trial has ended/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /pro — \$20\/mo/i })).toBeInTheDocument();
    expect(screen.queryByText(/starter \(free\)/i)).not.toBeInTheDocument();
  });

  it("shows a renew CTA (not Starter copy) when a paid license has expired", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "expired", customer_email: "buyer@example.com", plan: "monthly", tier: "pro", trial_uploads_left: null,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/expired/i)).toBeInTheDocument();
    expect(screen.getByText(/buyer@example.com/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /pro — \$20\/mo/i })).toBeInTheDocument();
    expect(screen.queryByText(/starter \(free\)/i)).not.toBeInTheDocument();
  });

  it("shows a config-check message (no buy buttons) for an invalid key, not a Starter/payment prompt", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "invalid", customer_email: null, plan: null, tier: "starter", trial_uploads_left: null,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/couldn't be verified/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /\$20\/mo/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/starter \(free\)/i)).not.toBeInTheDocument();
  });

  it("opens the PayPal checkout overlay for the selected tier/interval when a buy button is clicked", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, tier: "starter", trial_uploads_left: 5,
    });
    vi.mocked(paypal.openPayPalCheckout).mockResolvedValue(undefined);

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /pro annual/i }));

    await waitFor(() => expect(paypal.openPayPalCheckout).toHaveBeenCalledWith("annual", "pro"));
  });

  it("opens the PayPal checkout overlay for Advanced when its buy button is clicked", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, tier: "starter", trial_uploads_left: 5,
    });
    vi.mocked(paypal.openPayPalCheckout).mockResolvedValue(undefined);

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /advanced — \$40\/mo/i }));

    await waitFor(() => expect(paypal.openPayPalCheckout).toHaveBeenCalledWith("monthly", "advanced"));
  });

  it("shows an error message when PayPal checkout fails to open", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, tier: "starter", trial_uploads_left: 5,
    });
    vi.mocked(paypal.openPayPalCheckout).mockRejectedValue(new Error("PayPal isn't configured on this deployment."));

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /pro — \$20\/mo/i }));

    expect(await screen.findByText("PayPal isn't configured on this deployment.")).toBeInTheDocument();
  });

  it("does not show PayPal buttons when PayPal isn't configured on this deployment", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, tier: "starter", trial_uploads_left: 5,
    });

    render(<LicenseBanner />);

    await screen.findByRole("button", { name: /pro — \$20\/mo/i });
    expect(screen.queryByRole("button", { name: /pay with paypal/i })).not.toBeInTheDocument();
  });

  it("shows PayPal buttons and opens PayPal checkout when PayPal is configured", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, tier: "starter", trial_uploads_left: 5,
    });
    vi.mocked(api.fetchBillingConfig).mockResolvedValue({
      client_token: null, environment: "sandbox", price_id_monthly: null, price_id_annual: null,
      price_id_advanced_monthly: null, price_id_advanced_annual: null, paypal_available: true,
    });
    vi.mocked(paypal.openPayPalCheckout).mockResolvedValue(undefined);

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /pro annual/i }));

    await waitFor(() => expect(paypal.openPayPalCheckout).toHaveBeenCalledWith("annual", "pro"));
  });

  it("shows an error message when PayPal checkout fails to open", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, tier: "starter", trial_uploads_left: 5,
    });
    vi.mocked(api.fetchBillingConfig).mockResolvedValue({
      client_token: null, environment: "sandbox", price_id_monthly: null, price_id_annual: null,
      price_id_advanced_monthly: null, price_id_advanced_annual: null, paypal_available: true,
    });
    vi.mocked(paypal.openPayPalCheckout).mockRejectedValue(new Error("PayPal isn't configured on this deployment."));

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /pro — \$20\/mo/i }));

    expect(await screen.findByText("PayPal isn't configured on this deployment.")).toBeInTheDocument();
  });
});
