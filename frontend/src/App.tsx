import { useEffect, useState } from "react";
import { fetchAlerts, fetchLeads } from "./api";
import { AlertsPanel } from "./components/AlertsPanel";
import { LeadDetail } from "./components/LeadDetail";
import { LeadsTable } from "./components/LeadsTable";
import { LicenseBanner } from "./components/LicenseBanner";
import { UploadPanel } from "./components/UploadPanel";
import { PurchaseComplete } from "./pages/PurchaseComplete";
import type { Alert, ScoredLead } from "./types";

function LeadScoringApp() {
  const [leads, setLeads] = useState<ScoredLead[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [bucketFilter, setBucketFilter] = useState<"all" | "hot" | "warm" | "cold">("all");

  useEffect(() => {
    fetchLeads().then(setLeads).catch(() => {});
    fetchAlerts().then(setAlerts).catch(() => {});
  }, []);

  function handleUploaded(newLeads: ScoredLead[]) {
    setLeads(newLeads);
    fetchAlerts().then(setAlerts).catch(() => {});
  }

  function handleLeadUpdate(updated: ScoredLead) {
    setLeads((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
  }

  const selectedLead = leads.find((l) => l.id === selectedId) ?? null;

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Lead Generation &amp; Scoring Agent</h1>
        <p className="muted">Upload leads, get a ranked hybrid score, act on the hot ones.</p>
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
