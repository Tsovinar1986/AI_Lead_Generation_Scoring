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

  it("shows a trial banner with a buy button when unlicensed", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({ licensed: false });

    render(<LicenseBanner />);

    expect(await screen.findByText(/trial mode/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /buy a license/i })).toBeInTheDocument();
  });

  it("shows the customer/plan when licensed", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({
      licensed: true, customer_email: "buyer@example.com", plan: "pro", expires_at: null,
    });

    render(<LicenseBanner />);

    expect(await screen.findByText(/buyer@example.com/)).toBeInTheDocument();
    expect(screen.getByText(/pro plan/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /buy a license/i })).not.toBeInTheDocument();
  });

  it("redirects to the checkout url when buy is clicked", async () => {
    vi.mocked(api.fetchLicenseStatus).mockResolvedValue({ licensed: false });
    vi.mocked(api.startCheckout).mockResolvedValue({ checkout_url: "https://checkout.stripe.com/xyz" });

    const originalLocation = window.location;
    Object.defineProperty(window, "location", { value: { href: "" }, writable: true });

    render(<LicenseBanner />);
    await userEvent.click(await screen.findByRole("button", { name: /buy a license/i }));

    await waitFor(() => expect(window.location.href).toBe("https://checkout.stripe.com/xyz"));
    Object.defineProperty(window, "location", { value: originalLocation, writable: true });
  });
});
