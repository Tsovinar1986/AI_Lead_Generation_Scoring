import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LicenseBanner } from "./LicenseBanner";
import * as api from "../api";
import * as paddle from "../paddle";
import * as polar from "../polar";

vi.mock("../api", async (importActual) => {
  const actual = await importActual<typeof api>();
  return { ...actual, fetchLicenseStatus: vi.fn(), fetchBillingConfig: vi.fn() };
});

vi.mock("../paddle", () => ({ openPaddleCheckout: vi.fn() }));
vi.mock("../polar", () => ({ openPolarCheckout: vi.fn() }));

describe("LicenseBanner", () => {
  beforeEach(() => {
    // Most tests don't care about Polar -- default it "off" so the extra
    // buttons don't show up unless a test explicitly opts in.
    vi.mocked(api.fetchBillingConfig).mockResolvedValue({
      client_token: null, environment: "sandbox", price_id_monthly: null, price_id_annual: null,
      polar_available: false,
    });
  });

  it("renders nothing until the license status has loaded", () => {
    vi.mocked(api.fetchLicenseStatus).mockReturnValue(new Promise(() => {}));
    const { container } = render(<LicenseBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows trial messaging with uploads and days left and both plan buttons when no license was ever set", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, trial_days_left: 2, trial_uploads_left: 6,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/trial mode/i)).toBeInTheDocument();
    expect(screen.getByText(/6 of 10 free uploads left/i)).toBeInTheDocument();
    expect(screen.getByText(/2 days left/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\$20\/mo/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /buy annual/i })).toBeInTheDocument();
  });

  it("shows the customer/plan when licensed", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: true, customer_email: "buyer@example.com", plan: "pro", expires_at: null,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/buyer@example.com/)).toBeInTheDocument();
    expect(screen.getByText(/pro plan/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /\$20\/mo/i })).not.toBeInTheDocument();
  });

  it("shows a distinct message once the trial has run out with no purchase", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial_expired", customer_email: null, plan: null, trial_days_left: 0, trial_uploads_left: 5,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/trial has ended/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\$20\/mo/i })).toBeInTheDocument();
    expect(screen.queryByText(/trial mode/i)).not.toBeInTheDocument();
  });

  it("shows a renew CTA (not trial copy) when a paid license has expired", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "expired", customer_email: "buyer@example.com", plan: "pro", trial_days_left: null, trial_uploads_left: null,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/expired/i)).toBeInTheDocument();
    expect(screen.getByText(/buyer@example.com/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\$20\/mo/i })).toBeInTheDocument();
    expect(screen.queryByText(/trial mode/i)).not.toBeInTheDocument();
  });

  it("shows a config-check message (no buy buttons) for an invalid key, not a trial/payment prompt", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "invalid", customer_email: null, plan: null, trial_days_left: null, trial_uploads_left: null,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/couldn't be verified/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /\$20\/mo/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/trial mode/i)).not.toBeInTheDocument();
  });

  it("opens the Paddle checkout overlay for the selected interval when a buy button is clicked", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, trial_days_left: 3, trial_uploads_left: 5,
    });
    vi.mocked(paddle.openPaddleCheckout).mockResolvedValue(undefined);

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /buy annual/i }));

    await waitFor(() => expect(paddle.openPaddleCheckout).toHaveBeenCalledWith("annual"));
  });

  it("shows an error message when Paddle checkout fails to open", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, trial_days_left: 3, trial_uploads_left: 5,
    });
    vi.mocked(paddle.openPaddleCheckout).mockRejectedValue(new Error("Paddle isn't configured on this deployment."));

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /\$20\/mo/i }));

    expect(await screen.findByText("Paddle isn't configured on this deployment.")).toBeInTheDocument();
  });

  it("does not show Polar buttons when Polar isn't configured on this deployment", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, trial_days_left: 3, trial_uploads_left: 5,
    });

    render(<LicenseBanner />);

    await screen.findByRole("button", { name: /\$20\/mo/i });
    expect(screen.queryByRole("button", { name: /pay with polar/i })).not.toBeInTheDocument();
  });

  it("shows Polar buttons and opens Polar checkout when Polar is configured", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, trial_days_left: 3, trial_uploads_left: 5,
    });
    vi.mocked(api.fetchBillingConfig).mockResolvedValue({
      client_token: null, environment: "sandbox", price_id_monthly: null, price_id_annual: null,
      polar_available: true,
    });
    vi.mocked(polar.openPolarCheckout).mockResolvedValue(undefined);

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /pay with polar.*annual/i }));

    await waitFor(() => expect(polar.openPolarCheckout).toHaveBeenCalledWith("annual"));
  });

  it("shows an error message when Polar checkout fails to open", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: false, reason: "trial", customer_email: null, plan: null, trial_days_left: 3, trial_uploads_left: 5,
    });
    vi.mocked(api.fetchBillingConfig).mockResolvedValue({
      client_token: null, environment: "sandbox", price_id_monthly: null, price_id_annual: null,
      polar_available: true,
    });
    vi.mocked(polar.openPolarCheckout).mockRejectedValue(new Error("Polar isn't configured on this deployment."));

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /pay with polar.*mo/i }));

    expect(await screen.findByText("Polar isn't configured on this deployment.")).toBeInTheDocument();
  });
});
