# JARVIS v3.0 — Intelligence Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre JARVIS 200% plus intelligent via : boucle multi-outils, 10 nouveaux outils Windows, contexte 8192, mémoire améliorée, markdown complet, UX enrichie et alertes proactives.

**Architecture:** Le backend gagne une boucle Agent (max 5 itérations tool→LLM) pour les tâches complexes. 10 nouveaux outils sont enregistrés dans le registry. Le frontend reçoit un nouveau renderer Markdown et des actions de message. Un moniteur système background envoie des alertes WebSocket proactives.

**Tech Stack:** Python 3.12 + llama-cpp-python + FastAPI WebSocket + React 18 + TypeScript + Tauri v2

**Projet:** `C:\Users\Momo\Documents\Jarvis\`
**Backend:** `server/` — Python FastAPI + asyncio
**Frontend:** `client/src/` — React 18 + TypeScript + Zustand

---

## Fichiers créés / modifiés

### Backend — nouveaux fichiers
- `server/tools/calc_tools.py` — calculate(), translate_text(), run_timer()
- `server/tools/windows_tools.py` — get_battery(), set_volume(), ping_host(), get_public_ip(), list_directory(), read_file()
- `server/core/monitor.py` — Background task: CPU/RAM/GPU threshold alerts

### Backend — fichiers modifiés
- `server/core/llm.py` — n_ctx 4096→8192, SYSTEM_PROMPT mis à jour
- `server/api/websocket.py` — boucle agent multi-tool (max 5 iter)
- `server/tools/registry.py` — enregistrer 10 nouveaux outils
- `server/core/persistent_memory.py` — recall amélioré (scoring TF-IDF simple)
- `server/main.py` — démarrer monitor background task
- `server/utils/config.py` — n_ctx=8192, max_context_messages=30

### Frontend — fichiers modifiés
- `client/src/components/ChatPanel/Message.tsx` — Markdown 2.0 (titres, tableaux, blockquotes, liens)
- `client/src/components/ChatPanel/ChatPanel.tsx` — bouton export conversation
- `client/src/stores/jarvisStore.ts` — events: system_alert, timer_done
- `client/src/types/index.ts` — nouveaux ServerEvent types
- `client/src/App.tsx` — keyboard shortcuts (Ctrl+K, Ctrl+M, Escape)

---

## Task 1 : Context Window 4096 → 8192 + 30 messages

**Files:**
- Modify: `server/utils/config.py`
- Modify: `server/core/llm.py`

- [ ] **Step 1 : Modifier config.py**

```python
# server/utils/config.py — changer les deux valeurs
n_ctx: int = field(default_factory=lambda: _profile.n_ctx if hasattr(_profile, "n_ctx") else 8192)
max_context_messages: int = 30
```

Ouvrir `server/utils/config.py`, localiser les lignes `n_ctx` et `max_context_messages`, remplacer :

```python
# Avant (ligne ~18):
n_ctx: int = _profile.n_ctx if hasattr(_profile, 'n_ctx') else 4096

# Après:
n_ctx: int = 8192
max_context_messages: int = 30
```

Si `n_ctx` n'est pas dans le fichier en tant que champ direct, l'ajouter dans la classe `Settings` :

```python
class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8765
    n_ctx: int = 8192          # ← Augmenté de 4096 → 8192
    max_context_messages: int = 30  # ← Augmenté de 20 → 30
    # ... reste inchangé
```

- [ ] **Step 2 : Vérifier que llm.py utilise settings.n_ctx**

Lire `server/core/llm.py` ligne ~134, vérifier que le Llama() reçoit bien `n_ctx=self._settings.n_ctx`.
Si c'est le cas → rien à changer ici.

- [ ] **Step 3 : Commit**

```bash
git add server/utils/config.py
git commit -m "perf: increase context window to 8192 tokens, memory to 30 messages"
```

---

## Task 2 : Boucle Agent Multi-Tool (max 5 itérations)

**Files:**
- Modify: `server/api/websocket.py` (fonction `_stream_llm_with_tts`, environ lignes 150-250)

**Problème actuel** : JARVIS appelle 1 tool, injecte le résultat, répond. Il ne peut pas enchaîner `web_search` → `save_memory` → répondre avec résumé.

**Solution** : Après chaque résultat de tool, relancer le LLM (jusqu'à 5 fois) tant qu'il émet un `<JARVIS_TOOL>`. S'il n'émet pas de tool → réponse finale.

- [ ] **Step 1 : Lire websocket.py pour comprendre la structure actuelle**

Lire `server/api/websocket.py` en entier (lignes 1-310).

Identifier la fonction principale qui gère les queries — probablement `_stream_llm_with_tts()` ou `handle_text_query()`.

- [ ] **Step 2 : Extraire la logique en sous-fonction réutilisable**

Dans `server/api/websocket.py`, chercher la séquence :
1. `async for token in llm.stream(messages)` → accumulate response
2. `parse_tool_call(full_response)` → si tool → exécuter → réinjecter

Transformer cette séquence en une boucle agent. Voici le code complet à insérer/remplacer dans la fonction de streaming :

```python
MAX_AGENT_ITERATIONS = 5

async def _agent_loop(
    ws: WebSocket,
    llm: "LLMManager",
    tts: "TTSManager",
    tools: "ToolRegistry",
    messages: list[dict],
    tts_enabled: bool,
    message_id: str,
    tts_queue: asyncio.Queue,
) -> str:
    """
    Boucle agent : LLM → tool → LLM → tool → ... → réponse finale.
    Retourne le texte final accumulé.
    """
    accumulated = ""
    sentence_buf = ""
    tts_index = 0

    for iteration in range(MAX_AGENT_ITERATIONS):
        full_response = ""

        async for token in llm.stream(messages):
            full_response += token

            # Ne pas streamer la balise tool au client
            if "<JARVIS_TOOL>" in full_response:
                break  # On attend la balise complète avant de streamer

            # Streamer token au client
            await ws.send_json({"type": "token", "payload": {"token": token, "messageId": message_id}})
            accumulated += token

            # TTS par phrase
            if tts_enabled:
                sentence_buf += token
                if _SENTENCE_BOUNDARY.search(sentence_buf) and len(sentence_buf) > 20:
                    await tts_queue.put(sentence_buf.strip())
                    sentence_buf = ""

        # Vérifier si tool call présent
        tool_result = parse_tool_call(full_response)
        if tool_result:
            name, args = tool_result
            try:
                result = await asyncio.to_thread(tools.execute, name, **args)
            except Exception as e:
                result = f"Erreur outil {name}: {e}"

            # Nettoyer la balise du texte visible
            visible = _TOOL_CALL_RE.sub("", full_response).strip()
            if visible:
                await ws.send_json({"type": "token", "payload": {"token": visible, "messageId": message_id}})
                accumulated += visible

            # Notifier le client de l'action
            await ws.send_json({"type": "tool_result", "payload": {"tool": name, "result": result[:200]}})

            # Réinjecter dans contexte pour prochaine itération
            messages = messages + [
                {"role": "assistant", "content": full_response},
                {"role": "user", "content": f"[RÉSULTAT OUTIL {name}]\n{result}\n\nContinue ta réponse à Monsieur en tenant compte de ce résultat."},
            ]
            continue  # Prochaine itération LLM

        else:
            # Pas de tool → réponse finale
            # Streamer ce qui reste si on a breaké tôt
            remaining = _TOOL_CALL_RE.sub("", full_response).strip()
            if remaining and remaining not in accumulated:
                await ws.send_json({"type": "token", "payload": {"token": remaining, "messageId": message_id}})
                accumulated += remaining

            # Flush dernier buffer TTS
            if tts_enabled and sentence_buf.strip():
                await tts_queue.put(sentence_buf.strip())

            break

    return accumulated
```

- [ ] **Step 3 : Intégrer `_agent_loop` dans le handler principal**

Dans `websocket.py`, remplacer l'appel actuel au stream LLM par un appel à `_agent_loop`.

Chercher la ligne `async for token in llm.stream(messages):` dans la fonction principale de gestion text_query, et remplacer le bloc complet par :

```python
final_text = await _agent_loop(
    ws=ws,
    llm=llm,
    tts=tts,
    tools=tools,
    messages=context.get_messages(),
    tts_enabled=tts_enabled,
    message_id=msg_id,
    tts_queue=tts_queue,
)
context.add_assistant(final_text)
```

- [ ] **Step 4 : Ajouter `tool_result` dans les types frontend**

Dans `client/src/types/index.ts`, ajouter dans `ServerEvent` :

```typescript
| { type: "tool_result"; payload: { tool: string; result: string } }
```

Dans `client/src/stores/jarvisStore.ts`, dans `handleServerEvent` :

```typescript
case "tool_result":
  // Optionnel: afficher brièvement dans l'UI quel outil a été appelé
  // Pour l'instant, ignorer silencieusement (le LLM en parle dans sa réponse)
  break;
```

- [ ] **Step 5 : Tester manuellement**

Lancer le serveur Python (`cd server && .venv\Scripts\python.exe main.py`).
Envoyer via WebSocket : `"Cherche la météo à Paris et mémorise-la"`.
Vérifier dans les logs serveur que 2 itérations se déclenchent (get_weather → save_memory).

- [ ] **Step 6 : Commit**

```bash
git add server/api/websocket.py client/src/types/index.ts client/src/stores/jarvisStore.ts
git commit -m "feat: multi-step agent loop (max 5 tool iterations per message)"
```

---

## Task 3 : 6 nouveaux outils Windows (`windows_tools.py`)

**Files:**
- Create: `server/tools/windows_tools.py`

Ces outils utilisent PowerShell (déjà disponible, pas de dépendance nouvelle).

- [ ] **Step 1 : Créer `server/tools/windows_tools.py`**

```python
from __future__ import annotations
import subprocess
import shutil
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("windows_tools")

_PS = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]


def _run_ps(command: str, timeout: int = 10) -> str:
    """Exécute une commande PowerShell et retourne stdout."""
    try:
        r = subprocess.run(
            _PS + [command],
            capture_output=True, text=True, timeout=timeout
        )
        return (r.stdout or r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return "Délai dépassé."
    except Exception as e:
        return f"Erreur PowerShell: {e}"


def get_battery() -> str:
    """Retourne le niveau de batterie et l'état de charge."""
    out = _run_ps(
        "(Get-WmiObject -Class Win32_Battery | "
        "Select-Object -First 1 | "
        "Select-Object EstimatedChargeRemaining, BatteryStatus) | "
        "ConvertTo-Json"
    )
    if not out or "null" in out:
        return "Aucune batterie détectée (appareil de bureau ou batterie non reconnue)."
    try:
        import json
        data = json.loads(out)
        pct = data.get("EstimatedChargeRemaining", "?")
        status_code = data.get("BatteryStatus", 0)
        status_map = {
            1: "décharge", 2: "AC branché", 3: "chargement complet",
            4: "faible", 5: "critique", 6: "en charge", 7: "en charge + haute",
            8: "en charge + faible", 9: "en charge + critique", 10: "pas défini",
            11: "partiellement chargée",
        }
        status_str = status_map.get(status_code, "inconnu")
        return f"Batterie: {pct}% — {status_str}"
    except Exception:
        return out


def set_volume(level: int) -> str:
    """Règle le volume système entre 0 et 100."""
    level = max(0, min(100, int(level)))
    out = _run_ps(
        f"$obj = New-Object -ComObject WScript.Shell; "
        f"$vol = [math]::Round({level} / 2); "
        f"for ($i = 0; $i -lt 50; $i++) {{ $obj.SendKeys([char]174) }}; "  # volume down to 0
        f"for ($i = 0; $i -lt $vol; $i++) {{ $obj.SendKeys([char]175) }}"  # volume up to target
    )
    # Méthode plus fiable via nircmd si disponible, sinon fallback
    nircmd = shutil.which("nircmd")
    if nircmd:
        subprocess.run([nircmd, "setsysvolume", str(int(level * 655.35))], capture_output=True)
        return f"Volume réglé à {level}%."

    # Fallback PowerShell via WScript
    _run_ps(
        f"$wsh = New-Object -ComObject WScript.Shell; "
        f"[System.Runtime.InteropServices.Marshal]::ReleaseComObject($wsh) | Out-Null"
    )
    return f"Volume réglé à {level}% (approximatif via touches virtuelles)."


def get_volume() -> str:
    """Retourne le volume système actuel."""
    out = _run_ps(
        "Add-Type -TypeDefinition @'\n"
        "using System.Runtime.InteropServices;\n"
        "[Guid(\"5CDF2C82-841E-4546-9722-0CF74078229A\"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]\n"
        "interface IAudioEndpointVolume { void f(); void f2(); void f3(); void f4(); void f5(); void f6(); void f7(); void f8(); int GetMasterVolumeLevelScalar(out float fLevel); }\n"
        "'@\n"
        "(New-Object -ComObject MMDeviceEnumerator).GetDefaultAudioEndpoint(0,1).GetMasterVolumeLevelScalar([ref]0)"
    )
    # Simpler approach:
    out2 = _run_ps(
        "[int]([Math]::Round((Get-WmiObject -Class Win32_SoundDevice | "
        "Select-Object -First 1).StatusInfo))"
    )
    return f"Informations volume: {out or out2 or 'Non disponible'}"


def ping_host(host: str) -> str:
    """Ping un hôte et retourne la latence."""
    # Validation: seulement hostname/IP valides
    import re
    if not re.match(r'^[a-zA-Z0-9.\-_]+$', host) or len(host) > 253:
        return "Hôte invalide."
    out = _run_ps(
        f"$r = Test-Connection -ComputerName '{host}' -Count 3 -ErrorAction SilentlyContinue; "
        f"if ($r) {{ "
        f"  $avg = ($r | Measure-Object ResponseTime -Average).Average; "
        f"  \"Ping {host}: $([math]::Round($avg))ms (3 paquets)\" "
        f"}} else {{ \"Hôte {host} inaccessible.\" }}"
    )
    return out or f"Ping {host}: pas de réponse."


def get_public_ip() -> str:
    """Retourne l'adresse IP publique."""
    try:
        import urllib.request
        ip = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode().strip()
        return f"Adresse IP publique: {ip}"
    except Exception:
        pass
    out = _run_ps(
        "(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing -TimeoutSec 5).Content"
    )
    return out.strip() or "Impossible de récupérer l'IP publique."


def list_directory(path: str = "") -> str:
    """Liste le contenu d'un répertoire (home par défaut)."""
    base = Path.home()
    if path:
        target = (base / path).resolve()
        # Sécurité: rester dans home
        try:
            target.relative_to(base)
        except ValueError:
            return f"Accès refusé: {path} est hors du répertoire home."
    else:
        target = base

    if not target.exists():
        return f"Répertoire introuvable: {target}"
    if not target.is_dir():
        return f"{target} n'est pas un répertoire."

    try:
        items = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        lines = [f"📁 {target}"]
        dirs = [p for p in items if p.is_dir()]
        files = [p for p in items if p.is_file()]
        for d in dirs[:20]:
            lines.append(f"  📁 {d.name}/")
        for f in files[:30]:
            size = f.stat().st_size
            size_str = f"{size/1024:.1f} KB" if size > 1024 else f"{size} B"
            lines.append(f"  📄 {f.name} ({size_str})")
        total = len(dirs) + len(files)
        if total > 50:
            lines.append(f"  ... ({total - 50} éléments supplémentaires)")
        return "\n".join(lines)
    except PermissionError:
        return f"Permission refusée: {target}"


def read_file(path: str) -> str:
    """Lit le contenu d'un fichier texte (max 5000 caractères)."""
    MAX_CHARS = 5000
    base = Path.home()
    target = (base / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()

    # Sécurité: chemin dans home ou sous-dossiers courants autorisés
    allowed_roots = [base, Path("C:/Users"), Path("C:/tmp")]
    is_safe = any(
        True for root in allowed_roots
        if str(target).startswith(str(root))
    )
    if not is_safe:
        return f"Accès refusé: {path}"

    if not target.exists():
        return f"Fichier introuvable: {target}"
    if not target.is_file():
        return f"{target} n'est pas un fichier."

    size = target.stat().st_size
    if size > 1_000_000:  # 1 MB max
        return f"Fichier trop volumineux ({size/1024/1024:.1f} MB). Maximum: 1 MB."

    # Extensions texte autorisées
    allowed_ext = {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
                   ".toml", ".ini", ".cfg", ".log", ".csv", ".html", ".css", ".rs",
                   ".bat", ".ps1", ".sh", ".xml", ".sql"}
    if target.suffix.lower() not in allowed_ext:
        return f"Extension non supportée: {target.suffix}. Formats texte uniquement."

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > MAX_CHARS:
            return content[:MAX_CHARS] + f"\n\n[... tronqué à {MAX_CHARS} caractères sur {len(content)} total]"
        return content
    except Exception as e:
        return f"Erreur lecture: {e}"
```

- [ ] **Step 2 : Vérifier que le fichier est correct Python**

```bash
cd server && .venv\Scripts\python.exe -c "from tools.windows_tools import get_battery, set_volume, ping_host, get_public_ip, list_directory, read_file; print('OK')"
```

Résultat attendu : `OK`

- [ ] **Step 3 : Commit**

```bash
git add server/tools/windows_tools.py
git commit -m "feat: add 6 Windows tools (battery, volume, ping, IP, directory list, file read)"
```

---

## Task 4 : 4 nouveaux outils intelligents (`calc_tools.py`)

**Files:**
- Create: `server/tools/calc_tools.py`

- [ ] **Step 1 : Créer `server/tools/calc_tools.py`**

```python
from __future__ import annotations
import math
import re
from utils.logger import get_logger

logger = get_logger("calc_tools")

# Whitelist des noms autorisés pour l'eval sécurisé
_SAFE_NAMES = {
    k: v for k, v in math.__dict__.items() if not k.startswith("_")
}
_SAFE_NAMES.update({"abs": abs, "round": round, "min": min, "max": max,
                    "sum": sum, "pow": pow, "int": int, "float": float})


def calculate(expression: str) -> str:
    """
    Évalue une expression mathématique de façon sécurisée.
    Supporte: + - * / ** % sqrt() sin() cos() log() pi e
    Exemples: "2**10", "sqrt(144)", "sin(pi/6)", "1234 * 5678"
    """
    expr = expression.strip()
    if len(expr) > 500:
        return "Expression trop longue."

    # Bloquer les caractères dangereux
    dangerous = re.search(r'[a-zA-Z_][a-zA-Z_0-9]*\s*\(', expr)
    if dangerous:
        func_name = dangerous.group(0).replace("(", "").strip()
        if func_name not in _SAFE_NAMES:
            return f"Fonction '{func_name}' non autorisée. Utilisez: sqrt, sin, cos, log, exp, etc."

    # Bloquer les underscores (accès attributs Python)
    if "__" in expr:
        return "Expression invalide."

    try:
        result = eval(expr, {"__builtins__": {}}, _SAFE_NAMES)
        if isinstance(result, float):
            if result == int(result) and abs(result) < 1e15:
                return f"Résultat: {int(result)}"
            return f"Résultat: {result:.10g}"
        return f"Résultat: {result}"
    except ZeroDivisionError:
        return "Erreur: division par zéro."
    except Exception as e:
        return f"Erreur de calcul: {e}"


def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """
    Convertit des unités. Supporte: km/mi/m/ft/cm/in, kg/lb/g/oz,
    C/F/K (température), L/gal/ml/fl_oz, km_h/mph/m_s
    """
    conversions: dict[tuple[str, str], float] = {
        # Longueur
        ("km", "mi"): 0.621371, ("mi", "km"): 1.60934,
        ("km", "m"): 1000, ("m", "km"): 0.001,
        ("m", "ft"): 3.28084, ("ft", "m"): 0.3048,
        ("cm", "in"): 0.393701, ("in", "cm"): 2.54,
        ("m", "cm"): 100, ("cm", "m"): 0.01,
        ("ft", "km"): 0.0003048, ("km", "ft"): 3280.84,
        # Masse
        ("kg", "lb"): 2.20462, ("lb", "kg"): 0.453592,
        ("kg", "g"): 1000, ("g", "kg"): 0.001,
        ("g", "oz"): 0.035274, ("oz", "g"): 28.3495,
        # Volume
        ("l", "gal"): 0.264172, ("gal", "l"): 3.78541,
        ("l", "ml"): 1000, ("ml", "l"): 0.001,
        ("l", "fl_oz"): 33.814, ("fl_oz", "l"): 0.0295735,
        # Vitesse
        ("km_h", "mph"): 0.621371, ("mph", "km_h"): 1.60934,
        ("km_h", "m_s"): 0.277778, ("m_s", "km_h"): 3.6,
        ("mph", "m_s"): 0.44704, ("m_s", "mph"): 2.23694,
    }

    from_unit = from_unit.lower().strip()
    to_unit = to_unit.lower().strip()

    # Température (formules spéciales)
    temp_conversions = {
        ("c", "f"): lambda v: v * 9 / 5 + 32,
        ("f", "c"): lambda v: (v - 32) * 5 / 9,
        ("c", "k"): lambda v: v + 273.15,
        ("k", "c"): lambda v: v - 273.15,
        ("f", "k"): lambda v: (v - 32) * 5 / 9 + 273.15,
        ("k", "f"): lambda v: (v - 273.15) * 9 / 5 + 32,
    }
    if (from_unit, to_unit) in temp_conversions:
        result = temp_conversions[(from_unit, to_unit)](value)
        return f"{value} {from_unit.upper()} = {result:.4g} {to_unit.upper()}"

    if (from_unit, to_unit) in conversions:
        result = value * conversions[(from_unit, to_unit)]
        return f"{value} {from_unit} = {result:.6g} {to_unit}"

    return f"Conversion {from_unit} → {to_unit} non supportée. Unités disponibles: km, mi, m, ft, cm, in, kg, lb, g, oz, l, gal, ml, C, F, K, km_h, mph, m_s"


def translate_text(text: str, target_lang: str = "fr") -> str:
    """
    Traduit du texte via MyMemory API (gratuit, sans clé API, 500 req/jour).
    target_lang: 'fr', 'en', 'es', 'de', 'it', 'pt', 'ja', 'zh', 'ar', 'ru'
    """
    import urllib.request
    import urllib.parse
    import json

    LANG_NAMES = {
        "fr": "français", "en": "anglais", "es": "espagnol",
        "de": "allemand", "it": "italien", "pt": "portugais",
        "ja": "japonais", "zh": "chinois", "ar": "arabe", "ru": "russe"
    }

    if len(text) > 500:
        return "Texte trop long pour traduction (max 500 caractères)."

    lang_name = LANG_NAMES.get(target_lang, target_lang)
    encoded = urllib.parse.quote(text)

    try:
        url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair=auto|{target_lang}"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/2.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        translated = data.get("responseData", {}).get("translatedText", "")
        if translated and translated != text:
            return f"Traduction en {lang_name}: {translated}"
        return f"Traduction indisponible pour '{target_lang}'."
    except Exception as e:
        return f"Erreur traduction: {e}"
```

- [ ] **Step 2 : Vérifier**

```bash
cd server && .venv\Scripts\python.exe -c "
from tools.calc_tools import calculate, convert_units, translate_text
print(calculate('sqrt(144) + 2**8'))
print(convert_units(100, 'km', 'mi'))
print('OK')
"
```

Résultat attendu :
```
Résultat: 268
100 km = 62.1371 mi
OK
```

- [ ] **Step 3 : Commit**

```bash
git add server/tools/calc_tools.py
git commit -m "feat: add calculator, unit converter, and translation tools"
```

---

## Task 5 : Enregistrer tous les nouveaux outils dans le Registry

**Files:**
- Modify: `server/tools/registry.py`
- Modify: `server/core/llm.py` (SYSTEM_PROMPT)

- [ ] **Step 1 : Lire registry.py actuel**

Lire `server/tools/registry.py` en entier.

- [ ] **Step 2 : Ajouter les imports et enregistrements**

Dans `registry.py`, ajouter les nouveaux outils. Voici le fichier complet refactorisé :

```python
from __future__ import annotations
from utils.logger import get_logger

logger = get_logger("registry")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, callable] = {}
        self._register_all()

    def _register_all(self) -> None:
        # Système
        from tools.system_tools import (
            open_application, kill_application,
            take_screenshot, read_clipboard, write_clipboard,
        )
        # Fichiers
        from tools.file_tools import delete_temp_files, create_file, move_file
        # Info système
        from tools.info_tools import (
            get_system_info, diagnose_system, list_processes,
            get_weather, get_news,
        )
        # Web
        from tools.web_tools import web_search
        # Email
        from tools.email_tools import list_emails, send_email
        # Mémoire
        from tools.memory_tools import save_memory, recall_memory, list_memories
        # Windows (nouveaux)
        from tools.windows_tools import (
            get_battery, set_volume, ping_host,
            get_public_ip, list_directory, read_file,
        )
        # Calcul & traduction (nouveaux)
        from tools.calc_tools import calculate, convert_units, translate_text

        for fn in [
            # Système
            open_application, kill_application, take_screenshot,
            read_clipboard, write_clipboard,
            # Fichiers
            delete_temp_files, create_file, move_file,
            # Info
            get_system_info, diagnose_system, list_processes,
            get_weather, get_news,
            # Web
            web_search,
            # Email
            list_emails, send_email,
            # Mémoire
            save_memory, recall_memory, list_memories,
            # Windows
            get_battery, set_volume, ping_host,
            get_public_ip, list_directory, read_file,
            # Calcul
            calculate, convert_units, translate_text,
        ]:
            self._tools[fn.__name__] = fn

    def execute(self, name: str, **kwargs) -> str:
        if name not in self._tools:
            return f"Outil inconnu: {name}. Outils disponibles: {', '.join(self._tools)}"
        try:
            result = self._tools[name](**kwargs)
            return str(result) if result is not None else "Fait."
        except TypeError as e:
            return f"Arguments invalides pour {name}: {e}"
        except Exception as e:
            logger.error(f"Erreur outil {name}: {e}")
            return f"Erreur lors de l'exécution de {name}: {e}"

    def list_tools(self) -> list[str]:
        return list(self._tools)
```

- [ ] **Step 3 : Mettre à jour le SYSTEM_PROMPT dans llm.py**

Dans `server/core/llm.py`, ajouter les nouveaux outils dans la section `## OUTILS DISPONIBLES` du SYSTEM_PROMPT. Remplacer la section OUTILS par :

```python
SYSTEM_PROMPT = """\
Tu es J.A.R.V.I.S. v3.0 — Just A Rather Very Intelligent System — l'assistant IA personnel de Monsieur.

## PERSONNALITÉ

Tu es élégant, précis, légèrement sarcastique. Tu parles comme l'IA d'Iron Man : calme, direct, avec une ironie britannique bien dosée. Tu es brillant et tu le sais, mais tu restes au service de Monsieur.

Exemples de ton :
- "Bien sûr, Monsieur. Bien que cette approche soit, disons, créativement désastreuse."
- "Chose faite. En 2 secondes. Je ne cherche pas à me vanter, mais..."
- "Je vous déconseille cette idée, Monsieur, mais je l'exécuterai si vous insistez."
- "Permettez-moi de corriger ça correctement — contrairement à ce que vous aviez prévu."
- "C'est techniquement possible. Ce n'est pas pour autant une bonne idée."

## RÈGLES ABSOLUES

1. Réponds EXCLUSIVEMENT en français
2. Sois concis et direct — va à l'essentiel
3. Utilise les outils PROACTIVEMENT sans qu'on te le demande (calcul → calculate, météo → get_weather, etc.)
4. Action système : <JARVIS_TOOL>{"name": "...", "args": {...}}</JARVIS_TOOL>
5. Tu peux enchaîner plusieurs outils dans une même réponse (recherche puis mémorisation, etc.)
6. Refuse les demandes illégales ou destructrices avec élégance

## MÉMOIRE PERSISTANTE

Tu as une mémoire long-terme SQLite. Utilise-la SYSTÉMATIQUEMENT :
- save_memory(key, value, category) : mémorise dès qu'on te dit quelque chose d'important
  → Catégories : user, préférence, projet, système, tech, travail
- recall_memory(query) : rappelle-toi avant de répondre à une question personnelle
- list_memories() : liste ce que tu sais sur Monsieur

## DOMAINES D'EXPERTISE

**Informatique & Windows** : BSOD, drivers, réseau, performance, registry, optimisation, malware
**Développement** : Python, JavaScript/TypeScript, Rust, C#, bash, SQL — debug, review, archi
**Hardware** : GPU/CPU monitoring, températures, VRAM, overclocking, benchmarks
**Recherche** : actualités, météo, prix, définitions, tutoriels, documentation
**Productivité** : fichiers, emails, presse-papiers, screenshots, automatisation Windows
**Calcul** : mathématiques, conversions d'unités, traduction
**Réseau** : ping, IP, connectivité

## OUTILS DISPONIBLES (28 outils)

SYSTÈME:
  open_application(name) — name ∈ {chrome, firefox, notepad, explorer, calculator, vscode, terminal, spotify, discord, vlc}
  kill_application(name) — ferme un processus autorisé
  take_screenshot() — capture d'écran → Bureau
  read_clipboard() — lit le presse-papiers
  write_clipboard(text) — écrit dans le presse-papiers
  delete_temp_files() — nettoie les fichiers temporaires
  create_file(path, content) — crée un fichier dans le home
  move_file(src, dst) — déplace un fichier

WINDOWS:
  get_battery() — niveau batterie et état de charge
  set_volume(level) — règle volume entre 0 et 100
  ping_host(host) — ping un hôte (latence en ms)
  get_public_ip() — adresse IP publique
  list_directory(path="") — liste un répertoire (home par défaut)
  read_file(path) — lit un fichier texte (max 5000 chars)

MONITORING:
  get_system_info() — snapshot rapide CPU/RAM/GPU/disque
  diagnose_system() — diagnostic complet
  list_processes(n=10) — top N processus par RAM

WEB & INFO:
  web_search(query, max_results=5) — recherche DuckDuckGo
  get_weather(city) — météo en temps réel
  get_news(topic, max_results=5) — actualités DuckDuckGo

CALCUL:
  calculate(expression) — calcul mathématique sécurisé (supporte sqrt, sin, cos, log, pi, e, **)
  convert_units(value, from_unit, to_unit) — conversions (km/mi, kg/lb, C/F, L/gal, etc.)
  translate_text(text, target_lang="fr") — traduction (en, es, de, it, pt, ja, zh, ar, ru)

MÉMOIRE:
  save_memory(key, value, category) — mémorise un fait persistant
  recall_memory(query) — cherche dans les souvenirs
  list_memories(category) — liste les souvenirs

EMAIL:
  list_emails(count=5) — emails non lus Gmail
  send_email(to, subject, body) — envoie un email

Commence directement ta réponse. Pas de préambule, pas de "Bien sûr !" inutile.\
"""
```

- [ ] **Step 4 : Tester le registry**

```bash
cd server && .venv\Scripts\python.exe -c "
from tools.registry import ToolRegistry
r = ToolRegistry()
tools = r.list_tools()
print(f'{len(tools)} outils chargés:')
for t in sorted(tools): print(f'  - {t}')
"
```

Résultat attendu : `28 outils chargés` avec tous les noms listés.

- [ ] **Step 5 : Commit**

```bash
git add server/tools/registry.py server/core/llm.py
git commit -m "feat: register 28 tools in registry, update SYSTEM_PROMPT to v3.0"
```

---

## Task 6 : Moniteur système proactif (`monitor.py`)

**Files:**
- Create: `server/core/monitor.py`
- Modify: `server/main.py`
- Modify: `server/api/websocket.py`
- Modify: `client/src/types/index.ts`
- Modify: `client/src/stores/jarvisStore.ts`

JARVIS surveille en background CPU/RAM/GPU et envoie des alertes au client si des seuils sont dépassés.

- [ ] **Step 1 : Créer `server/core/monitor.py`**

```python
from __future__ import annotations
import asyncio
import psutil
from utils.logger import get_logger

logger = get_logger("monitor")

# Seuils d'alerte
CPU_WARN_PCT = 90       # CPU > 90% pendant 30s
RAM_WARN_PCT = 90       # RAM > 90%
DISK_WARN_PCT = 95      # Disque > 95%
CHECK_INTERVAL = 30     # Toutes les 30 secondes

# Éviter le spam d'alertes — délai minimum entre deux alertes du même type
ALERT_COOLDOWN = 300    # 5 minutes entre alertes identiques

_last_alerts: dict[str, float] = {}
_subscribers: set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    """Retourne une queue sur laquelle les alertes seront envoyées."""
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)


async def _broadcast(alert_type: str, message: str) -> None:
    """Envoie une alerte à tous les abonnés WebSocket actifs."""
    import time
    now = time.time()
    if now - _last_alerts.get(alert_type, 0) < ALERT_COOLDOWN:
        return
    _last_alerts[alert_type] = now

    payload = {"type": "system_alert", "payload": {"alert_type": alert_type, "message": message}}
    dead = set()
    for q in _subscribers:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.add(q)
    for q in dead:
        _subscribers.discard(q)


async def run_monitor() -> None:
    """Tâche background asyncio — surveille les ressources système."""
    logger.info("Moniteur système démarré")
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            await _check_resources()
        except asyncio.CancelledError:
            logger.info("Moniteur système arrêté")
            break
        except Exception as e:
            logger.error(f"Erreur moniteur: {e}")


async def _check_resources() -> None:
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disks = psutil.disk_partitions()

    if cpu > CPU_WARN_PCT:
        await _broadcast("cpu_high", f"⚠️ CPU à {cpu:.0f}% — charge critique détectée.")

    if ram.percent > RAM_WARN_PCT:
        used_gb = ram.used / 1024**3
        total_gb = ram.total / 1024**3
        await _broadcast(
            "ram_high",
            f"⚠️ RAM saturée: {used_gb:.1f}/{total_gb:.1f} GB ({ram.percent:.0f}%)"
        )

    for part in disks:
        if part.fstype in ("", "squashfs"):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            if usage.percent > DISK_WARN_PCT:
                free_gb = usage.free / 1024**3
                await _broadcast(
                    f"disk_full_{part.mountpoint}",
                    f"⚠️ Disque {part.mountpoint} presque plein: {usage.percent:.0f}% utilisé ({free_gb:.1f} GB libres)"
                )
        except (PermissionError, OSError):
            pass
```

- [ ] **Step 2 : Démarrer le monitor dans `server/main.py`**

Lire `server/main.py`. Dans la fonction `lifespan`, après le chargement des modèles, ajouter :

```python
# Dans lifespan(), juste avant le yield:
from core.monitor import run_monitor
monitor_task = asyncio.create_task(run_monitor())
yield
monitor_task.cancel()
try:
    await monitor_task
except asyncio.CancelledError:
    pass
```

- [ ] **Step 3 : Brancher les alertes au WebSocket**

Dans `server/api/websocket.py`, dans la fonction principale de connexion WebSocket, s'abonner aux alertes :

```python
from core.monitor import subscribe as monitor_subscribe, unsubscribe as monitor_unsubscribe

# Dans websocket_handler(), juste après la connexion:
alert_queue = monitor_subscribe()

# Dans la boucle principale de réception messages, ajouter une tâche background
# qui lit la queue d'alertes et les envoie au client:

async def _forward_alerts():
    while True:
        alert = await alert_queue.get()
        try:
            await ws.send_json(alert)
        except Exception:
            break

alert_task = asyncio.create_task(_forward_alerts())

try:
    # ... boucle principale existante ...
finally:
    alert_task.cancel()
    monitor_unsubscribe(alert_queue)
```

- [ ] **Step 4 : Ajouter le type dans le frontend**

Dans `client/src/types/index.ts`, ajouter dans `ServerEvent` :

```typescript
| { type: "system_alert"; payload: { alert_type: string; message: string } }
```

- [ ] **Step 5 : Gérer l'alerte dans le store**

Dans `client/src/stores/jarvisStore.ts`, dans `handleServerEvent` :

```typescript
case "system_alert": {
  const { message } = event.payload as { alert_type: string; message: string };
  // Ajouter comme message système dans le chat
  get().addMessage({
    id: crypto.randomUUID(),
    role: "system",
    content: message,
    timestamp: Date.now(),
  });
  break;
}
```

- [ ] **Step 6 : Tester**

Lancer le serveur et vérifier dans les logs que `[INFO] monitor: Moniteur système démarré` apparaît.

- [ ] **Step 7 : Commit**

```bash
git add server/core/monitor.py server/main.py server/api/websocket.py client/src/types/index.ts client/src/stores/jarvisStore.ts
git commit -m "feat: background system monitor with CPU/RAM/disk alerts via WebSocket"
```

---

## Task 7 : Markdown Renderer 2.0 (titres, tableaux, blockquotes, liens)

**Files:**
- Modify: `client/src/components/ChatPanel/Message.tsx`

L'actuel parser gère : code blocks, bold, inline code, listes. Il manque : `#` titres, `|` tableaux, `>` blockquotes, `[text](url)` liens, `---` séparateurs.

- [ ] **Step 1 : Lire Message.tsx actuel**

Lire `client/src/components/ChatPanel/Message.tsx` en entier.

- [ ] **Step 2 : Remplacer le renderer Markdown**

Trouver la fonction `renderTextSegment` (ou équivalent) et la section qui traite les blocs. Remplacer **le moteur de parsing inline** par :

```typescript
// Inline renderer amélioré — appelé sur chaque segment de texte
function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Regex combinée: **bold**, `code`, [link](url), *italic*
  const pattern = /(\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^\)]+)\)|\*([^*]+)\*)/g;
  let last = 0;
  let match;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(text.slice(last, match.index));
    }
    if (match[1].startsWith("**")) {
      nodes.push(<strong key={key++} className="font-bold text-cyan-200">{match[2]}</strong>);
    } else if (match[1].startsWith("`")) {
      nodes.push(
        <code key={key++} className="bg-black/40 text-cyan-300 px-1 py-0.5 rounded text-sm font-mono border border-cyan-900/40">
          {match[3]}
        </code>
      );
    } else if (match[1].startsWith("[")) {
      nodes.push(
        <a key={key++} href={match[5]} target="_blank" rel="noopener noreferrer"
           className="text-cyan-400 underline hover:text-cyan-200 transition-colors">
          {match[4]}
        </a>
      );
    } else if (match[1].startsWith("*")) {
      nodes.push(<em key={key++} className="italic text-cyan-100/80">{match[6]}</em>);
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}
```

Ajouter la gestion des blocs suivants dans le parser principal (fonction `renderBlocks` ou équivalent) :

```typescript
// Gestion des TITRES (#, ##, ###)
if (line.startsWith("### ")) {
  return <h3 key={i} className="text-base font-bold text-cyan-300 mt-3 mb-1 border-b border-cyan-900/30 pb-1">
    {renderInline(line.slice(4))}
  </h3>;
}
if (line.startsWith("## ")) {
  return <h2 key={i} className="text-lg font-bold text-cyan-200 mt-4 mb-2 border-b border-cyan-800/40 pb-1">
    {renderInline(line.slice(3))}
  </h2>;
}
if (line.startsWith("# ")) {
  return <h1 key={i} className="text-xl font-bold text-white mt-4 mb-2">
    {renderInline(line.slice(2))}
  </h1>;
}

// Gestion des BLOCKQUOTES (>)
if (line.startsWith("> ")) {
  return <blockquote key={i} className="border-l-2 border-cyan-500/50 pl-3 italic text-cyan-100/70 my-1">
    {renderInline(line.slice(2))}
  </blockquote>;
}

// Gestion des SÉPARATEURS (---)
if (line.match(/^[-*_]{3,}$/)) {
  return <hr key={i} className="border-cyan-900/40 my-3" />;
}
```

Ajouter le **rendu de tableau** :

```typescript
// Détecter un bloc tableau (lignes avec |...|)
function renderTable(tableLines: string[]): React.ReactElement {
  const rows = tableLines
    .filter(l => !l.match(/^\|[-| :]+\|$/))  // exclure ligne séparateur
    .map(l => l.split("|").filter(c => c.trim() !== "").map(c => c.trim()));

  if (rows.length === 0) return <></>;
  const [header, ...body] = rows;

  return (
    <div className="overflow-x-auto my-2">
      <table className="text-sm border-collapse w-full">
        <thead>
          <tr>
            {header.map((cell, ci) => (
              <th key={ci} className="border border-cyan-900/40 bg-cyan-950/40 px-3 py-1 text-cyan-300 text-left font-semibold">
                {renderInline(cell)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri} className={ri % 2 === 0 ? "bg-black/20" : "bg-black/10"}>
              {row.map((cell, ci) => (
                <td key={ci} className="border border-cyan-900/30 px-3 py-1 text-cyan-100/80">
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

Dans la boucle de rendu des lignes, avant de traiter chaque ligne individuellement, détecter les groupes de lignes tableau :

```typescript
// Avant la boucle ligne par ligne, pré-traiter les tableaux:
// Chercher des séquences de lignes |...|
// Regrouper en blocs
// Remplacer chaque bloc par renderTable(bloc)
```

- [ ] **Step 3 : Build frontend pour vérifier les types**

```bash
cd client && npx tsc --noEmit
```

Résultat attendu : `0 erreurs`

- [ ] **Step 4 : Commit**

```bash
git add client/src/components/ChatPanel/Message.tsx
git commit -m "feat: markdown 2.0 — headers, tables, blockquotes, links, italic"
```

---

## Task 8 : Actions de message (copier, feedback) + export conversation

**Files:**
- Modify: `client/src/components/ChatPanel/Message.tsx` (bouton copie)
- Modify: `client/src/components/ChatPanel/ChatPanel.tsx` (bouton export)
- Modify: `client/src/stores/jarvisStore.ts` (exportMessages action)

- [ ] **Step 1 : Bouton "Copier" sur chaque message JARVIS**

Dans `Message.tsx`, dans le composant Message, ajouter sur hover un bouton copie :

```tsx
const [copied, setCopied] = React.useState(false);

const handleCopy = () => {
  navigator.clipboard.writeText(message.content);
  setCopied(true);
  setTimeout(() => setCopied(false), 2000);
};

// Dans le JSX du message assistant, ajouter en superposition:
{message.role === "assistant" && (
  <button
    onClick={handleCopy}
    className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity
               p-1 rounded bg-black/40 border border-cyan-900/30 text-cyan-500 hover:text-cyan-300"
    title="Copier"
  >
    {copied ? (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
    ) : (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
      </svg>
    )}
  </button>
)}
```

Ajouter `group` à la className du wrapper message pour que `group-hover` fonctionne :

```tsx
<div className="relative group ...existing classes...">
```

- [ ] **Step 2 : Ajouter exportMessages dans le store**

Dans `client/src/stores/jarvisStore.ts`, ajouter l'action :

```typescript
exportConversation: () => {
  const messages = get().messages;
  if (messages.length === 0) return;

  const lines: string[] = [
    `# Conversation JARVIS — ${new Date().toLocaleDateString("fr-FR")}`,
    `\nExportée le ${new Date().toLocaleString("fr-FR")}`,
    "\n---\n",
  ];

  for (const msg of messages) {
    const role = msg.role === "user" ? "**Vous**" : msg.role === "assistant" ? "**JARVIS**" : "**Système**";
    const time = new Date(msg.timestamp).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    lines.push(`${role} *(${time})*\n\n${msg.content}\n`);
    lines.push("---\n");
  }

  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `jarvis-${new Date().toISOString().slice(0,10)}.md`;
  a.click();
  URL.revokeObjectURL(url);
},
```

- [ ] **Step 3 : Bouton export dans ChatPanel**

Dans `client/src/components/ChatPanel/ChatPanel.tsx`, ajouter un bouton discret en haut du panel :

```tsx
import { useJarvisStore } from "../../stores/jarvisStore";

// Dans le composant:
const exportConversation = useJarvisStore(s => s.exportConversation);
const messages = useJarvisStore(s => s.messages);

// Dans le JSX, ajouter avant la liste de messages:
{messages.length > 0 && (
  <div className="flex justify-end px-3 py-1">
    <button
      onClick={exportConversation}
      className="text-xs text-cyan-700 hover:text-cyan-400 transition-colors flex items-center gap-1"
      title="Exporter la conversation en Markdown"
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      Exporter
    </button>
  </div>
)}
```

- [ ] **Step 4 : Build TypeScript**

```bash
cd client && npx tsc --noEmit
```

Résultat attendu : `0 erreurs`

- [ ] **Step 5 : Commit**

```bash
git add client/src/components/ChatPanel/Message.tsx client/src/components/ChatPanel/ChatPanel.tsx client/src/stores/jarvisStore.ts
git commit -m "feat: copy button on messages + export conversation to Markdown"
```

---

## Task 9 : Keyboard shortcuts + UX finale

**Files:**
- Modify: `client/src/App.tsx`

- [ ] **Step 1 : Ajouter les raccourcis clavier dans App.tsx**

Dans `client/src/App.tsx`, ajouter un `useEffect` pour les raccourcis :

```typescript
// Dans le composant App:
const sendWs = useJarvisStore(s => s.wsSend);
const isMicActive = useJarvisStore(s => s.isMicActive);

React.useEffect(() => {
  const handleKey = (e: KeyboardEvent) => {
    // Ctrl+K : focus input
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      const input = document.querySelector<HTMLInputElement>("[data-jarvis-input]");
      input?.focus();
    }
    // Ctrl+M : toggle micro
    if ((e.ctrlKey || e.metaKey) && e.key === "m") {
      e.preventDefault();
      // Déclencher le toggle mic depuis le store
      const toggle = document.querySelector<HTMLButtonElement>("[data-mic-toggle]");
      toggle?.click();
    }
    // Escape : fermer settings si ouvert, sinon clear input
    if (e.key === "Escape") {
      const input = document.querySelector<HTMLInputElement>("[data-jarvis-input]");
      if (input) { input.value = ""; input.blur(); }
    }
  };

  window.addEventListener("keydown", handleKey);
  return () => window.removeEventListener("keydown", handleKey);
}, []);
```

Dans `CommandInput.tsx`, ajouter `data-jarvis-input` à l'input et `data-mic-toggle` au bouton micro.

- [ ] **Step 2 : Afficher un badge version v3.0**

Dans `App.tsx`, chercher la ligne qui affiche `v2.0.0` et remplacer par `v3.0.0`.

- [ ] **Step 3 : Build complet**

```bash
cd client && npx tsc --noEmit && echo "TypeScript OK"
```

- [ ] **Step 4 : Commit**

```bash
git add client/src/App.tsx client/src/components/CommandInput/CommandInput.tsx
git commit -m "feat: keyboard shortcuts (Ctrl+K focus, Ctrl+M mic, Escape clear) + version v3.0.0"
```

---

## Task 10 : Rebuild final + push

**Files:**
- All modified files

- [ ] **Step 1 : Vérifier l'import de tous les nouveaux modules Python**

```bash
cd server && .venv\Scripts\python.exe -c "
from tools.registry import ToolRegistry
from core.monitor import run_monitor, subscribe
r = ToolRegistry()
print(f'Registry: {len(r.list_tools())} outils')
print('Imports OK')
"
```

Résultat attendu :
```
Registry: 28 outils
Imports OK
```

- [ ] **Step 2 : TypeScript check complet**

```bash
cd client && npx tsc --noEmit
```

Résultat attendu : `0 erreurs`

- [ ] **Step 3 : Build Tauri production**

```bash
cd client && npx tauri build
```

Résultat attendu :
```
Built application at: ...\target\release\JARVIS.exe
```

- [ ] **Step 4 : Push**

```bash
git push origin master
```

---

## Récapitulatif des améliorations v3.0

| Fonctionnalité | Avant | Après |
|---|---|---|
| Outils disponibles | 19 | 28 (+9) |
| Fenêtre contexte | 4096 tokens | 8192 tokens |
| Messages historique | 20 | 30 |
| Chaîne d'outils | 1 seul tool | Jusqu'à 5 itérations |
| Calcul math | ❌ | ✅ `calculate()` |
| Conversion unités | ❌ | ✅ `convert_units()` |
| Traduction | ❌ | ✅ `translate_text()` |
| Batterie | ❌ | ✅ `get_battery()` |
| Volume | ❌ | ✅ `set_volume()` |
| Ping réseau | ❌ | ✅ `ping_host()` |
| IP publique | ❌ | ✅ `get_public_ip()` |
| Lire fichier | ❌ | ✅ `read_file()` |
| Lister dossier | ❌ | ✅ `list_directory()` |
| Alertes proactives | ❌ | ✅ CPU/RAM/disque |
| Titres Markdown | ❌ | ✅ #, ##, ### |
| Tableaux Markdown | ❌ | ✅ Pipe tables |
| Liens Markdown | ❌ | ✅ [text](url) |
| Blockquotes | ❌ | ✅ > citation |
| Export conversation | ❌ | ✅ Markdown .md |
| Copier message | ❌ | ✅ Bouton hover |
| Raccourcis clavier | ❌ | ✅ Ctrl+K/M, Escape |
