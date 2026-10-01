import { useEffect } from "react";
import { useJarvisStore, THEMES, accentOf } from "../../stores/jarvisStore";
import type { JarvisStatus } from "../../types";

function hexToRgb(hex: string): string {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex.trim());
  return m ? `${parseInt(m[1], 16)} ${parseInt(m[2], 16)} ${parseInt(m[3], 16)}` : "0 212 255";
}

/** Pose la palette (--accent-rgb) et l'esthétique (data-skin) sur <html>. */
export function useThemeVars() {
  const theme = useJarvisStore((s) => s.theme);
  const customAccent = useJarvisStore((s) => s.customAccent);
  const skin = useJarvisStore((s) => s.skin);
  useEffect(() => {
    const root = document.documentElement;
    const accent = accentOf(theme, customAccent);
    root.style.setProperty("--accent-rgb", hexToRgb(accent));
    root.style.setProperty("--accent-2-rgb", hexToRgb(theme === "custom" ? accent : THEMES[theme].accentSoft));
    root.dataset.skin = skin;
  }, [theme, customAccent, skin]);
}

export const STATUS_LABELS: Record<JarvisStatus, string> = {
  idle: "EN LIGNE",
  standby: "VEILLE · « HEY JARVIS »",
  listening: "ÉCOUTE",
  processing: "ANALYSE",
  speaking: "PAROLE",
  error: "ERREUR",
};

export const STATUS_COLORS: Record<Exclude<JarvisStatus, "idle">, string> = {
  standby: "#3388cc",
  listening: "#00ff88",
  processing: "#ffaa00",
  speaking: "#b388ff",
  error: "#ff4466",
};

/** Couleur CSS du statut (idle = accent du thème). */
export function statusCss(status: JarvisStatus): string {
  return status === "idle" ? "var(--accent)" : STATUS_COLORS[status];
}
