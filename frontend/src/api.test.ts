import { afterEach, describe, expect, it, vi } from "vitest";
import {
  LicenseRequiredError,
  TenantAuthError,
  clearTenantApiKey,
  fetchBillingConfig,
  fetchLeads,
  setTenantApiKey,
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
      headers: { get: () => null },
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["a,b"], "leads.csv", { type: "text/csv" });
    const result = await uploadLeads(file);
    expect(result).toEqual({ leads: [], trialLimitedRows: null, trialTotalRows: null });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/leads/upload");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
  });

  it("surfaces the trial row cap from response headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
      headers: {
        get: (name: string) => ({ "X-Trial-Limited-Rows": "10", "X-Trial-Total-Rows": "45" }[name] ?? null),
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await uploadLeads(new File(["a,b"], "leads.csv", { type: "text/csv" }));
    expect(result).toEqual({ leads: [], trialLimitedRows: 10, trialTotalRows: 45 });
  });
});

describe("fetchBillingConfig", () => {
  it("gets /billing/config and returns the parsed billing config", async () => {
    const config = {
      client_token: "test_token",
      environment: "sandbox" as const,
      price_id_monthly: "pri_monthly",
      price_id_annual: "pri_annual",
    };
    mockFetchOnce(200, config);

    const result = await fetchBillingConfig();
    expect(result).toEqual(config);

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(url).toContain("/billing/config");
  });
});
