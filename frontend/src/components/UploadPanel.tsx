import { useRef, useState } from "react";
import { LicenseRequiredError, startCheckout, uploadLeads } from "../api";
import type { BillingInterval, ScoredLead } from "../types";

interface Props {
  onUploaded: (leads: ScoredLead[]) => void;
}

export function UploadPanel({ onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [licenseRequired, setLicenseRequired] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    setLicenseRequired(false);
    setFileName(file.name);
    try {
      const leads = await uploadLeads(file);
      onUploaded(leads);
    } catch (err) {
      if (err instanceof LicenseRequiredError) {
        setLicenseRequired(true);
      } else {
        setError(err instanceof Error ? err.message : "Upload failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleBuy(interval: BillingInterval) {
    setBusy(true);
    try {
      const { checkout_url } = await startCheckout(interval);
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't start checkout");
      setBusy(false);
    }
  }

  return (
    <div className="panel upload-panel">
      <div>
        <h2>Upload leads</h2>
        <p className="muted">
          CSV or XLSX with at least a company name and domain column. Missing
          firmographic fields are filled in automatically.
        </p>
      </div>
      <div className="upload-controls">
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
        <button
          className="primary"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
          {busy ? "Scoring…" : "Choose file"}
        </button>
        {fileName && <span className="muted">{fileName}</span>}
      </div>
      {error && <p className="error">{error}</p>}
      {licenseRequired && (
        <div className="license-required">
          <p>Your trial has expired — a license is required to keep scoring leads.</p>
          <button className="primary" disabled={busy} onClick={() => handleBuy("monthly")}>
            $30/mo
          </button>
          <button className="primary" disabled={busy} onClick={() => handleBuy("annual")}>
            Buy annual (save 2 months)
          </button>
        </div>
      )}
    </div>
  );
}
