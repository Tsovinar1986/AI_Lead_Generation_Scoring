import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LeadsTable } from "./LeadsTable";
import type { ScoredLead } from "../types";

function makeLead(overrides: Partial<ScoredLead>): ScoredLead {
  return {
    id: "1",
    company_name: "Acme",
    domain: "acme.com",
    contact_name: "Jane",
    contact_title: "VP",
    industry: "SaaS",
    employee_count: 200,
    revenue_usd: 20_000_000,
    geography: "United States",
    source: "csv_upload",
    tech_stack: ["AWS"],
    is_hiring: true,
    enrichment_source: "mock",
    fit_score: 80,
    score_breakdown: {
      industry_match: 20, company_size_fit: 20, revenue_fit: 15,
      tech_stack_match: 15, geography_fit: 10, title_seniority: 10, hiring_signal: 10,
    },
    conversion_likelihood: 80,
    llm_rationale: "strong fit",
    combined_score: 80,
    bucket: "hot",
    outreach_draft: null,
    crm_pushed: false,
    ...overrides,
  };
}

describe("LeadsTable", () => {
  it("shows an empty state with no leads", () => {
    render(
      <LeadsTable leads={[]} selectedId={null} bucketFilter="all" onSelect={vi.fn()} onBucketFilterChange={vi.fn()} />
    );
    expect(screen.getByText(/no leads yet/i)).toBeInTheDocument();
  });

  it("renders one row per lead", () => {
    const leads = [makeLead({ id: "1", company_name: "Acme" }), makeLead({ id: "2", company_name: "Globex" })];
    render(
      <LeadsTable leads={leads} selectedId={null} bucketFilter="all" onSelect={vi.fn()} onBucketFilterChange={vi.fn()} />
    );
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Globex")).toBeInTheDocument();
  });

  it("calls onSelect with the clicked lead", async () => {
    const onSelect = vi.fn();
    const leads = [makeLead({ id: "1", company_name: "Acme" })];
    render(
      <LeadsTable leads={leads} selectedId={null} bucketFilter="all" onSelect={onSelect} onBucketFilterChange={vi.fn()} />
    );

    await userEvent.click(screen.getByText("Acme"));
    expect(onSelect).toHaveBeenCalledWith(leads[0]);
  });

  it("filters rows by bucket", () => {
    const leads = [
      makeLead({ id: "1", company_name: "HotCo", bucket: "hot" }),
      makeLead({ id: "2", company_name: "ColdCo", bucket: "cold" }),
    ];
    render(
      <LeadsTable leads={leads} selectedId={null} bucketFilter="hot" onSelect={vi.fn()} onBucketFilterChange={vi.fn()} />
    );

    expect(screen.getByText("HotCo")).toBeInTheDocument();
    expect(screen.queryByText("ColdCo")).not.toBeInTheDocument();
  });

  it("calls onBucketFilterChange when a filter chip is clicked", async () => {
    const onBucketFilterChange = vi.fn();
    render(
      <LeadsTable leads={[]} selectedId={null} bucketFilter="all" onSelect={vi.fn()} onBucketFilterChange={onBucketFilterChange} />
    );

    await userEvent.click(screen.getByText(/^Hot/));
    expect(onBucketFilterChange).toHaveBeenCalledWith("hot");
  });
});
