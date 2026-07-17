import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { UploadPanel } from "./UploadPanel";
import * as api from "../api";

vi.mock("../api", async (importActual) => {
  const actual = await importActual<typeof api>();
  return { ...actual, uploadLeads: vi.fn(), startCheckout: vi.fn() };
});

function selectFile() {
  const file = new File(["company_name,domain\nAcme,acme.com"], "leads.csv", { type: "text/csv" });
  const input = document.querySelector("input[type=file]") as HTMLInputElement;
  return userEvent.upload(input, file);
}

describe("UploadPanel", () => {
  it("calls onUploaded with the scored leads on success", async () => {
    const leads = [{ id: "1", company_name: "Acme" }] as never;
    vi.mocked(api.uploadLeads).mockResolvedValue(leads);
    const onUploaded = vi.fn();

    render(<UploadPanel onUploaded={onUploaded} />);
    await selectFile();

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith(leads));
  });

  it("shows a generic error message for a non-license failure", async () => {
    vi.mocked(api.uploadLeads).mockRejectedValue(new Error("File must include a domain column."));

    render(<UploadPanel onUploaded={vi.fn()} />);
    await selectFile();

    expect(await screen.findByText("File must include a domain column.")).toBeInTheDocument();
  });

  it("shows a distinct upgrade CTA for a 402 LicenseRequiredError, not the generic error", async () => {
    vi.mocked(api.uploadLeads).mockRejectedValue(new api.LicenseRequiredError("No valid license found."));

    render(<UploadPanel onUploaded={vi.fn()} />);
    await selectFile();

    expect(await screen.findByText(/trial has expired/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\$30\/mo/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /buy annual/i })).toBeInTheDocument();
    expect(screen.queryByText("No valid license found.")).not.toBeInTheDocument();
  });
});
