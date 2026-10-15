// Mise à jour automatique : plugin officiel Tauri (manifeste signé minisign
// sur les releases GitHub), installation silencieuse (NSIS « passive »), relance.
import { create } from "zustand";
import { isTauri } from "./platform";

const KEY = "jarvis_auto_update";

/** Réglage « vérifier automatiquement » : actif par défaut, seul "0" le coupe. */
export function readAutoUpdate(): boolean {
  try {
    return localStorage.getItem(KEY) !== "0";
  } catch {
    return true;
  }
}

export function writeAutoUpdate(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? "1" : "0");
  } catch {
    /* stockage indisponible : le réglage reste valable pour la session */
  }
}

/** Pas de mise à jour en dev ni dans le panneau web (rien à remplacer). */
export const updaterAvailable = isTauri && !import.meta.env.DEV;

export type UpdatePhase = "idle" | "checking" | "uptodate" | "available" | "installing" | "error";

interface UpdateState {
  phase: UpdatePhase;
  auto: boolean;
  version: string;
  notes: string;
  percent: number | null; // null = taille inconnue
  error: string;
  setAuto: (on: boolean) => void;
  dismiss: () => void;
}

export const useUpdateStore = create<UpdateState>((set) => ({
  phase: "idle",
  auto: readAutoUpdate(),
  version: "",
  notes: "",
  percent: null,
  error: "",
  setAuto: (auto) => {
    writeAutoUpdate(auto);
    set({ auto });
  },
  dismiss: () => set({ phase: "idle" }),
}));

const set = useUpdateStore.setState;
type DownloadEvent = { event: string; data?: { contentLength?: number; chunkLength?: number } };
let pending: { downloadAndInstall: (cb: (e: DownloadEvent) => void) => Promise<void> } | null = null;

/**
 * Cherche une mise à jour. `silent` = vérification au démarrage : rien
 * d'affiché s'il n'y a rien ou si le canal est injoignable.
 */
export async function checkForUpdate(silent: boolean): Promise<void> {
  if (!updaterAvailable) return;
  const { phase } = useUpdateStore.getState();
  if (phase === "checking" || phase === "installing") return;
  set({ phase: "checking", error: "" });
  try {
    const { check } = await import("@tauri-apps/plugin-updater");
    const update = await check();
    if (!update) {
      set({ phase: silent ? "idle" : "uptodate" });
      return;
    }
    pending = update;
    set({ phase: "available", version: update.version, notes: update.body ?? "", percent: null });
  } catch (e) {
    console.error("[maj] vérification impossible", e);
    set({ phase: silent ? "idle" : "error", error: String(e) });
  }
}

/** Télécharge, vérifie la signature, installe, puis relance JARVIS. */
export async function installUpdate(): Promise<void> {
  if (!pending) return;
  set({ phase: "installing", percent: null });
  try {
    let total = 0;
    let done = 0;
    await pending.downloadAndInstall((e) => {
      if (e.event === "Started") total = e.data?.contentLength ?? 0;
      if (e.event === "Progress") {
        done += e.data?.chunkLength ?? 0;
        if (total > 0) set({ percent: Math.min(100, Math.round((done / total) * 100)) });
      }
    });
    const { relaunch } = await import("@tauri-apps/plugin-process");
    await relaunch();
  } catch (e) {
    console.error("[maj] installation impossible", e);
    set({ phase: "error", error: String(e) });
  }
}
