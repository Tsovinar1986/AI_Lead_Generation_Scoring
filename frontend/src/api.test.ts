import { afterEach, describe, expect, it, vi } from "vitest";
import {
  LicenseRequiredError,
  TenantAuthError,
  clearTenantApiKey,
  fetchLeads,
  setTenantApiKey,
  startCheckout,
  uploadLeads,
} from "./api";

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      statusText: "error",
      json: async () => body,
    })
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearTenantApiKey();
});

describe("api error handling", () => {
  it("throws LicenseRequiredError on a 402 response", async () => {
    mockFetchOnce(402, { detail: "No valid license found." });

    await expect(fetchLeads()).rejects.toBeInstanceOf(LicenseRequiredError);
  });

  it("throws a plain Error with the server detail on other failures", async () => {
    mockFetchOnce(400, { detail: "File must include a domain column." });

    await expect(fetchLeads()).rejects.toThrow("File must include a domain column.");
  });

  it("returns parsed JSON on success", async () => {
    mockFetchOnce(200, [{ id: "1", company_name: "Acme" }]);

    const leads = await fetchLeads();
    expect(leads).toEqual([{ id: "1", company_name: "Acme" }]);
  });

  it("throws TenantAuthError on a 401 response", async () => {
    mockFetchOnce(401, { detail: "Invalid API key" });

    await expect(fetchLeads()).rejects.toBeInstanceOf(TenantAuthError);
  });
});

describe("tenant auth header", () => {
  it("sends no Authorization header when no workspace key is set", async () => {
    mockFetchOnce(200, []);
    await fetchLeads();

    const [, options] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(options?.headers?.Authorization).toBeUndefined();
  });

  it("sends Bearer <key> once a workspace key is set", async () => {
    setTenantApiKey("secret-key-123");
    mockFetchOnce(200, []);
    await fetchLeads();

    const [, options] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(options?.headers?.Authorization).toBe("Bearer secret-key-123");
  });
});

describe("uploadLeads", () => {
  it("posts multipart form data to /leads/upload", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["a,b"], "leads.csv", { type: "text/csv" });
    await uploadLeads(file);

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/leads/upload");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
  });
});

describe("startCheckout", () => {
  it("posts to /billing/checkout with the selected interval and returns the checkout url", async () => {
    mockFetchOnce(200, { checkout_url: "https://buyer.paddle.com/checkout/xyz" });

    const result = await startCheckout("annual");
    expect(result.checkout_url).toBe("https://buyer.paddle.com/checkout/xyz");

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/billing/checkout?interval=annual");
  });
});
