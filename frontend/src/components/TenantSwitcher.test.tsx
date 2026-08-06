import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TenantSwitcher } from "./TenantSwitcher";
import * as api from "../api";
import { clearTenantApiKey, getTenantApiKey } from "../api";

vi.mock("../api", async (importActual) => {
  const actual = await importActual<typeof api>();
  return { ...actual, signup: vi.fn(), login: vi.fn(), forgotPassword: vi.fn() };
});

afterEach(() => {
  clearTenantApiKey();
  vi.clearAllMocks();
});

async function openPasteKey() {
  await userEvent.click(screen.getByText(/log in \/ sign up/i));
  await userEvent.click(screen.getByText(/paste a key instead/i));
}

describe("TenantSwitcher", () => {
  it("shows the connect link when no workspace key is set", () => {
    render(<TenantSwitcher onChange={vi.fn()} />);
    expect(screen.getByText(/log in \/ sign up/i)).toBeInTheDocument();
  });

  it("saves a pasted key to storage and calls onChange when connecting", async () => {
    const onChange = vi.fn();
    render(<TenantSwitcher onChange={onChange} />);

    await openPasteKey();
    await userEvent.type(screen.getByPlaceholderText(/paste your workspace api key/i), "secret-key-123");
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));

    expect(getTenantApiKey()).toBe("secret-key-123");
    expect(onChange).toHaveBeenCalled();
  });

  it("shows connected state and clears the key on disconnect", async () => {
    const onChange = vi.fn();
    render(<TenantSwitcher onChange={onChange} />);

    await openPasteKey();
    await userEvent.type(screen.getByPlaceholderText(/paste your workspace api key/i), "secret-key-123");
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));

    expect(screen.getByText(/connected to a custom workspace/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /disconnect/i }));

    expect(getTenantApiKey()).toBeNull();
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  it("signs up, stores the returned api key, and calls onChange", async () => {
    vi.mocked(api.signup).mockResolvedValue({ tenant_id: "t1", name: "Acme", api_key: "new-key-1" });
    const onChange = vi.fn();
    render(<TenantSwitcher onChange={onChange} />);

    await userEvent.click(screen.getByText(/log in \/ sign up/i));
    await userEvent.click(screen.getByText(/new here\? sign up/i));
    await userEvent.type(screen.getByPlaceholderText(/company\/workspace name/i), "Acme");
    await userEvent.type(screen.getByPlaceholderText(/^email$/i), "buyer@acme.com");
    await userEvent.type(screen.getByPlaceholderText(/^password$/i), "Correct-Horse9");
    await userEvent.click(screen.getByRole("button", { name: /^sign up$/i }));

    await waitFor(() => expect(api.signup).toHaveBeenCalledWith("Acme", "buyer@acme.com", "Correct-Horse9"));
    expect(getTenantApiKey()).toBe("new-key-1");
    expect(onChange).toHaveBeenCalled();
  });

  it("shows a signup error without storing a key", async () => {
    vi.mocked(api.signup).mockRejectedValue(new Error("An account with that email already exists."));
    render(<TenantSwitcher onChange={vi.fn()} />);

    await userEvent.click(screen.getByText(/log in \/ sign up/i));
    await userEvent.click(screen.getByText(/new here\? sign up/i));
    await userEvent.type(screen.getByPlaceholderText(/company\/workspace name/i), "Acme");
    await userEvent.type(screen.getByPlaceholderText(/^email$/i), "buyer@acme.com");
    await userEvent.type(screen.getByPlaceholderText(/^password$/i), "Correct-Horse9");
    await userEvent.click(screen.getByRole("button", { name: /^sign up$/i }));

    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
    expect(getTenantApiKey()).toBeNull();
  });

  it("logs in and stores the returned api key", async () => {
    vi.mocked(api.login).mockResolvedValue({ tenant_id: "t1", name: "Acme", api_key: "login-key-1" });
    const onChange = vi.fn();
    render(<TenantSwitcher onChange={onChange} />);

    await userEvent.click(screen.getByText(/log in \/ sign up/i));
    await userEvent.type(screen.getByPlaceholderText(/^email$/i), "buyer@acme.com");
    await userEvent.type(screen.getByPlaceholderText(/^password$/i), "Correct-Horse9");
    await userEvent.click(screen.getByRole("button", { name: /^log in$/i }));

    await waitFor(() => expect(api.login).toHaveBeenCalledWith("buyer@acme.com", "Correct-Horse9"));
    expect(getTenantApiKey()).toBe("login-key-1");
    expect(onChange).toHaveBeenCalled();
  });

  it("shows a login error without storing a key", async () => {
    vi.mocked(api.login).mockRejectedValue(new Error("Incorrect email or password."));
    render(<TenantSwitcher onChange={vi.fn()} />);

    await userEvent.click(screen.getByText(/log in \/ sign up/i));
    await userEvent.type(screen.getByPlaceholderText(/^email$/i), "buyer@acme.com");
    await userEvent.type(screen.getByPlaceholderText(/^password$/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /^log in$/i }));

    expect(await screen.findByText(/incorrect email or password/i)).toBeInTheDocument();
    expect(getTenantApiKey()).toBeNull();
  });

  it("sends a forgot-password request and shows the generic confirmation", async () => {
    vi.mocked(api.forgotPassword).mockResolvedValue({ detail: "ok" });
    render(<TenantSwitcher onChange={vi.fn()} />);

    await userEvent.click(screen.getByText(/log in \/ sign up/i));
    await userEvent.click(screen.getByText(/forgot password/i));
    await userEvent.type(screen.getByPlaceholderText(/^email$/i), "buyer@acme.com");
    await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));

    await waitFor(() => expect(api.forgotPassword).toHaveBeenCalledWith("buyer@acme.com"));
    expect(await screen.findByText(/reset link is on its way/i)).toBeInTheDocument();
  });
});
