from __future__ import annotations
import math
import re
import urllib.request
import urllib.parse
import json
from utils.logger import get_logger

logger = get_logger("calc_tools")

_SAFE_NAMES = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
_SAFE_NAMES.update({"abs": abs, "round": round, "min": min, "max": max,
                    "sum": sum, "pow": pow, "int": int, "float": float})


def calculate(expression: str) -> str:
    """
    Évalue une expression mathématique sécurisée.
    Supporte: + - * / ** % sqrt() sin() cos() log() pi e abs() round()
    """
    expr = expression.strip()
    if len(expr) > 500:
        return "Expression trop longue."
    if "__" in expr:
        return "Expression invalide."

    # Vérifier que les fonctions appelées sont dans la whitelist
    for m in re.finditer(r'([a-zA-Z_]\w*)\s*\(', expr):
        fn = m.group(1)
        if fn not in _SAFE_NAMES:
            return f"Fonction '{fn}' non autorisée. Utilisez: sqrt, sin, cos, log, exp, abs, round, etc."

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
    C/F/K (température), l/gal/ml, km_h/mph/m_s
    """
    conversions: dict[tuple[str, str], float] = {
        ("km", "mi"): 0.621371, ("mi", "km"): 1.60934,
        ("km", "m"): 1000, ("m", "km"): 0.001,
        ("m", "ft"): 3.28084, ("ft", "m"): 0.3048,
        ("cm", "in"): 0.393701, ("in", "cm"): 2.54,
        ("m", "cm"): 100, ("cm", "m"): 0.01,
        ("ft", "km"): 0.0003048, ("km", "ft"): 3280.84,
        ("kg", "lb"): 2.20462, ("lb", "kg"): 0.453592,
        ("kg", "g"): 1000, ("g", "kg"): 0.001,
        ("g", "oz"): 0.035274, ("oz", "g"): 28.3495,
        ("l", "gal"): 0.264172, ("gal", "l"): 3.78541,
        ("l", "ml"): 1000, ("ml", "l"): 0.001,
        ("km_h", "mph"): 0.621371, ("mph", "km_h"): 1.60934,
        ("km_h", "m_s"): 0.277778, ("m_s", "km_h"): 3.6,
        ("mph", "m_s"): 0.44704, ("m_s", "mph"): 2.23694,
    }
    temp_conversions: dict[tuple[str, str], object] = {
        ("c", "f"): lambda v: v * 9 / 5 + 32,
        ("f", "c"): lambda v: (v - 32) * 5 / 9,
        ("c", "k"): lambda v: v + 273.15,
        ("k", "c"): lambda v: v - 273.15,
        ("f", "k"): lambda v: (v - 32) * 5 / 9 + 273.15,
        ("k", "f"): lambda v: (v - 273.15) * 9 / 5 + 32,
    }

    fu = from_unit.lower().strip()
    tu = to_unit.lower().strip()

    if (fu, tu) in temp_conversions:
        result = temp_conversions[(fu, tu)](float(value))
        return f"{value} {from_unit.upper()} = {result:.4g} {to_unit.upper()}"
    if (fu, tu) in conversions:
        result = float(value) * conversions[(fu, tu)]
        return f"{value} {from_unit} = {result:.6g} {to_unit}"
    return (
        f"Conversion {from_unit} → {to_unit} non supportée. "
        "Unités: km, mi, m, ft, cm, in, kg, lb, g, oz, l, gal, ml, C, F, K, km_h, mph, m_s"
    )


def translate_text(text: str, target_lang: str = "fr") -> str:
    """
    Traduit du texte via MyMemory API (gratuit, sans clé API).
    target_lang: fr, en, es, de, it, pt, ja, zh, ar, ru
    """
    LANG_NAMES = {
        "fr": "français", "en": "anglais", "es": "espagnol",
        "de": "allemand", "it": "italien", "pt": "portugais",
        "ja": "japonais", "zh": "chinois", "ar": "arabe", "ru": "russe",
    }
    if len(text) > 500:
        return "Texte trop long pour traduction (max 500 caractères)."

    lang_name = LANG_NAMES.get(target_lang, target_lang)
    encoded = urllib.parse.quote(text)
    try:
        url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair=auto|{target_lang}"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/3.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        translated = data.get("responseData", {}).get("translatedText", "")
        if translated and translated.lower() != text.lower():
            return f"Traduction en {lang_name}: {translated}"
        return f"Traduction indisponible pour '{target_lang}'."
    except Exception as e:
        return f"Erreur traduction: {e}"
