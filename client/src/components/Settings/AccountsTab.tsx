import { useCallback, useEffect, useState } from "react";
import { CheckCircle, ExternalLink, Loader2, Plug, Save, Trash2, Unplug, XCircle } from "lucide-react";
import { api, openExternal } from "../../lib/platform";
import { Section, Toggle } from "./controls";

interface AccountField {
  key: string;
  label: string;
  secret: boolean;
  placeholder: string;
  required: boolean;
  kind: "text" | "url" | "int" | "email";
  help: string;
  value: string;
  masked: string;
}

interface Account {
  id: string;
  label: string;
  category: string;
  description: string;
  help: string;
  help_url: string;
  reads: string;
  writes: string;
  examples: string[];
  configured: boolean;
  allow_write: boolean;
  account: string;
  fields: AccountField[];
}

type Result = { ok: boolean; detail: string };

async function call(path: string, init?: RequestInit): Promise<{ connections: Account[] } & Partial<Result>> {
  const res = await api(path, init);
  const data = await res.json();
  if (!res.ok) throw new Error(String(data.detail ?? "Erreur"));
  return data;
}

function AccountCard({ a, onChange }: { a: Account; onChange: (list: Account[]) => void }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"" | "save" | "test" | "remove" | "write">("");
  const [result, setResult] = useState<Result | null>(null);

  const run = async (kind: typeof busy, fn: () => Promise<void>) => {
    setBusy(kind);
    setResult(null);
    try {
      await fn();
    } catch (e) {
      setResult({ ok: false, detail: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy("");
    }
  };

  /** Enregistre les champs puis teste aussitôt la connexion. */
  const saveAndTest = () => run("save", async () => {
    const saved = await call(`/connections/${a.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values }),
    });
    onChange(saved.connections);
    setValues({});
    const tested = await call(`/connections/${a.id}/test`, { method: "POST" });
    onChange(tested.connections);
    setResult({ ok: Boolean(tested.ok), detail: String(tested.detail ?? "") });
  });

  const setWrite = (allow: boolean) => run("write", async () => {
    const data = await call(`/connections/${a.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values: {}, allow_write: allow }),
    });
    onChange(data.connections);
  });

  const disconnect = () => run("remove", async () => {
    const data = await call(`/connections/${a.id}`, { method: "DELETE" });
    onChange(data.connections);
    setOpen(false);
  });

  const dirty = Object.values(values).some((v) => v.trim());

  return (
    <div className={`set-pcard${a.configured ? " is-ready" : ""}`}>
      <div className="set-pcard-head">
        <i className={a.configured ? "pdot ok" : "pdot"} title={a.configured ? "Connecté" : "Non connecté"} />
        <span className="set-provider-text">
          <strong>{a.label}</strong>
          <small>{a.configured ? (a.account ? `Connecté · ${a.account}` : "Connecté") : a.description}</small>
        </span>
        <button
          type="button"
          className={`btn btn-sm ${a.configured ? "btn-ghost" : "btn-primary"}`}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? "Fermer" : a.configured ? "Gérer" : <><Plug />Connecter</>}
        </button>
      </div>

      {a.configured && a.writes && (
        <div className="set-account-write">
          <span className="set-hint">
            Autoriser JARVIS à <strong>{a.writes}</strong>
            {!a.allow_write && " — pour l'instant, il peut seulement lire."}
          </span>
          <Toggle label={`Autoriser les actions ${a.label}`} checked={a.allow_write} disabled={!!busy} onChange={(v) => void setWrite(v)} />
        </div>
      )}

      {result && (
        <p className={`set-status ${result.ok ? "ok" : "err"}`} role="status">
          {result.ok ? <CheckCircle size={14} /> : <XCircle size={14} />} {result.detail}
        </p>
      )}

      {open && (
        <div className="set-editor">
          <p className="set-hint">
            {a.reads && <>JARVIS pourra : {a.reads}{a.writes ? ` ; et, si vous l'autorisez : ${a.writes}` : ""}.</>}
            {!a.reads && a.writes && <>JARVIS pourra : {a.writes}.</>}
          </p>
          {a.examples.length > 0 && (
            <div className="set-templates">
              <span className="set-hint">Exemples :</span>
              {a.examples.map((ex) => <span key={ex} className="set-chip is-static">« {ex} »</span>)}
            </div>
          )}
          {(a.help || a.help_url) && (
            <div className="set-account-help">
              {a.help && <span className="set-hint">{a.help}</span>}
              {a.help_url && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => void openExternal(a.help_url)}>
                  <ExternalLink />Où trouver ces informations ?
                </button>
              )}
            </div>
          )}
          <div className="set-grid2">
            {a.fields.map((f) => (
              <label key={f.key} className="set-field">
                <span className="set-label">
                  {f.label}{!f.required && <em>(facultatif)</em>}
                  {f.secret && f.masked && <em>(enregistré : {f.masked})</em>}
                </span>
                <input
                  className="set-input"
                  type={f.secret ? "password" : f.kind === "int" ? "number" : f.kind === "email" ? "email" : "text"}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder={f.secret && f.masked ? "Laisser vide pour conserver" : f.placeholder}
                  value={values[f.key] ?? (f.secret ? "" : f.value)}
                  onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                  onKeyDown={(e) => e.key === "Enter" && void saveAndTest()}
                />
                {f.help && <span className="set-hint">{f.help}</span>}
              </label>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn btn-primary btn-sm" disabled={!!busy || (!dirty && !a.configured)} onClick={() => void saveAndTest()}>
              {busy === "save" ? <Loader2 className="animate-spin" /> : <Save />}
              {a.configured ? "Enregistrer et tester" : "Connecter"}
            </button>
            {a.configured && (
              <button
                type="button"
                className="btn btn-danger btn-sm"
                disabled={!!busy}
                onClick={() => {
                  if (window.confirm(`Déconnecter ${a.label} ? Les identifiants enregistrés seront effacés.`)) void disconnect();
                }}
              >
                {busy === "remove" ? <Loader2 className="animate-spin" /> : <Unplug />}Déconnecter
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** Onglet COMPTES — mail, GitHub, agenda, maison connectée… que JARVIS peut gérer. */
export function AccountsTab() {
  const [list, setList] = useState<Account[] | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    call("/connections")
      .then((d) => setList(d.connections))
      .catch(() => setError("Serveur injoignable"));
  }, []);
  useEffect(refresh, [refresh]);

  if (!list) {
    return <p className="set-hint flex items-center gap-2">{error || <><Loader2 size={14} className="animate-spin" /> Chargement…</>}</p>;
  }

  const connected = list.filter((a) => a.configured);
  const categories = [...new Set(list.map((a) => a.category))];

  return (
    <>
      <div className="set-banner">
        <Plug size={16} />
        <span>
          {connected.length === 0
            ? "Aucun compte connecté. Connectez vos services pour que JARVIS les gère à votre place."
            : <>Comptes connectés : <strong>{connected.map((a) => a.label).join(", ")}</strong></>}
        </span>
      </div>
      <p className="set-hint">
        Les identifiants restent sur votre machine, côté serveur, et ne sont jamais réaffichés. Par défaut JARVIS ne fait que
        lire ; il n'envoie, ne publie et ne modifie rien sans votre autorisation, compte par compte, et sans que vous le lui
        demandiez.
      </p>
      {categories.map((cat) => (
        <Section key={cat} title={cat}>
          <div className="set-providers">
            {list.filter((a) => a.category === cat).map((a) => <AccountCard key={a.id} a={a} onChange={setList} />)}
          </div>
        </Section>
      ))}
      <p className="set-hint"><Trash2 size={12} className="inline" /> « Déconnecter » efface les identifiants de ce compte.</p>
    </>
  );
}
