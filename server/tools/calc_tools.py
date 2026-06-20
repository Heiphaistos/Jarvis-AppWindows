from __future__ import annotations
import ast
import math
import operator
import re
import urllib.request
import urllib.parse
import json
from utils.logger import get_logger

logger = get_logger("calc_tools")

# Fonctions mathématiques autorisées (liste blanche explicite)
_SAFE_FUNCTIONS: dict[str, object] = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
_SAFE_FUNCTIONS.update({
    "abs": abs, "round": round, "min": min, "max": max,
    "sum": sum, "pow": pow, "int": int, "float": float,
})

# Constantes autorisées (ast.Name nodes)
_SAFE_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
}

# Opérateurs binaires et unaires autorisés
_BIN_OPS: dict[type, object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: dict[type, object] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_node(node: ast.expr, depth: int = 0) -> float:
    """Évalue récursivement un nœud AST de manière sécurisée."""
    if depth > 50:
        raise ValueError("Expression trop complexe (profondeur maximale atteinte).")

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Type de constante non autorisé: {type(node.value).__name__}")

    if isinstance(node, ast.Name):
        if node.id in _SAFE_CONSTANTS:
            return _SAFE_CONSTANTS[node.id]
        raise ValueError(f"Identifiant non autorisé: '{node.id}'")

    if isinstance(node, ast.BinOp):
        op_fn = _BIN_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Opérateur binaire non autorisé: {type(node.op).__name__}")
        left = _safe_eval_node(node.left, depth + 1)
        right = _safe_eval_node(node.right, depth + 1)
        return op_fn(left, right)  # type: ignore[operator]

    if isinstance(node, ast.UnaryOp):
        op_fn = _UNARY_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Opérateur unaire non autorisé: {type(node.op).__name__}")
        return op_fn(_safe_eval_node(node.operand, depth + 1))  # type: ignore[operator]

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Appels de méthode non autorisés (utilisez les fonctions directes).")
        fn_name = node.func.id
        fn = _SAFE_FUNCTIONS.get(fn_name)
        if fn is None:
            raise ValueError(
                f"Fonction '{fn_name}' non autorisée. Utilisez: sqrt, sin, cos, log, exp, abs, round, etc."
            )
        args = [_safe_eval_node(arg, depth + 1) for arg in node.args]
        if node.keywords:
            raise ValueError("Arguments nommés non supportés dans les appels de fonction.")
        return fn(*args)  # type: ignore[operator]

    raise ValueError(f"Construction non autorisée: {type(node).__name__}")


def calculate(expression: str) -> str:
    """
    Évalue une expression mathématique sécurisée via AST (sans eval).
    Supporte: + - * / ** % // sqrt() sin() cos() log() pi e abs() round()
    """
    expr = expression.strip()
    if len(expr) > 500:
        return "Expression trop longue."

    # Remplacer ^ par ** pour compatibilité
    expr = expr.replace("^", "**")

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return f"Syntaxe invalide: {e}"

    try:
        result = _safe_eval_node(tree.body)
        if isinstance(result, float):
            if result == int(result) and abs(result) < 1e15:
                return f"Résultat: {int(result)}"
            return f"Résultat: {result:.10g}"
        return f"Résultat: {result}"
    except ZeroDivisionError:
        return "Erreur: division par zéro."
    except (ValueError, TypeError) as e:
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
