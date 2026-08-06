import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResetPasswordPage } from "./ResetPasswordPage";
import * as api from "../api";
import { clearTenantApiKey, getTenantApiKey } from "../api";

vi.mock("../api", async (importActual) => {
  const actual = await importActual<typeof api>();
  return { ...actual, resetPassword: vi.fn() };
});

function setUrl(search: string) {
  window.history.pushState({}, "", `/reset-password${search}`);
}

afterEach(() => {
  clearTenantApiKey();
  vi.clearAllMocks();
});

describe("ResetPasswordPage", () => {
  it("shows an invalid-link message when there's no token in the URL", () => {
    setUrl("");
    render(<ResetPasswordPage />);
    expect(screen.getByText(/invalid reset link/i)).toBeInTheDocument();
  });

  it("submits the token + new password and stores the returned api key", async () => {
    setUrl("?token=abc123");
    vi.mocked(api.resetPassword).mockResolvedValue({ tenant_id: "t1", name: "Acme", api_key: "fresh-key" });

    render(<ResetPasswordPage />);
    await userEvent.type(screen.getByPlaceholderText(/^new password$/i), "Correct-Horse9");
    await userEvent.type(screen.getByPlaceholderText(/confirm new password/i), "Correct-Horse9");
    await userEvent.click(screen.getByRole("button", { name: /update password/i }));

    await waitFor(() => expect(api.resetPassword).toHaveBeenCalledWith("abc123", "Correct-Horse9"));
    expect(getTenantApiKey()).toBe("fresh-key");
    expect(await screen.findByText(/password updated/i)).toBeInTheDocument();
  });

  it("shows an error when the passwords don't match, without calling the API", async () => {
    setUrl("?token=abc123");
    render(<ResetPasswordPage />);

    await userEvent.type(screen.getByPlaceholderText(/^new password$/i), "Correct-Horse9");
    await userEvent.type(screen.getByPlaceholderText(/confirm new password/i), "Different-Horse9");
    await userEvent.click(screen.getByRole("button", { name: /update password/i }));

    expect(await screen.findByText(/don't match/i)).toBeInTheDocument();
    expect(api.resetPassword).not.toHaveBeenCalled();
  });

  it("shows the server's error message when the token is invalid/expired", async () => {
    setUrl("?token=expired-token");
    vi.mocked(api.resetPassword).mockRejectedValue(new Error("That reset link is invalid or has expired."));

    render(<ResetPasswordPage />);
    await userEvent.type(screen.getByPlaceholderText(/^new password$/i), "Correct-Horse9");
    await userEvent.type(screen.getByPlaceholderText(/confirm new password/i), "Correct-Horse9");
    await userEvent.click(screen.getByRole("button", { name: /update password/i }));

    expect(await screen.findByText(/invalid or has expired/i)).toBeInTheDocument();
  });
});
