import { useEffect, useState } from "react";
import { TenantAuthError, clearTenantApiKey, fetchLeads } from "./api";
import { LeadDetail } from "./components/LeadDetail";
import { LeadsTable } from "./components/LeadsTable";
import { LicenseBanner } from "./components/LicenseBanner";
import { TenantSwitcher } from "./components/TenantSwitcher";
import { UploadPanel } from "./components/UploadPanel";
import { PurchaseComplete } from "./pages/PurchaseComplete";
import type { ScoredLead } from "./types";

function LeadScoringApp() {
  const [leads, setLeads] = useState<ScoredLead[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [bucketFilter, setBucketFilter] = useState<"all" | "hot" | "warm" | "cold">("all");
  const [workspaceGeneration, setWorkspaceGeneration] = useState(0);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    fetchLeads()
      .then(setLeads)
      .catch((err) => {
        if (err instanceof TenantAuthError) {
          clearTenantApiKey();
          setAuthError("That workspace key was rejected — disconnected, showing the default workspace.");
        }
      });
  }, [workspaceGeneration]);

  function handleUploaded(newLeads: ScoredLead[]) {
    setLeads(newLeads);
  }

  function handleLeadUpdate(updated: ScoredLead) {
    setLeads((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
  }

  function handleWorkspaceChange() {
    setAuthError(null);
    setSelectedId(null);
    setWorkspaceGeneration((n) => n + 1);
  }

  const selectedLead = leads.find((l) => l.id === selectedId) ?? null;

  return (
    <div className="min-h-screen bg-bg font-sans text-text antialiased">
      <div className="mx-auto max-w-[1200px] px-6 py-8">
        <header className="animate-fade-in-up mb-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent/70 font-display text-lg font-semibold text-white shadow-[0_2px_8px_-2px_var(--color-accent)]"
              >
                A
              </span>
              <div>
                <h1 className="font-display text-[1.7rem] font-semibold tracking-tight text-heading">
                  AI Lead Generation &amp; Scoring Agent
                </h1>
                <p className="mt-0.5 text-sm text-text/75">
                  Upload leads, get a ranked hybrid score, act on the hot ones.
                </p>
              </div>
            </div>
            <TenantSwitcher onChange={handleWorkspaceChange} />
          </div>
          {authError && <p className="mt-3 text-sm text-hot">{authError}</p>}
        </header>

        <div className="animate-fade-in-up mb-5" style={{ animationDelay: "60ms" }}>
          <LicenseBanner />
        </div>

        <main className="flex flex-col gap-5">
          <div className="animate-fade-in-up" style={{ animationDelay: "110ms" }}>
            <UploadPanel onUploaded={handleUploaded} />
          </div>
          <div className="animate-fade-in-up" style={{ animationDelay: "160ms" }}>
            <LeadsTable
              leads={leads}
              selectedId={selectedId}
              bucketFilter={bucketFilter}
              onSelect={(lead) => setSelectedId(lead.id)}
              onBucketFilterChange={setBucketFilter}
            />
          </div>
        </main>
      </div>

      {selectedLead && (
        <LeadDetail
          lead={selectedLead}
          onClose={() => setSelectedId(null)}
          onUpdate={handleLeadUpdate}
        />
      )}
    </div>
  );
}

function App() {
  if (window.location.pathname === "/purchase-complete") {
    return <PurchaseComplete />;
  }
  return <LeadScoringApp />;
}

export default App;
