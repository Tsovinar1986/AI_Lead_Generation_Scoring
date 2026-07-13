import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TenantSwitcher } from "./TenantSwitcher";
import { clearTenantApiKey, getTenantApiKey } from "../api";

afterEach(() => {
  clearTenantApiKey();
});

describe("TenantSwitcher", () => {
  it("shows the connect link when no workspace key is set", () => {
    render(<TenantSwitcher onChange={vi.fn()} />);
    expect(screen.getByText(/have a workspace key/i)).toBeInTheDocument();
  });

  it("saves the key to storage and calls onChange when connecting", async () => {
    const onChange = vi.fn();
    render(<TenantSwitcher onChange={onChange} />);

    await userEvent.click(screen.getByText(/have a workspace key/i));
    await userEvent.type(screen.getByPlaceholderText(/paste your workspace api key/i), "secret-key-123");
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));

    expect(getTenantApiKey()).toBe("secret-key-123");
    expect(onChange).toHaveBeenCalled();
  });

  it("shows connected state and clears the key on disconnect", async () => {
    const onChange = vi.fn();
    render(<TenantSwitcher onChange={onChange} />);

    await userEvent.click(screen.getByText(/have a workspace key/i));
    await userEvent.type(screen.getByPlaceholderText(/paste your workspace api key/i), "secret-key-123");
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));

    expect(screen.getByText(/connected to a custom workspace/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /disconnect/i }));

    expect(getTenantApiKey()).toBeNull();
    expect(onChange).toHaveBeenCalledTimes(2);
  });
});
