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
    <div className="app">
      <header className="app-header">
        <div className="app-header-row">
          <div>
            <h1>AI Lead Generation &amp; Scoring Agent</h1>
            <p className="muted">Upload leads, get a ranked hybrid score, act on the hot ones.</p>
          </div>
          <TenantSwitcher onChange={handleWorkspaceChange} />
        </div>
        {authError && <p className="error">{authError}</p>}
      </header>

      <LicenseBanner />

      <main className="app-grid">
        <div className="app-main-col">
          <UploadPanel onUploaded={handleUploaded} />
          <LeadsTable
            leads={leads}
            selectedId={selectedId}
            bucketFilter={bucketFilter}
            onSelect={(lead) => setSelectedId(lead.id)}
            onBucketFilterChange={setBucketFilter}
          />
        </div>
        <div className="app-side-col">
          <AlertsPanel alerts={alerts} />
        </div>
      </main>

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
