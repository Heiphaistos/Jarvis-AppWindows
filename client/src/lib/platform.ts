/**
 * Où tourne l'interface, et comment joindre le serveur JARVIS.
 *
 * - Application Tauri (et serveur Vite de développement) : le serveur local
 *   http://127.0.0.1:8765.
 * - Panneau web (agent local) ou version hébergée : l'interface est servie
 *   par le serveur lui-même → même origine, URL relatives.
 */
export const isTauri =
  typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

const LOCAL_SERVER = "http://127.0.0.1:8765";
const sameOrigin = !isTauri && !import.meta.env.DEV;

/** Base HTTP du serveur ("" = même origine). */
export const SERVER_ORIGIN = sameOrigin ? "" : LOCAL_SERVER;

export const apiUrl = (path: string) => `${SERVER_ORIGIN}/api${path.startsWith("/") ? path : `/${path}`}`;

export function wsUrl(): string {
  if (!sameOrigin) return "ws://127.0.0.1:8765/ws";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws`;
}

/** fetch vers l'API, cookie de session compris. */
export function api(path: string, init?: RequestInit): Promise<Response> {
  return fetch(apiUrl(path), { credentials: "same-origin", ...init });
}

/** Ouvre un lien externe (navigateur par défaut). */
export async function openExternal(url: string): Promise<void> {
  if (isTauri) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}

/** Libellé de la liaison temps réel (télémétrie, séquence de démarrage). */
export function linkLabel(): string {
  if (!sameOrigin) return "WS · 8765";
  return window.location.protocol === "https:" ? "WSS · TLS" : `WS · ${window.location.port || "80"}`;
}

/** Adresse de retour OAuth Gmail à déclarer dans la console Google. */
export function gmailRedirectUri(): string {
  const base = sameOrigin ? window.location.origin : "http://localhost:8765";
  return `${base}/api/auth/gmail/callback`;
}
