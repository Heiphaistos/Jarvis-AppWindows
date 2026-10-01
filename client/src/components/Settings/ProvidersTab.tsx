import { useCallback, useEffect, useState } from "react";
import {
  ArrowDown, ArrowUp, CheckCircle, Cpu, ExternalLink, KeyRound, ListRestart, Loader2, Plug, Plus, Trash2, X, XCircle, Zap,
} from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";
import type { BrainLevel, ProviderInfo, ProvidersStatus } from "../../types";
import { api, openExternal } from "../../lib/platform";
import { Section } from "./controls";

const LEVELS: { id: BrainLevel; label: string; hint: string }[] = [
  { id: "instant", label: "Instantané", hint: "salutations, ordres, reformulations" },
  { id: "standard", label: "Standard", hint: "conversation" },
  { id: "deep", label: "Profond", hint: "analyse, code, rédaction" },
];

/** Où créer une clé API pour chaque fournisseur. */
const KEY_PAGES: Record<string, string> = {
  anthropic: "https://console.anthropic.com/settings/keys",
  openai: "https://platform.openai.com/api-keys",
  gemini: "https://aistudio.google.com/app/apikey",
  groq: "https://console.groq.com/keys",
  deepseek: "https://platform.deepseek.com/api_keys",
  xai: "https://console.x.ai",
  openrouter: "https://openrouter.ai/keys",
  cerebras: "https://cloud.cerebras.ai",
  huggingface: "https://huggingface.co/settings/tokens",
  mistral: "https://console.mistral.ai/api-keys",
};

type TestResult = { ok: boolean; detail: string };

async function postProviders(body: Record<string, unknown>): Promise<ProvidersStatus> {
  const res = await api("/providers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(String(data.detail ?? "Erreur de configuration"));
  return data as ProvidersStatus;
}

/* ── Mode AUTO : chaînes de cerveaux modifiables ─────────────────────────── */

function ChainEditor({ status, onSave, busy }: {
  status: ProvidersStatus;
  onSave: (chains: Record<BrainLevel, string[]>) => void;
  busy: boolean;
}) {
  const routing = status.routing;
  const [chains, setChains] = useState<Record<BrainLevel, string[]> | null>(routing ? { ...routing.chains } : null);
  const [adding, setAdding] = useState<Record<BrainLevel, string>>({ instant: "", standard: "", deep: "" });
  useEffect(() => {
    if (routing) setChains({ ...routing.chains });
  }, [routing]);
  if (!routing || !chains) return null;

  const configured = new Set(status.providers.filter((p) => p.configured).map((p) => p.name));
  if (status.local_available) configured.add("local");
  const options = [...status.providers.map((p) => p.name), "local"];
  const dirty = JSON.stringify(chains) !== JSON.stringify(routing.chains);

  const move = (level: BrainLevel, i: number, delta: number) => {
    const list = [...chains[level]];
    const j = i + delta;
    if (j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]];
    setChains({ ...chains, [level]: list });
  };
  const remove = (level: BrainLevel, i: number) =>
    setChains({ ...chains, [level]: chains[level].filter((_, k) => k !== i) });
  const add = (level: BrainLevel) => {
    const spec = adding[level].trim();
    if (!spec || chains[level].includes(spec)) return;
    setChains({ ...chains, [level]: [...chains[level], spec] });
    setAdding({ ...adding, [level]: "" });
  };

  return (
    <details className="set-chains-box">
      <summary>Modifier les chaînes de cerveaux</summary>
    <div className="set-chains">
      {LEVELS.map((l) => (
        <div key={l.id} className="set-chain">
          <div className="set-label">{l.label} <span className="set-hint">· {l.hint}</span></div>
          <ol>
            {chains[l.id].map((spec, i) => {
              const ok = configured.has(spec.split("@")[0]);
              return (
                <li key={`${spec}-${i}`} className={ok ? "" : "is-off"} title={ok ? undefined : "Clé non configurée : ignoré"}>
                  <span className="truncate">{spec}</span>
                  {!ok && <em className="set-chain-off">sans clé</em>}
                  <button type="button" className="icon-btn" onClick={() => move(l.id, i, -1)} aria-label="Monter"><ArrowUp /></button>
                  <button type="button" className="icon-btn" onClick={() => move(l.id, i, 1)} aria-label="Descendre"><ArrowDown /></button>
                  <button type="button" className="icon-btn" onClick={() => remove(l.id, i)} aria-label="Retirer"><X /></button>
                </li>
              );
            })}
          </ol>
          <div className="flex gap-2">
            <input
              className="set-input"
              list="jarvis-brain-specs"
              placeholder="fournisseur ou fournisseur@modèle"
              value={adding[l.id]}
              onChange={(e) => setAdding({ ...adding, [l.id]: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && add(l.id)}
            />
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => add(l.id)}><Plus />Ajouter</button>
          </div>
        </div>
      ))}
      <datalist id="jarvis-brain-specs">
        {options.map((o) => <option key={o} value={o} />)}
      </datalist>
      <div className="flex gap-2">
        <button type="button" className="btn btn-primary btn-sm" disabled={!dirty || busy} onClick={() => onSave(chains)}>
          Enregistrer les chaînes
        </button>
        <button type="button" className="btn btn-ghost btn-sm" disabled={!dirty || busy} onClick={() => setChains({ ...routing.chains })}>
          <ListRestart />Annuler
        </button>
      </div>
    </div>
    </details>
  );
}

/* ── Éditeur d'un fournisseur ────────────────────────────────────────────── */

function ProviderEditor({ p, onSaved, onError, onActivate }: {
  p: ProviderInfo;
  onSaved: (s: ProvidersStatus) => void;
  onError: (msg: string) => void;
  onActivate: () => Promise<void>;
}) {
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(p.model);
  const [baseUrl, setBaseUrl] = useState(p.base_url);
  const [models, setModels] = useState<string[]>([]);
  const [busy, setBusy] = useState<"" | "save" | "test" | "models">("");
  const [test, setTest] = useState<TestResult | null>(null);

  const save = async (extra: Record<string, unknown> = {}) => {
    const body: Record<string, unknown> = { name: p.name, activate: false, model, base_url: baseUrl, ...extra };
    if (apiKey) body.api_key = apiKey;
    const next = await postProviders(body);
    setApiKey("");
    onSaved(next);
  };

  const run = async (kind: "save" | "test" | "models", fn: () => Promise<void>) => {
    setBusy(kind);
    onError("");
    try {
      await fn();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  };

  const loadModels = () => run("models", async () => {
    await save();
    const res = await api(`/providers/${p.name}/models`);
    const data = await res.json();
    if (!res.ok) throw new Error(String(data.detail ?? "Liste indisponible"));
    setModels(data.models ?? []);
  });

  const testConnection = () => run("test", async () => {
    await save();
    const res = await api(`/providers/${p.name}/test`, { method: "POST" });
    setTest((await res.json()) as TestResult);
  });

  const listId = `models-${p.name}`;
  return (
    <div className="set-editor">
      {p.needs_key && (
        <label className="set-field">
          <span className="set-label"><KeyRound size={13} /> Clé API {p.api_key_masked && <em>(enregistrée : {p.api_key_masked})</em>}</span>
          <div className="flex gap-2">
            <input
              className="set-input"
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={p.api_key_masked ? "Laisser vide pour conserver la clé" : "Collez votre clé ici"}
            />
            {KEY_PAGES[p.name] && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => void openExternal(KEY_PAGES[p.name])}>
                <ExternalLink />Obtenir une clé
              </button>
            )}
          </div>
        </label>
      )}
      <label className="set-field">
        <span className="set-label">Modèle</span>
        <div className="flex gap-2">
          <input className="set-input" list={listId} value={model} onChange={(e) => setModel(e.target.value)} placeholder="nom-du-modele" />
          <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => void loadModels()}>
            {busy === "models" ? <Loader2 className="animate-spin" /> : <ListRestart />}Charger la liste
          </button>
        </div>
        <datalist id={listId}>{models.map((m) => <option key={m} value={m} />)}</datalist>
        {models.length > 0 && <span className="set-hint">{models.length} modèles disponibles : tapez pour filtrer.</span>}
      </label>
      <label className="set-field">
        <span className="set-label">Adresse de l'API</span>
        <input className="set-input" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://…/v1" />
      </label>

      {test && (
        <p className={`set-status ${test.ok ? "ok" : "err"}`} role="status">
          {test.ok ? <CheckCircle size={14} /> : <XCircle size={14} />} {test.detail}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => void testConnection()}>
          {busy === "test" ? <Loader2 className="animate-spin" /> : <Plug />}Tester
        </button>
        <button type="button" className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => void run("save", () => save())}>
          Enregistrer
        </button>
        <button type="button" className="btn btn-primary btn-sm" disabled={!!busy} onClick={() => void run("save", async () => { await save(); await onActivate(); })}>
          Utiliser ce cerveau
        </button>
        {p.api_key_masked && (
          <button
            type="button"
            className="btn btn-danger btn-sm"
            disabled={!!busy}
            onClick={() => {
              if (window.confirm(`Supprimer la clé ${p.label} ?`)) void run("save", () => save({ api_key: "" }));
            }}
          >
            <Trash2 />Supprimer la clé
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Onglet ──────────────────────────────────────────────────────────────── */

/** Onglet CERVEAU — clés API, modèles, cerveau actif et routage AUTO.
 *  Les clés sont write-only : envoyées au serveur, jamais relues. */
export function ProvidersTab() {
  const [status, setStatus] = useState<ProvidersStatus | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    api("/providers")
      .then((r) => r.json())
      .then((d: ProvidersStatus) => setStatus(d))
      .catch(() => setError("Serveur injoignable"));
  }, []);
  useEffect(refresh, [refresh]);

  const apply = (next: ProvidersStatus) => {
    setStatus(next);
    // Mise à jour immédiate du HUD (label CERVEAU) sans attendre le WS
    useJarvisStore.setState({ providerLabel: next.active_label, providerModel: next.active_model });
  };

  const activate = async (name: string) => {
    setBusy(true);
    setError("");
    try {
      apply(await postProviders({ name, activate: true }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const saveRouting = async (extra: Record<string, unknown>) => {
    if (!status) return;
    setBusy(true);
    setError("");
    try {
      apply(await postProviders({ name: status.active, activate: false, ...extra }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!status) {
    return (
      <p className="set-hint flex items-center gap-2">
        {error || <><Loader2 size={14} className="animate-spin" /> Chargement…</>}
      </p>
    );
  }

  const isAuto = status.active === "auto";
  const configuredCount = status.providers.filter((p) => p.configured).length;

  return (
    <>
      <div className="set-banner">
        <Cpu size={16} />
        <span>
          Cerveau actif : <strong>{status.active_label}</strong>
          {status.active_model && <em> · {status.active_model}</em>}
        </span>
      </div>
      {error && <p className="set-status err" role="alert">{error}</p>}

      <Section
        title="Fournisseurs"
        hint="Les clés restent sur votre machine, côté serveur, et ne sont jamais réaffichées. Toute API compatible OpenAI fonctionne via « API personnalisée ». En cas de panne d'un cerveau cloud, JARVIS bascule sur le cerveau local."
      >
        <div className="set-providers">
          <button
            type="button"
            className={`set-provider${status.active === "local" ? " is-active" : ""}`}
            disabled={busy || !status.local_available}
            onClick={() => void activate("local")}
          >
            <i className={status.local_available ? "pdot ok" : "pdot"} />
            <span className="set-provider-text">
              <strong>Local (Mistral GGUF)</strong>
              <small>{status.local_available ? "100 % privé · hors ligne" : "Modèle local non installé"}</small>
            </span>
            {status.active === "local" && <CheckCircle size={16} />}
          </button>
          {status.providers.map((p) => {
            const active = status.active === p.name;
            const isOpen = open === p.name;
            return (
              <div key={p.name}>
                <button
                  type="button"
                  className={`set-provider${active ? " is-active" : ""}`}
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? null : p.name)}
                >
                  <i className={p.configured ? "pdot ok" : "pdot"} />
                  <span className="set-provider-text">
                    <strong>{p.label}</strong>
                    <small>
                      {p.configured ? p.model || "modèle à définir" : p.needs_key ? "Clé API à renseigner" : p.model || "à configurer"}
                      {p.api_key_masked && ` · clé ${p.api_key_masked}`}
                    </small>
                  </span>
                  {active && <CheckCircle size={16} />}
                </button>
                {isOpen && (
                  <ProviderEditor
                    p={p}
                    onSaved={apply}
                    onError={setError}
                    onActivate={() => activate(p.name)}
                  />
                )}
              </div>
            );
          })}
        </div>
      </Section>
      <Section
        title="Mode AUTO — un cerveau par niveau de réflexion"
        hint="Chaque demande part vers le premier cerveau disponible de sa chaîne ; si le premier tarde, le suivant démarre en parallèle et le plus rapide répond. Les cerveaux grisés n'ont pas de clé et sont ignorés. Écrivez « fournisseur@modèle » pour imposer un modèle."
      >
        <div className="flex flex-wrap items-center gap-3">
          {isAuto ? (
            <span className="set-status ok"><Zap size={14} /> Mode AUTO actif</span>
          ) : (
            <button type="button" className="btn btn-primary btn-sm" disabled={busy || configuredCount === 0} onClick={() => void activate("auto")}>
              <Zap />Activer le mode AUTO
            </button>
          )}
          {status.routing && (
            <label className="set-check">
              <input
                type="checkbox"
                checked={status.routing.hedging}
                disabled={busy}
                onChange={(e) => void saveRouting({ hedging: e.target.checked })}
              />
              Course au premier mot
            </label>
          )}
        </div>
        {status.routing && (
          <dl className="set-resolved">
            {LEVELS.map((l) => (
              <div key={l.id}>
                <dt>{l.label}</dt>
                <dd>{status.routing!.resolved[l.id]?.slice(0, 3).join("  →  ") || "aucun cerveau avec clé (cerveau local)"}</dd>
              </div>
            ))}
          </dl>
        )}
        <ChainEditor status={status} busy={busy} onSave={(chains) => void saveRouting({ chains })} />
      </Section>

    </>
  );
}
