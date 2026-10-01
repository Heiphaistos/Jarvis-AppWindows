from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

from tools.decorator import tool
from utils.logger import get_logger

logger = get_logger("assistant_tools")

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JARVIS/4.8"
_MAX_PAGE_CHARS = 6000


# ── Minuteurs et rappels ──────────────────────────────────────────────────────

@tool
def set_timer(minutes: float, label: str = "") -> str:
    """Lance un minuteur de N minutes (décimales acceptées : 0.5 = 30 s). JARVIS l'annonce à voix haute à l'échéance."""
    from core.reminders import get_reminders
    minutes = float(minutes)
    if not 0 < minutes <= 24 * 60:
        return "Durée invalide : entre quelques secondes et 24 heures."
    r = get_reminders().add(minutes * 60, label or f"Minuteur de {minutes:g} min écoulé", "timer")
    return f"Minuteur #{r.id} lancé pour {minutes:g} min (fin à {datetime.fromtimestamp(r.due):%H:%M:%S})."


_TIME_RE = re.compile(r"^(?:(\d{4}-\d{2}-\d{2})[ T])?(\d{1,2})[:hH](\d{2})?$")


@tool
def set_reminder(when: str, message: str) -> str:
    """Programme un rappel parlé. when : « 18:30 », « 18h », « 2026-10-02 09:00 » ou un délai « dans 20 min », « dans 2 h »."""
    from core.reminders import get_reminders
    text = when.strip().lower()
    now = datetime.now()
    m = re.match(r"^dans\s+(\d+(?:[.,]\d+)?)\s*(min|minutes?|h|heures?|s|sec|secondes?|j|jours?)$", text)
    if m:
        value = float(m.group(1).replace(",", "."))
        unit = m.group(2)
        seconds = value * (3600 if unit.startswith("h") else 86400 if unit.startswith("j") else 1 if unit.startswith("s") else 60)
        target = now + timedelta(seconds=seconds)
    else:
        m = _TIME_RE.match(text)
        if not m:
            return "Format d'heure non reconnu. Exemples : « 18:30 », « 2026-10-02 09:00 », « dans 20 min »."
        day = datetime.strptime(m.group(1), "%Y-%m-%d").date() if m.group(1) else now.date()
        target = datetime.combine(day, datetime.min.time()).replace(hour=int(m.group(2)), minute=int(m.group(3) or 0))
        if target <= now and not m.group(1):
            target += timedelta(days=1)  # « 8h » alors qu'il est 10h → demain
    delay = (target - now).total_seconds()
    if delay <= 0:
        return "Cette heure est déjà passée."
    if delay > 366 * 86400:
        return "Rappel trop lointain (un an maximum)."
    r = get_reminders().add(delay, message, "reminder")
    return f"Rappel #{r.id} programmé le {target:%d/%m à %H:%M} : {message}"


_DAY_WORDS = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
}


def parse_days(text: str) -> list[int]:
    """« tous les jours », « en semaine », « week-end », « lundi, mercredi », « lundi-vendredi »."""
    t = (text or "").strip().lower()
    if not t or re.search(r"tous les jours|chaque jour|quotidien|daily|tlj", t):
        return list(range(7))
    if re.search(r"semaine|ouvr[ée]s?|ouvrables?|weekdays?", t) and "week-end" not in t:
        return list(range(5))
    if re.search(r"week-?end", t):
        return [5, 6]
    m = re.search(r"(\w+)\s*(?:-|à|au|a)\s*(\w+)", t)
    if m and m.group(1) in _DAY_WORDS and m.group(2) in _DAY_WORDS:
        a, b = _DAY_WORDS[m.group(1)], _DAY_WORDS[m.group(2)]
        return list(range(a, b + 1)) if a <= b else list(range(a, 7)) + list(range(0, b + 1))
    return sorted({d for word, d in _DAY_WORDS.items() if re.search(rf"\b{word}s?\b", t)})


@tool
def set_routine(time: str, action: str = "briefing", days: str = "tous les jours", message: str = "") -> str:
    """Programme une routine récurrente à heure fixe (« 08:00 »). action : briefing (point du jour parlé), pc_check (contrôle santé du PC via NiTriTe, ne parle qu'en cas de problème) ou message (rappel récurrent, avec message). days : « tous les jours », « en semaine », « week-end », « lundi, jeudi »…"""
    from core.reminders import ROUTINE_ACTIONS, describe, get_reminders
    m = _TIME_RE.match((time or "").strip().lower())
    if not m or m.group(1):
        return "Heure non reconnue : donnez une heure fixe, par exemple « 08:00 » ou « 7h30 »."
    hour, minute = int(m.group(2)), int(m.group(3) or 0)
    if hour > 23 or minute > 59:
        return "Heure invalide."
    act = {"brief": "briefing", "point": "briefing", "pc": "pc_check", "sante": "pc_check",
           "santé": "pc_check", "diagnostic": "pc_check", "rappel": "message"}.get(action.strip().lower(), action.strip().lower())
    if act not in ROUTINE_ACTIONS:
        return "Action inconnue : briefing, pc_check ou message."
    if act == "message" and not message.strip():
        return "Précisez le message du rappel récurrent."
    day_list = parse_days(days)
    if not day_list:
        return "Jours non reconnus : « tous les jours », « en semaine », « week-end » ou des noms de jours."
    try:
        r = get_reminders().add_routine(f"{hour:02d}:{minute:02d}", day_list, act, message)
    except ValueError as e:
        return f"Erreur: {e}"
    return f"Routine programmée : {describe(r)}. Annulable avec cancel_reminder({r.id})."


@tool
def list_reminders() -> str:
    """Liste les minuteurs et rappels en attente."""
    from core.reminders import describe, get_reminders
    items = get_reminders().pending()
    return "\n".join(describe(r) for r in items) if items else "Aucun minuteur ni rappel en attente."


@tool
def cancel_reminder(reminder_id: int) -> str:
    """Annule un minuteur ou un rappel par son numéro."""
    from core.reminders import get_reminders
    return f"Rappel #{reminder_id} annulé." if get_reminders().cancel(int(reminder_id)) else f"Aucun rappel #{reminder_id}."


# ── Lecture web ──────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"}
    _BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def _assert_public(url: str) -> None:
    host = urllib.parse.urlparse(url).hostname or ""
    for info in socket.getaddrinfo(host, None):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("adresse locale ou privée refusée")


def html_to_text(raw: str) -> tuple[str, str]:
    parser = _TextExtractor()
    parser.feed(raw)
    text = html.unescape("".join(parser.parts))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return parser.title.strip(), text


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Chaque redirection est revérifiée : pas de rebond vers le réseau local."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _assert_public(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SafeRedirect)


@tool
def read_webpage(url: str) -> str:
    """Lit le texte principal d'une page web (article, documentation, fiche produit) pour la résumer ou y répondre."""
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    try:
        _assert_public(url)
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Language": "fr,en;q=0.8"})
        with _opener.open(req, timeout=12) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype:
                return f"Contenu non textuel ({ctype or 'inconnu'})."
            raw = resp.read(2_000_000).decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
    except Exception as e:
        return f"Lecture impossible de {url} : {e}"
    title, text = html_to_text(raw)
    if len(text) > _MAX_PAGE_CHARS:
        text = text[:_MAX_PAGE_CHARS] + "\n[… page tronquée]"
    return f"{title}\n{url}\n\n{text}" if title else f"{url}\n\n{text}"


@tool
def wikipedia_summary(topic: str, lang: str = "fr") -> str:
    """Résumé Wikipédia d'un sujet (personne, lieu, concept, événement)."""
    lang = lang if re.fullmatch(r"[a-z]{2,3}", lang or "") else "fr"
    base = f"https://{lang}.wikipedia.org"
    try:
        q = urllib.parse.urlencode({"action": "opensearch", "search": topic, "limit": 1, "format": "json"})
        with urllib.request.urlopen(urllib.request.Request(f"{base}/w/api.php?{q}", headers={"User-Agent": _UA}), timeout=10) as r:
            titles = json.loads(r.read())[1]
        if not titles:
            return f"Aucun article Wikipédia pour « {topic} »."
        page = urllib.parse.quote(titles[0].replace(" ", "_"))
        with urllib.request.urlopen(urllib.request.Request(f"{base}/api/rest_v1/page/summary/{page}", headers={"User-Agent": _UA}), timeout=10) as r:
            data = json.loads(r.read())
        return f"{data.get('title', titles[0])} — {data.get('extract', '')}\n{base}/wiki/{page}"
    except Exception as e:
        return f"Wikipédia injoignable : {e}"


# ── Médias ───────────────────────────────────────────────────────────────────

_MEDIA_KEYS = {
    "play_pause": "playpause", "pause": "playpause", "play": "playpause",
    "next": "nexttrack", "suivant": "nexttrack",
    "previous": "prevtrack", "precedent": "prevtrack", "précédent": "prevtrack",
    "stop": "stop", "mute": "volumemute", "volume_up": "volumeup", "volume_down": "volumedown",
}


# Équivalents MPRIS (Linux) des touches multimédia.
_PLAYERCTL = {"playpause": "play-pause", "nexttrack": "next", "prevtrack": "previous", "stop": "stop"}


@tool
def media_control(action: str) -> str:
    """Contrôle la lecture multimédia (Spotify, YouTube, VLC…) : play_pause, next, previous, stop, mute, volume_up, volume_down."""
    key = _MEDIA_KEYS.get(action.strip().lower())
    if not key:
        return f"Action inconnue. Possibles : {', '.join(sorted(set(_MEDIA_KEYS)))}"
    from utils.platform import IS_LINUX, run as _run, which_first
    if IS_LINUX and key in _PLAYERCTL and which_first("playerctl"):
        # MPRIS : pilote Spotify, VLC, Firefox/Chrome (YouTube)… même sous Wayland.
        r = _run(["playerctl", _PLAYERCTL[key]], timeout=5)
        if r.returncode == 0:
            return f"Commande multimédia « {action} » envoyée."
    try:
        import pyautogui  # type: ignore[import]
        pyautogui.press(key)
        return f"Touche multimédia « {action} » envoyée."
    except Exception as e:
        return f"Contrôle multimédia indisponible : {e}"


# ── Vision ───────────────────────────────────────────────────────────────────

def _capture_screen() -> tuple[bytes, str]:
    """Capture l'écran principal en JPEG réduit (1600 px max) → (octets, mime)."""
    if sys.platform == "win32":
        out = Path(tempfile.gettempdir()) / "jarvis_vision.jpg"
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$s=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
            "$b=New-Object System.Drawing.Bitmap $s.Width,$s.Height;"
            "$g=[System.Drawing.Graphics]::FromImage($b);"
            "$g.CopyFromScreen($s.Location,[System.Drawing.Point]::Empty,$s.Size);"
            "$r=[Math]::Min(1.0,1600/$s.Width);"
            "$t=New-Object System.Drawing.Bitmap ([int]($s.Width*$r)),([int]($s.Height*$r));"
            "$h=[System.Drawing.Graphics]::FromImage($t);"
            "$h.InterpolationMode='HighQualityBicubic';"
            "$h.DrawImage($b,0,0,$t.Width,$t.Height);"
            f"$t.Save('{out}',[System.Drawing.Imaging.ImageFormat]::Jpeg);"
            "$g.Dispose();$h.Dispose();$b.Dispose();$t.Dispose()"
        )
        from utils.platform import run as _run
        _run(["powershell", "-NonInteractive", "-Command", ps], timeout=20)
        data = out.read_bytes()
        out.unlink(missing_ok=True)
        return data, "image/jpeg"
    from PIL import ImageGrab  # type: ignore[import]
    import io
    img = ImageGrab.grab()
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


@tool
def analyze_screen(question: str = "") -> str:
    """Regarde l'écran de Monsieur et répond à une question sur ce qui s'affiche (erreur, fenêtre, graphique, texte…)."""
    try:
        image, mime = _capture_screen()
    except Exception as e:
        return f"Capture d'écran impossible : {e}"
    from core.vision import describe_image
    return describe_image(image, mime, question or "Décris précisément ce qui est affiché à l'écran.")


@tool
def analyze_image(path: str, question: str = "") -> str:
    """Analyse une image du disque (photo, capture, schéma) et répond à une question dessus."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path.home() / p
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}.get(p.suffix.lower())
    if not mime:
        return "Format non pris en charge (png, jpg, webp, gif)."
    if not p.exists() or p.stat().st_size > 15 * 1024 * 1024:
        return "Image introuvable ou trop lourde (15 Mo max)."
    from core.vision import describe_image
    return describe_image(p.read_bytes(), mime, question)


# ── Briefing ─────────────────────────────────────────────────────────────────

def _home_city() -> str:
    """Ville mémorisée (clé contenant « ville » ou « city »), sinon chaîne vide."""
    try:
        from core.persistent_memory import get_memory
        found = get_memory().recall("ville")
        m = re.search(r"ville[^:]*:\s*([A-Za-zÀ-ÿ' -]{2,40})", found, re.IGNORECASE)
        return m.group(1).strip() if m else ""
    except Exception:
        return ""


@tool
def briefing(city: str = "") -> str:
    """Point complet façon JARVIS : date, météo, rappels du jour, état de la machine et titres de l'actualité."""
    from core.reminders import describe, get_reminders
    from tools.info_tools import get_datetime, get_news, get_system_info, get_weather

    parts = [get_datetime()]
    town = city.strip() or _home_city()
    if town:
        parts.append(get_weather(town))
    else:
        parts.append("Météo : ville inconnue (dites « souviens-toi que j'habite à … »).")
    try:
        today_end = datetime.combine(datetime.now().date(), datetime.max.time()).timestamp()
        todays = [describe(r) for r in get_reminders().pending() if r.due <= today_end]
        parts.append("Rappels d'aujourd'hui :\n" + "\n".join(todays) if todays else "Aucun rappel aujourd'hui.")
    except Exception:
        pass
    parts.append(get_system_info())
    parts.append(_pc_alerts())
    parts.append(get_news("", 3))
    return "\n\n".join(p for p in parts if p)


def _pc_alerts() -> str:
    """Alertes santé du PC (batterie, disques, températures) si NiTriTe Agent tourne."""
    try:
        from core import nitrite
        if not nitrite.is_running():
            return ""
        from tools.pc_tools import TOPICS, _collect, alerts
        raw, _, _ = _collect(TOPICS["batterie"] + TOPICS["disques"] + TOPICS["temperatures"])
        found = alerts(raw)
        return "Santé du PC : " + (" ".join(found) if found else "rien à signaler.")
    except Exception:
        return ""
