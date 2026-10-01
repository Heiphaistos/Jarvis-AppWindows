import { useEffect, useState } from "react";
import { Brain, Trash2, Lightbulb, Loader2, MessagesSquare } from "lucide-react";
import { useJarvisStore } from "../../stores/jarvisStore";
import { SERVER_ORIGIN } from "../../lib/platform";

const API = `${SERVER_ORIGIN}/api`;

interface Fact {
  key: string;
  value: string;
  category: string;
  updated_at: string;
}

interface Lesson {
  id: number;
  lesson: string;
  created_at: string;
}

interface Episode {
  id: number;
  summary: string;
  created_at: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  identite: "Identité",
  preferences: "Préférences",
  projets: "Projets",
  travail: "Travail",
  relations: "Proches",
  habitudes: "Habitudes",
  lieux: "Lieux",
  sante: "Santé",
  general: "Divers",
};

/** Onglet MÉMOIRE — ce que JARVIS sait, ses leçons, et la mémoire automatique. */
export function MemoryTab() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [auto, setAuto] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Recharge quand JARVIS apprend quelque chose pendant que l'onglet est ouvert.
  const memoryVersion = useJarvisStore((s) => s.memoryVersion);

  useEffect(() => {
    fetch(`${API}/memories`)
      .then((r) => r.json())
      .then((d) => {
        setFacts(d.facts ?? []);
        setLessons(d.lessons ?? []);
        setEpisodes(d.episodes ?? []);
        setAuto(Boolean(d.auto));
        setError("");
      })
      .catch(() => setError("Serveur injoignable"))
      .finally(() => setLoading(false));
  }, [memoryVersion]);

  const toggleAuto = async () => {
    const next = !auto;
    setAuto(next);
    try {
      const r = await fetch(`${API}/memories/auto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
      setAuto(Boolean((await r.json()).auto));
    } catch {
      setAuto(!next);
      setError("Serveur injoignable");
    }
  };

  const forgetFact = async (key: string) => {
    setFacts((f) => f.filter((x) => x.key !== key));
    await fetch(`${API}/memories/${encodeURIComponent(key)}`, { method: "DELETE" }).catch(() => {});
  };

  const forgetLesson = async (id: number) => {
    setLessons((l) => l.filter((x) => x.id !== id));
    await fetch(`${API}/lessons/${id}`, { method: "DELETE" }).catch(() => {});
  };

  const forgetEpisode = async (id: number) => {
    setEpisodes((e) => e.filter((x) => x.id !== id));
    await fetch(`${API}/episodes/${id}`, { method: "DELETE" }).catch(() => {});
  };

  const grouped = facts.reduce<Record<string, Fact[]>>((acc, f) => {
    (acc[f.category] ??= []).push(f);
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-4">
      <button
        onClick={() => void toggleAuto()}
        className="flex items-start gap-3 p-3 rounded-xl text-left transition-all"
        style={{
          background: auto ? "rgb(var(--accent-rgb) / 0.08)" : "rgba(255,255,255,0.02)",
          border: `1px solid ${auto ? "rgb(var(--accent-rgb) / 0.3)" : "rgba(255,255,255,0.06)"}`,
        }}
      >
        <Brain size={16} className={auto ? "text-cyan-400 mt-0.5" : "text-blue-400/40 mt-0.5"} />
        <div className="flex-1">
          <div className="text-[12px] font-bold tracking-wider" style={{ color: auto ? "var(--accent)" : "#ffffff88" }}>
            MÉMOIRE AUTOMATIQUE
            <span className={`ml-2 text-[8px] ${auto ? "text-green-400" : "text-blue-400/40"}`}>
              {auto ? "● ACTIVE" : "○ COUPÉE"}
            </span>
          </div>
          <div className="text-[9px] text-blue-400/40 mt-0.5 leading-relaxed">
            Après chaque échange, JARVIS retient ce que vous dites de vous (identité, goûts, projets, proches)
            et tire une leçon quand vous le corrigez. Jamais de mot de passe ni de numéro de carte.
          </div>
        </div>
      </button>

      {error && <div className="text-[9px] text-red-400 px-1">{error}</div>}
      {loading && (
        <div className="flex items-center gap-2 text-[10px] text-blue-400/50">
          <Loader2 size={11} className="animate-spin" /> Lecture de la mémoire…
        </div>
      )}

      <div className="flex flex-col gap-3">
        <div className="text-[9px] tracking-[0.2em] text-blue-400/50">
          CE QUE JARVIS SAIT ({facts.length})
        </div>
        {!loading && facts.length === 0 && (
          <div className="text-[10px] text-blue-400/40">Rien pour l'instant — parlez-lui de vous.</div>
        )}
        {Object.entries(grouped).map(([category, items]) => (
          <div key={category} className="flex flex-col gap-1">
            <div className="text-[8px] tracking-[0.2em] text-cyan-400/60 uppercase">
              {CATEGORY_LABELS[category] ?? category}
            </div>
            {items.map((f) => (
              <div
                key={f.key}
                className="group flex items-start gap-2 px-2.5 py-1.5 rounded-lg"
                style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)" }}
              >
                <div className="flex-1 min-w-0">
                  <span className="text-[9px] font-mono text-blue-400/50">{f.key.replace(/_/g, " ")}</span>
                  <div className="text-[11px] text-white/80 break-words">{f.value}</div>
                </div>
                <button
                  onClick={() => void forgetFact(f.key)}
                  title="Oublier"
                  className="opacity-40 hover:opacity-100 text-red-400 transition-opacity mt-0.5"
                >
                  <Trash2 size={11} />
                </button>
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="text-[9px] tracking-[0.2em] text-blue-400/50">CONVERSATIONS PASSÉES ({episodes.length})</div>
        {!loading && episodes.length === 0 && (
          <div className="text-[10px] text-blue-400/40">Les conversations sont résumées et archivées automatiquement.</div>
        )}
        {episodes.map((e) => (
          <div
            key={e.id}
            className="flex items-start gap-2 px-2.5 py-1.5 rounded-lg"
            style={{ background: "rgb(var(--accent-rgb) / 0.03)", border: "1px solid rgb(var(--accent-rgb) / 0.1)" }}
          >
            <MessagesSquare size={11} className="text-cyan-400/60 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <span className="text-[8px] font-mono text-blue-400/50">
                {new Date(e.created_at + "Z").toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}
              </span>
              <div className="text-[10px] text-white/70 break-words">{e.summary}</div>
            </div>
            <button
              onClick={() => void forgetEpisode(e.id)}
              title="Oublier cette conversation"
              className="opacity-40 hover:opacity-100 text-red-400 transition-opacity"
            >
              <Trash2 size={11} />
            </button>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="text-[9px] tracking-[0.2em] text-blue-400/50">LEÇONS APPRISES ({lessons.length})</div>
        {!loading && lessons.length === 0 && (
          <div className="text-[10px] text-blue-400/40">Aucune erreur à retenir pour l'instant.</div>
        )}
        {lessons.map((l) => (
          <div
            key={l.id}
            className="flex items-start gap-2 px-2.5 py-1.5 rounded-lg"
            style={{ background: "rgba(255,170,0,0.04)", border: "1px solid rgba(255,170,0,0.12)" }}
          >
            <Lightbulb size={11} className="text-amber-400/70 shrink-0 mt-0.5" />
            <div className="flex-1 text-[10px] text-white/70 break-words">{l.lesson}</div>
            <button
              onClick={() => void forgetLesson(l.id)}
              title="Oublier cette leçon"
              className="opacity-40 hover:opacity-100 text-red-400 transition-opacity"
            >
              <Trash2 size={11} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
