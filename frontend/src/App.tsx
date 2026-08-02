import { useEffect, useState } from "react";
import { TenantAuthError, clearTenantApiKey, fetchAlerts, fetchLeads } from "./api";
import { AlertsPanel } from "./components/AlertsPanel";
import { LeadDetail } from "./components/LeadDetail";
import { LeadsTable } from "./components/LeadsTable";
import { LicenseBanner } from "./components/LicenseBanner";
import { TenantSwitcher } from "./components/TenantSwitcher";
import { UploadPanel } from "./components/UploadPanel";
import { PurchaseComplete } from "./pages/PurchaseComplete";
import type { Alert, ScoredLead } from "./types";

function LeadScoringApp() {
  const [leads, setLeads] = useState<ScoredLead[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
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
    fetchAlerts().then(setAlerts).catch(() => {});
  }, [workspaceGeneration]);

  function handleUploaded(newLeads: ScoredLead[]) {
    setLeads(newLeads);
    fetchAlerts().then(setAlerts).catch(() => {});
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
        <header className="mb-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-heading">
                AI Lead Generation &amp; Scoring Agent
              </h1>
              <p className="mt-1 text-sm text-text/75">
                Upload leads, get a ranked hybrid score, act on the hot ones.
              </p>
            </div>
            <TenantSwitcher onChange={handleWorkspaceChange} />
          </div>
          {authError && <p className="mt-3 text-sm text-hot">{authError}</p>}
        </header>

        <div className="mb-5">
          <LicenseBanner />
        </div>

        <main className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1fr_280px]">
          <div className="flex min-w-0 flex-col gap-5">
            <UploadPanel onUploaded={handleUploaded} />
            <LeadsTable
              leads={leads}
              selectedId={selectedId}
              bucketFilter={bucketFilter}
              onSelect={(lead) => setSelectedId(lead.id)}
              onBucketFilterChange={setBucketFilter}
            />
          </div>
          <div>
            <AlertsPanel alerts={alerts} />
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
