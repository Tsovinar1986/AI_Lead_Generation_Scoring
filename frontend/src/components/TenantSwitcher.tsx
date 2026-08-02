import { useState } from "react";
import { clearTenantApiKey, getTenantApiKey, setTenantApiKey } from "../api";

interface Props {
  onChange: () => void;
}

// Only relevant when a seller runs one shared instance for multiple
// customers (backend/scripts/create_tenant.py) -- a single self-hosted
// buyer never needs this, so it stays a small, unobtrusive control rather
// than a blocking login screen. No key set = the backend's default tenant,
// identical to this app's original zero-config behavior.
export function TenantSwitcher({ onChange }: Props) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const hasKey = Boolean(getTenantApiKey());

  function handleSave() {
    if (value.trim()) {
      setTenantApiKey(value.trim());
      setEditing(false);
      setValue("");
      onChange();
    }
  }

  function handleClear() {
    clearTenantApiKey();
    onChange();
  }

  if (editing) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="password"
          placeholder="Paste your workspace API key"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
          className="min-w-[220px] rounded-md border border-border bg-panel px-3 py-1.5 text-sm text-heading outline-none focus:border-accent"
        />
        <button
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90"
          onClick={handleSave}
        >
          Connect
        </button>
        <button
          className="rounded-md border border-border bg-panel px-3 py-1.5 text-sm text-heading transition-colors hover:border-accent/40"
          onClick={() => setEditing(false)}
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {hasKey ? (
        <>
          <span className="text-sm text-text/75">Connected to a custom workspace</span>
          <button
            className="rounded-md border border-border bg-panel px-3 py-1.5 text-sm text-heading transition-colors hover:border-accent/40"
            onClick={handleClear}
          >
            Disconnect
          </button>
        </>
      ) : (
        <button
          className="bg-transparent text-sm text-accent underline underline-offset-2"
          onClick={() => setEditing(true)}
        >
          Have a workspace key?
        </button>
      )}
    </div>
  );
}
