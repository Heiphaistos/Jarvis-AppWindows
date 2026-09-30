from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from tools.decorator import tool
from utils.logger import get_logger

logger = get_logger("pc_tools")

# Diagnostic du PC via NiTriTe Agent (voir core/nitrite.py) : santé batterie,
# SMART des disques, températures, plantages, démarrage, performances.
# Chaque section est résumée en texte compact et des ALERTES sont calculées
# localement (seuils fixes) : JARVIS ne dépend pas du LLM pour repérer un
# disque qui meurt ou une batterie usée.

TOPICS: dict[str, list[tuple[str, str, dict]]] = {
    "batterie": [("Batterie", "get_battery_detailed", {})],
    "disques": [("Disques (SMART)", "get_disks_smart", {})],
    "temperatures": [("Températures", "get_temperatures", {}), ("GPU", "get_gpu_temps", {})],
    "plantages": [("Écrans bleus", "get_bsod_history", {}),
                  ("Journal Système (erreurs récentes)", "get_event_logs", {"logName": "System", "count": 15})],
    "demarrage": [("Programmes au démarrage", "get_startup_programs", {})],
    "sante": [("Santé de Windows", "check_system_health", {})],
    "performances": [("Performances", "get_perf_snapshot", {}),
                     ("Processus les plus gourmands", "get_top_processes_by_cpu", {"limit": 8})],
    "materiel": [("Système", "get_system_info", {}), ("Mémoire vive", "get_ram_detailed", {}),
                 ("Carte graphique", "get_gpu_detailed", {})],
}
_ALIASES = {
    "battery": "batterie", "disk": "disques", "disque": "disques", "ssd": "disques", "smart": "disques",
    "temperature": "temperatures", "température": "temperatures", "températures": "temperatures",
    "chaleur": "temperatures", "crash": "plantages", "bsod": "plantages", "ecran bleu": "plantages",
    "écran bleu": "plantages", "startup": "demarrage", "démarrage": "demarrage", "health": "sante",
    "santé": "sante", "windows": "sante", "perf": "performances", "lenteur": "performances",
    "hardware": "materiel", "matériel": "materiel", "ram": "materiel", "gpu": "materiel",
}
_SECTION_CHARS = 1400


def _norm_topic(topic: str) -> str | None:
    t = (topic or "").strip().lower()
    if t in ("", "all", "tout", "complet", "global"):
        return "all"
    return t if t in TOPICS else _ALIASES.get(t)


def compact(value, max_items: int = 12, depth: int = 0) -> list[str]:
    """JSON → lignes « clé: valeur » lisibles, sans champs vides, listes bornées."""
    pad = "  " * depth
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            if v in (None, "", [], {}):
                continue
            label = str(k).replace("_", " ")
            if isinstance(v, (dict, list)):
                sub = compact(v, max_items, depth + 1)
                if sub:
                    lines.append(f"{pad}{label}:")
                    lines += sub
            else:
                if isinstance(v, float):
                    v = round(v, 1)
                lines.append(f"{pad}{label}: {v}")
        return lines
    if isinstance(value, list):
        lines = []
        for i, item in enumerate(value[:max_items]):
            sub = compact(item, max_items, depth + 1)
            if isinstance(item, (dict, list)) and sub:
                lines.append(f"{pad}- #{i + 1}")
                lines += sub
            elif sub:
                lines.append(f"{pad}- {sub[0].strip()}")
        if len(value) > max_items:
            lines.append(f"{pad}… {len(value) - max_items} de plus")
        return lines
    return [f"{pad}{value}"] if value not in (None, "") else []


def _num(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return v
    return None


def alerts(data: dict[str, object]) -> list[str]:
    """Problèmes détectés sur les résultats bruts (clé = commande NiTriTe)."""
    out: list[str] = []
    for b in data.get("get_battery_detailed") or []:
        if not isinstance(b, dict):
            continue
        health = _num(b, "battery_health_percent", "batteryHealthPercent")
        if not health:
            design, full = _num(b, "design_capacity", "designCapacity"), _num(b, "full_charge_capacity", "fullChargeCapacity")
            health = round(100 * full / design, 1) if design and full else None
        if health:
            if health < 60:
                out.append(f"CRITIQUE — batterie usée : {health:.0f} % de sa capacité d'origine, à remplacer.")
            elif health < 80:
                out.append(f"Attention — batterie fatiguée : {health:.0f} % de sa capacité d'origine.")
        cycles = _num(b, "cycle_count", "cycleCount")
        if cycles and cycles > 800:
            out.append(f"Attention — batterie : {cycles} cycles de charge.")
    for d in data.get("get_disks_smart") or []:
        if not isinstance(d, dict):
            continue
        name = d.get("label") or f"disque {d.get('disk_index', '?')}"
        health = str(d.get("health", ""))
        if health in ("Warning", "Unhealthy"):
            level = "CRITIQUE" if health == "Unhealthy" else "Attention"
            out.append(f"{level} — {name} : état SMART « {health} », sauvegardez vos données.")
        realloc = _num(d, "reallocated_sectors", "reallocatedSectors")
        if realloc:
            out.append(f"Attention — {name} : {realloc} secteurs réalloués (usure physique).")
        temp = _num(d, "temperature")
        if temp and temp >= 60:
            out.append(f"Attention — {name} à {temp} °C.")
    for key in ("get_temperatures", "get_gpu_temps"):
        for t in data.get(key) or []:
            if not isinstance(t, dict):
                continue
            c = _num(t, "temp_celsius", "tempCelsius", "temperature")
            if c and c >= 90:
                out.append(f"CRITIQUE — {t.get('sensor_name') or t.get('name') or 'capteur'} à {c:.0f} °C.")
            elif c and c >= 80:
                out.append(f"Attention — {t.get('sensor_name') or t.get('name') or 'capteur'} à {c:.0f} °C.")
    bsod = data.get("get_bsod_history")
    if isinstance(bsod, dict) and (_num(bsod, "total_count", "totalCount") or 0) > 0:
        out.append(f"Attention — {bsod.get('total_count', bsod.get('totalCount'))} écran(s) bleu(s) enregistré(s), "
                   f"dernier : {bsod.get('last_bsod') or bsod.get('lastBsod') or 'date inconnue'}.")
    health = data.get("check_system_health")
    if isinstance(health, dict):
        if health.get("pending_reboot") or health.get("pendingReboot"):
            out.append("Info — un redémarrage est en attente (mises à jour).")
        for err in (health.get("disk_errors") or health.get("diskErrors") or [])[:3]:
            out.append(f"Attention — erreur disque signalée par Windows : {err}")
    perf = data.get("get_perf_snapshot")
    if isinstance(perf, dict):
        ram = _num(perf, "ram_percent", "ramPercent")
        if ram and ram >= 90:
            out.append(f"Attention — mémoire vive saturée ({ram:.0f} %).")
    startup = data.get("get_startup_programs")
    if isinstance(startup, list) and len(startup) > 15:
        out.append(f"Info — {len(startup)} programmes se lancent au démarrage : le démarrage peut être lent.")
    return out


def _collect(sections: list[tuple[str, str, dict]]) -> tuple[dict, dict, list[str]]:
    from core import nitrite
    raw: dict[str, object] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=min(len(sections), 6)) as pool:
        futures = {pool.submit(nitrite.invoke, cmd, args): (label, cmd) for label, cmd, args in sections}
        for fut, (label, cmd) in futures.items():
            try:
                raw[cmd] = fut.result(timeout=90)
            except nitrite.NitriteUnavailable:
                raise
            except Exception as e:
                errors.append(f"{label} : indisponible ({str(e)[:100]})")
    labels = {cmd: label for label, cmd, _ in sections}
    return raw, labels, errors


def _fallback_report() -> str:
    """Sans NiTriTe : ce que psutil sait (moins complet)."""
    lines = ["NiTriTe Agent n'est pas lancé — diagnostic de base uniquement."]
    try:
        import psutil
        bat = psutil.sensors_battery()
        if bat is not None:
            lines.append(f"Batterie : {bat.percent:.0f} %{' (en charge)' if bat.power_plugged else ''}")
        lines.append(f"CPU : {psutil.cpu_percent(interval=0.5):.0f} % · RAM : {psutil.virtual_memory().percent:.0f} %")
        for part in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(part.mountpoint)
                lines.append(f"Disque {part.mountpoint} : {u.percent:.0f} % utilisé, {u.free / 1e9:.0f} Go libres")
            except OSError:
                continue
    except Exception as e:
        lines.append(f"(psutil indisponible : {e})")
    lines.append("Pour la santé de la batterie, l'état SMART des disques, les températures et l'historique "
                 "des plantages : dites « lance NiTriTe ».")
    return "\n".join(lines)


def _report(topic: str) -> tuple[str, str]:
    """(texte pour le LLM, markdown pour le fichier)."""
    from core import nitrite
    key = _norm_topic(topic)
    if key is None:
        return f"Sujet inconnu : {topic}. Possibles : {', '.join(TOPICS)} ou « tout ».", ""
    sections = [s for k in (TOPICS if key == "all" else [key]) for s in TOPICS[k]]
    try:
        raw, labels, errors = _collect(sections)
    except nitrite.NitriteUnavailable as e:
        logger.info(f"NiTriTe indisponible : {e}")
        text = _fallback_report()
        return text, text
    found = alerts(raw)
    parts = ["ALERTES :\n" + ("\n".join(f"- {a}" for a in found) if found else "- aucune anomalie détectée")]
    for cmd, value in raw.items():
        body = "\n".join(compact(value))[:_SECTION_CHARS] or "(vide)"
        parts.append(f"## {labels[cmd]}\n{body}")
    if errors:
        parts.append("Non disponible : " + " ; ".join(errors))
    text = "\n\n".join(parts)
    return text, text


@tool
def pc_diagnostic(topic: str = "all") -> str:
    """Diagnostic du PC via NiTriTe : batterie (santé, cycles), disques (SMART), temperatures, plantages (écrans bleus, journal), demarrage, sante (Windows), performances, materiel — ou « all ». Signale les anomalies."""
    text, _ = _report(topic)
    return text


def _reports_dir() -> Path:
    docs = Path.home() / "Documents"
    return (docs if docs.is_dir() else Path.home()) / "JARVIS" / "Rapports"


@tool
def pc_health_report() -> str:
    """Rapport complet de santé du PC (batterie, disques, températures, plantages, Windows, performances, matériel), enregistré en Markdown dans Documents/JARVIS/Rapports."""
    text, markdown = _report("all")
    try:
        folder = _reports_dir()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"rapport-pc-{datetime.now():%Y%m%d-%H%M}.md"
        path.write_text(
            f"# Rapport de santé du PC — {datetime.now():%d/%m/%Y %H:%M}\n\n_Généré par JARVIS avec NiTriTe_\n\n{markdown}\n",
            encoding="utf-8",
        )
        return f"{text}\n\nRapport enregistré : {path}"
    except OSError as e:
        return f"{text}\n\n(Rapport non enregistré : {e})"


@tool
def nitrite_start() -> str:
    """Lance NiTriTe Agent (moteur de diagnostic avancé) en arrière-plan, sans navigateur."""
    from core import nitrite
    return nitrite.start_agent()
