import { accentOf, useJarvisStore } from "../../stores/jarvisStore";
import type { JarvisStatus } from "../../types";

export const STATUS_LABELS: Record<JarvisStatus, string> = {
  idle: "EN LIGNE",
  standby: "VEILLE · « HEY JARVIS »",
  listening: "ÉCOUTE",
  processing: "ANALYSE",
  speaking: "PAROLE",
  error: "ANOMALIE",
};

/** Accent du thème courant. */
export function useAccent(): string {
  const theme = useJarvisStore((s) => s.theme);
  const custom = useJarvisStore((s) => s.customAccent);
  return accentOf(theme, custom);
}

/** Couleur du statut courant (repos = accent du thème). */
export function useStatusColor(): { status: JarvisStatus; color: string } {
  const status = useJarvisStore((s) => s.status);
  const accent = useAccent();
  const map: Record<JarvisStatus, string> = {
    idle: accent,
    standby: "#3388cc",
    listening: "#00ff88",
    processing: "#ffaa00",
    speaking: "#8866ff",
    error: "#ff3355",
  };
  return { status, color: map[status] };
}
