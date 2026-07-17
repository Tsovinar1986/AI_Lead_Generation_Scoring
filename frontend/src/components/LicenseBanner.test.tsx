import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LicenseBanner } from "./LicenseBanner";
import * as api from "../api";

vi.mock("../api", async (importActual) => {
  const actual = await importActual<typeof api>();
  return { ...actual, fetchLicenseStatus: vi.fn(), startCheckout: vi.fn() };
});

describe("LicenseBanner", () => {
  it("renders nothing until the license status has loaded", () => {
    vi.mocked(api.fetchLicenseStatus).mockReturnValue(new Promise(() => {}));
    const { container } = render(<LicenseBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows trial messaging with days left and both plan buttons when no license was ever set", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, trial_days_left: 2,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/trial mode/i)).toBeInTheDocument();
    expect(screen.getByText(/2 days left/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\$30\/mo/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /buy annual/i })).toBeInTheDocument();
  });

  it("shows the customer/plan when licensed", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: true, customer_email: "buyer@example.com", plan: "pro", expires_at: null,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/buyer@example.com/)).toBeInTheDocument();
    expect(screen.getByText(/pro plan/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /\$30\/mo/i })).not.toBeInTheDocument();
  });

  it("shows a distinct message once the trial has run out with no purchase", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial_expired", customer_email: null, plan: null, trial_days_left: 0,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/trial has ended/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\$30\/mo/i })).toBeInTheDocument();
    expect(screen.queryByText(/trial mode/i)).not.toBeInTheDocument();
  });

  it("shows a renew CTA (not trial copy) when a paid license has expired", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "expired", customer_email: "buyer@example.com", plan: "pro", trial_days_left: null,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/expired/i)).toBeInTheDocument();
    expect(screen.getByText(/buyer@example.com/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\$30\/mo/i })).toBeInTheDocument();
    expect(screen.queryByText(/trial mode/i)).not.toBeInTheDocument();
  });

  it("shows a config-check message (no buy buttons) for an invalid key, not a trial/payment prompt", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "invalid", customer_email: null, plan: null, trial_days_left: null,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/couldn't be verified/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /\$30\/mo/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/trial mode/i)).not.toBeInTheDocument();
  });

  it("redirects to the checkout url for the selected interval when a buy button is clicked", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, trial_days_left: 3,
    });
    vi.mocked(api.startCheckout).mockResolvedValue({ checkout_url: "https://buyer.paddle.com/checkout/xyz" });

    const originalLocation = window.location;
    Object.defineProperty(window, "location", { value: { href: "" }, writable: true });

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /buy annual/i }));

    await waitFor(() => expect(window.location.href).toBe("https://buyer.paddle.com/checkout/xyz"));
    expect(api.startCheckout).toHaveBeenCalledWith("annual");
    Object.defineProperty(window, "location", { value: originalLocation, writable: true });
  });
});
