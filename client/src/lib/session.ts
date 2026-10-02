import { api, isTauri } from "./platform";

export type ServerMode = "desktop" | "agent" | "hosted";

export interface SessionState {
  mode: ServerMode;
  authenticated: boolean;
  passwordConfigured?: boolean | null;
  /** Le serveur ne répond pas (agent arrêté, VPS injoignable). */
  offline?: boolean;
}

let current: ServerMode = "desktop";

export const serverMode = () => current;

/**
 * Ouvre la session du panneau web.
 * Agent local : la clé arrive dans le fragment de l'URL (#t=…, jamais envoyé
 * sur le réseau). Elle est échangée contre un cookie HttpOnly, puis effacée
 * de la barre d'adresse et de l'historique.
 */
export async function bootstrapSession(): Promise<SessionState> {
  if (isTauri) return { mode: "desktop", authenticated: true };
  const token = new URLSearchParams(window.location.hash.slice(1)).get("t");
  if (token) {
    history.replaceState(null, "", window.location.pathname + window.location.search);
    try {
      await api("/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
    } catch {
      /* l'état réel est relu juste après */
    }
  }
  try {
    const r = await api("/session");
    const s = (await r.json()) as SessionState;
    current = s.mode;
    return s;
  } catch {
    return { mode: "agent", authenticated: false, offline: true };
  }
}

export async function login(password: string): Promise<string | null> {
  try {
    const r = await api("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (r.ok) return null;
    const d = (await r.json().catch(() => ({}))) as { detail?: string };
    return d.detail ?? `Erreur ${r.status}`;
  } catch {
    return "Serveur injoignable.";
  }
}

export async function logout(): Promise<void> {
  await api("/logout", { method: "POST" }).catch(() => undefined);
  window.location.reload();
}

export async function stopAgent(): Promise<void> {
  await api("/agent/shutdown", { method: "POST" }).catch(() => undefined);
}
