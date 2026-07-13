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
      <div className="tenant-switcher">
        <input
          type="password"
          placeholder="Paste your workspace API key"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
        />
        <button className="primary" onClick={handleSave}>Connect</button>
        <button onClick={() => setEditing(false)}>Cancel</button>
      </div>
    );
  }

  return (
    <div className="tenant-switcher">
      {hasKey ? (
        <>
          <span className="muted">Connected to a custom workspace</span>
          <button onClick={handleClear}>Disconnect</button>
        </>
      ) : (
        <button className="tenant-switcher-link" onClick={() => setEditing(true)}>
          Have a workspace key?
        </button>
      )}
    </div>
  );
}
