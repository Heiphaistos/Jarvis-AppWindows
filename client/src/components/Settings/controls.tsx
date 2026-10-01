import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api } from "../../lib/platform";

/* ── Réglages serveur (data/settings.json via /api/settings) ─────────────── */

export type SettingValue = boolean | number | string;

export interface SettingSchema {
  kind: "bool" | "int" | "float" | "str" | "choice";
  label: string;
  default: SettingValue;
  min: number | null;
  max: number | null;
  choices: string[];
}

export function useRuntimeSettings() {
  const [values, setValues] = useState<Record<string, SettingValue> | null>(null);
  const [schema, setSchema] = useState<Record<string, SettingSchema>>({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api("/settings")
      .then((r) => r.json())
      .then((d) => {
        setValues(d.values);
        setSchema(d.schema);
      })
      .catch(() => setError("Serveur injoignable"));
  }, []);

  /** Enregistre immédiatement ; la valeur affichée suit la réponse du serveur. */
  const update = useCallback(async (changes: Record<string, SettingValue>) => {
    setError("");
    setValues((v) => (v ? { ...v, ...changes } : v));
    try {
      const res = await api("/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values: changes }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(String(data.detail ?? "Réglage refusé"));
        // Recharge l'état réel du serveur
        const fresh = await api("/settings").then((r) => r.json());
        setValues(fresh.values);
        return false;
      }
      setValues(data.values);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1500);
      return true;
    } catch {
      setError("Serveur injoignable");
      return false;
    }
  }, []);

  return { values, schema, update, error, saved };
}

/* ── Contrôles ───────────────────────────────────────────────────────────── */

export function Section({ title, children, hint }: { title: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <section className="set-section">
      <h3 className="set-title">{title}</h3>
      {children}
      {hint && <p className="set-hint">{hint}</p>}
    </section>
  );
}

export function Row({ label, hint, children }: { label: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="set-row">
      <div className="set-row-text">
        <span className="set-label">{label}</span>
        {hint && <span className="set-hint">{hint}</span>}
      </div>
      <div className="set-row-ctrl">{children}</div>
    </div>
  );
}

export function Toggle({ checked, onChange, disabled, label }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className="set-toggle"
      onClick={() => onChange(!checked)}
    >
      <span />
    </button>
  );
}

export function Slider({ value, min, max, step, onCommit, format, label }: {
  value: number;
  min: number;
  max: number;
  step: number;
  onCommit: (v: number) => void;
  format: (v: number) => string;
  label: string;
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  return (
    <div className="set-slider">
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={local}
        aria-label={label}
        onChange={(e) => setLocal(Number(e.target.value))}
        onPointerUp={() => local !== value && onCommit(local)}
        onKeyUp={() => local !== value && onCommit(local)}
        onBlur={() => local !== value && onCommit(local)}
      />
      <output>{format(local)}</output>
    </div>
  );
}

export function Select({ value, options, onChange, label }: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  label: string;
}) {
  return (
    <select className="set-input" value={value} aria-label={label} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

/** Champ texte enregistré à la validation (Entrée ou perte du focus). */
export function TextField({ value, onCommit, placeholder, label, list, type = "text" }: {
  value: string;
  onCommit: (v: string) => void;
  placeholder?: string;
  label: string;
  list?: string;
  type?: "text" | "password";
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  const commit = () => {
    if (local.trim() !== value) onCommit(local.trim());
  };
  return (
    <input
      className="set-input"
      type={type}
      value={local}
      placeholder={placeholder}
      aria-label={label}
      list={list}
      spellCheck={false}
      onChange={(e) => setLocal(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
      }}
    />
  );
}

/** Zone de texte sur plusieurs lignes, enregistrée à la perte du focus. */
export function TextArea({ value, onCommit, placeholder, label, maxLength, rows = 5 }: {
  value: string;
  onCommit: (v: string) => void;
  placeholder?: string;
  label: string;
  maxLength?: number;
  rows?: number;
}) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  // Enregistre aussi pendant la saisie : fermer les paramètres ne perd rien.
  useEffect(() => {
    if (local.trim() === value) return;
    const t = window.setTimeout(() => onCommit(local.trim()), 900);
    return () => window.clearTimeout(t);
  }, [local, value, onCommit]);
  return (
    <div className="set-textarea">
      <textarea
        className="set-input"
        rows={rows}
        value={local}
        placeholder={placeholder}
        aria-label={label}
        maxLength={maxLength}
        onChange={(e) => setLocal(e.target.value)}
      />
      {maxLength && <small className="set-hint">{local.length} / {maxLength} · enregistré automatiquement</small>}
    </div>
  );
}

export function Status({ error, saved }: { error: string; saved: boolean }) {
  if (error) return <p className="set-status err" role="alert">{error}</p>;
  if (saved) return <p className="set-status ok" role="status">Enregistré</p>;
  return null;
}
