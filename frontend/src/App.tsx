import { useEffect, useState } from "react";
import { TenantAuthError, clearTenantApiKey, fetchLeads, getTenantApiKey, setTenantApiKey } from "./api";
import { LeadDetail } from "./components/LeadDetail";
import { LeadsTable } from "./components/LeadsTable";
import { LicenseBanner } from "./components/LicenseBanner";
import { ScoreDashboard } from "./components/ScoreDashboard";
import { TenantSwitcher } from "./components/TenantSwitcher";
import { UploadPanel } from "./components/UploadPanel";
import { PurchaseComplete } from "./pages/PurchaseComplete";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import type { ScoredLead } from "./types";

// crmscoring.com's "Get started free" opens the app with #workspace=<key>
// for the trial workspace it just created -- keep the key, drop it from the
// URL so it isn't left in history or a copied link.
function adoptWorkspaceFromUrl() {
  const match = window.location.hash.match(/^#workspace=([\w-]+)$/);
  if (!match) return;
  setTenantApiKey(match[1]);
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

adoptWorkspaceFromUrl();

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
        // No key at all on the hosted deployment is just a new visitor --
        // the banner offers a free trial. Only a rejected key is an error.
        if (err instanceof TenantAuthError && getTenantApiKey()) {
          clearTenantApiKey();
          setAuthError("That workspace key was rejected — disconnected.");
          setWorkspaceGeneration((n) => n + 1);
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

        {/* Decides for itself whether to show (see LicenseBanner). Keyed on
            the workspace so it re-reads status after connect/disconnect. */}
        <div className="animate-fade-in-up mb-5 empty:hidden" style={{ animationDelay: "60ms" }}>
          <LicenseBanner key={workspaceGeneration} onWorkspaceChange={handleWorkspaceChange} />
        </div>

        <main className="flex flex-col gap-5">
          <div className="animate-fade-in-up" style={{ animationDelay: "110ms" }}>
            <UploadPanel onUploaded={handleUploaded} />
          </div>
          {leads.length > 0 && (
            <div className="animate-fade-in-up" style={{ animationDelay: "135ms" }}>
              <ScoreDashboard leads={leads} />
            </div>
          )}
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
  if (window.location.pathname === "/reset-password") {
    return <ResetPasswordPage />;
  }
  return <LeadScoringApp />;
}

export default App;
