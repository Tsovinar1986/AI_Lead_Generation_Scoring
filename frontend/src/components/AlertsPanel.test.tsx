import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AlertsPanel } from "./AlertsPanel";

describe("AlertsPanel", () => {
  it("shows an empty state with no alerts", () => {
    render(<AlertsPanel alerts={[]} />);
    expect(screen.getByText(/no hot leads yet/i)).toBeInTheDocument();
  });

  it("renders one item per alert", () => {
    render(
      <AlertsPanel
        alerts={[
          { id: "1", lead_id: "l1", company_name: "Acme", combined_score: 90, message: "Hot lead: Acme", channel: "slack" },
          { id: "2", lead_id: "l2", company_name: "Globex", combined_score: 85, message: "Hot lead: Globex", channel: "slack" },
        ]}
      />
    );
    expect(screen.getByText("Hot lead: Acme")).toBeInTheDocument();
    expect(screen.getByText("Hot lead: Globex")).toBeInTheDocument();
  });
});
