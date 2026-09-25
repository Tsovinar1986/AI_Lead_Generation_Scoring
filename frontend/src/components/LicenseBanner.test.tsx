import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LicenseBanner } from "./LicenseBanner";
import * as api from "../api";
import * as paypal from "../paypal";
import { configured, fakePayPal } from "../test/paypalFixtures";

vi.mock("../api", async (importActual) => {
  const actual = await importActual<typeof api>();
  return {
    ...actual,
    fetchLicenseStatus: vi.fn(),
    fetchBillingConfig: vi.fn(),
    activatePayPalSubscription: vi.fn(),
  };
});

vi.mock("../paypal", () => ({ loadPayPalSdk: vi.fn(), openPayPalCheckout: vi.fn() }));

const trial = {
  licensed: false as const, reason: "trial" as const, customer_email: null, plan: null, tier: "starter" as const, trial_uploads_left: 5,
};

describe("LicenseBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Most tests don't care about PayPal -- default it "off" so the extra
    // buttons don't show up unless a test explicitly opts in.
    vi.mocked(api.fetchBillingConfig).mockResolvedValue({ environment: "sandbox", paypal_available: false });
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

  it("renders PayPal subscription buttons for the chosen plan and shows the key on approval", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue(trial);
    vi.mocked(api.fetchBillingConfig).mockResolvedValue(configured);
    const fake = fakePayPal();
    vi.mocked(paypal.loadPayPalSdk).mockResolvedValue(fake.namespace);
    vi.mocked(api.activatePayPalSubscription).mockResolvedValue({
      status: "ok", email: "buyer@example.com", tier: "advanced", plan: "annual", license_key: "LK-123",
    });

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /advanced annual/i }));

    expect(await screen.findByText(/advanced — \$384\/year/i)).toBeInTheDocument();
    await waitFor(() => expect(fake.options()).toBeDefined());
    expect(paypal.loadPayPalSdk).toHaveBeenCalledWith("client-123", "USD");
    await expect(fake.createSubscription()).resolves.toBe("I-NEW");
    expect(fake.createdWith()).toEqual({ plan_id: "P-ADV-A" });

    await fake.approve("I-NEW");

    expect(api.activatePayPalSubscription).toHaveBeenCalledWith("I-NEW");
    expect(await screen.findByText("LK-123")).toBeInTheDocument();
    expect(screen.getByText("buyer@example.com")).toBeInTheDocument();
  });

  it("says PayPal isn't configured instead of loading PayPal when plans are missing", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue(trial);

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /pro — \$20\/mo/i }));

    expect(await screen.findByText("PayPal isn't configured on this deployment.")).toBeInTheDocument();
    expect(paypal.loadPayPalSdk).not.toHaveBeenCalled();
  });

  it("offers the redirect checkout when PayPal's script can't load", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue(trial);
    vi.mocked(api.fetchBillingConfig).mockResolvedValue(configured);
    vi.mocked(paypal.loadPayPalSdk).mockRejectedValue(new Error("Couldn't load PayPal."));
    vi.mocked(paypal.openPayPalCheckout).mockResolvedValue(undefined);

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /pro annual/i }));
    await userEvent.click(await screen.findByRole("button", { name: /continue on paypal/i }));

    expect(paypal.openPayPalCheckout).toHaveBeenCalledWith("annual", "pro");
  });

  it("explains the emailed key if activation can't be confirmed", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue(trial);
    vi.mocked(api.fetchBillingConfig).mockResolvedValue(configured);
    const fake = fakePayPal();
    vi.mocked(paypal.loadPayPalSdk).mockResolvedValue(fake.namespace);
    vi.mocked(api.activatePayPalSubscription).mockRejectedValue(new Error("PayPal subscription isn't active yet."));

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /pro — \$20\/mo/i }));
    await waitFor(() => expect(fake.options()).toBeDefined());
    await fake.approve("I-1");

    expect(await screen.findByText(/emailed as soon as PayPal confirms/i)).toBeInTheDocument();
  });
});
