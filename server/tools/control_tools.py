from __future__ import annotations

from tools.decorator import tool
from utils.logger import get_logger

logger = get_logger("control_tools")

MAX_TYPED_CHARS = 5000
MAX_FORM_FIELDS = 20

_ACTIONS = {
    "activer": "focus", "focus": "focus", "afficher": "focus", "montrer": "focus", "basculer": "focus",
    "reduire": "minimize", "réduire": "minimize", "minimize": "minimize", "minimiser": "minimize",
    "agrandir": "maximize", "maximize": "maximize", "maximiser": "maximize", "plein_ecran": "maximize",
    "restaurer": "restore", "restore": "restore",
    "fermer": "close", "close": "close",
}


def _desktop():
    from core.desktop import get_desktop
    d = get_desktop()
    if not d.available:
        raise RuntimeError("Le contrôle des fenêtres ne fonctionne que sous Windows.")
    return d


def _target(window: str):
    """Fenêtre nommée, sinon celle qui était au premier plan avant JARVIS."""
    from core.desktop import last_user_window, match_window
    d = _desktop()
    wins = d.windows()
    if window.strip():
        w = match_window(wins, window)
        if w is None:
            titles = ", ".join(f"« {x.title[:40]} »" for x in wins[:8])
            raise LookupError(f"Aucune fenêtre ne contient « {window} ». Ouvertes : {titles}")
        return d, w
    w = last_user_window(wins)
    if w is None:
        raise LookupError("Aucune fenêtre cible : ouvrez l'application ou nommez la fenêtre.")
    return d, w


@tool
def list_windows() -> str:
    """Liste les fenêtres ouvertes (titre), de celle au premier plan à la plus en arrière."""
    try:
        wins = _desktop().windows()
    except RuntimeError as e:
        return str(e)
    if not wins:
        return "Aucune fenêtre ouverte."
    return "Fenêtres ouvertes :\n" + "\n".join(
        f"- {w.title}{' (réduite)' if w.minimized else ''}" for w in wins[:30]
    )


@tool
def window_action(window: str, action: str = "focus") -> str:
    """Agit sur une fenêtre désignée par une partie de son titre : focus (mettre au premier plan), minimize, maximize, restore ou close (fermeture normale, l'application peut demander d'enregistrer)."""
    act = _ACTIONS.get((action or "focus").strip().lower().replace(" ", "_"))
    if act is None:
        return "Action inconnue : focus, minimize, maximize, restore ou close."
    if not isinstance(window, str) or not window.strip():
        return "Erreur: précisez la fenêtre (une partie de son titre)."
    try:
        d, w = _target(window)
    except (RuntimeError, LookupError) as e:
        return str(e)
    if act == "focus":
        d.activate(w)
        return f"Fenêtre « {w.title} » au premier plan."
    if act == "close":
        d.close(w)
        return f"Fermeture demandée pour « {w.title} »."
    d.show(w, {"minimize": 6, "maximize": 3, "restore": 9}[act])  # SW_MINIMIZE / SW_MAXIMIZE / SW_RESTORE
    return {"minimize": "Réduite", "maximize": "Agrandie", "restore": "Restaurée"}[act] + f" : « {w.title} »."


@tool
def type_text(text: str, window: str = "", press_enter: bool = False) -> str:
    """Tape du texte au clavier dans une fenêtre (partie du titre) ou, par défaut, dans celle qui était au premier plan avant JARVIS. Accents et caractères spéciaux pris en charge ; press_enter valide ensuite."""
    if not isinstance(text, str) or not text:
        return "Erreur: texte vide."
    if len(text) > MAX_TYPED_CHARS:
        return f"Erreur: texte trop long ({MAX_TYPED_CHARS} caractères max)."
    try:
        d, w = _target(window if isinstance(window, str) else "")
    except (RuntimeError, LookupError) as e:
        return str(e)
    d.activate(w)
    d.type_text(text + ("\n" if press_enter else ""))
    logger.info(f"Texte tapé dans « {w.title} » ({len(text)} caractères)")
    return f"Texte tapé dans « {w.title} » ({len(text)} caractères){', validé' if press_enter else ''}."


@tool
def press_keys(keys: str, window: str = "") -> str:
    """Appuie sur une touche ou un raccourci clavier (ex. « ctrl+s », « alt+tab », « enter », « ctrl+shift+esc », « win+d ») dans une fenêtre ou celle qui était au premier plan avant JARVIS. Plusieurs raccourcis séparés par des virgules."""
    from core.desktop import parse_keys
    if not isinstance(keys, str) or not keys.strip():
        return "Erreur: aucune touche."
    try:
        combos = [parse_keys(k) for k in keys.split(",") if k.strip()]
    except ValueError as e:
        return f"Erreur: {e}"
    try:
        d, w = _target(window if isinstance(window, str) else "")
    except (RuntimeError, LookupError) as e:
        return str(e)
    d.activate(w)
    for codes in combos:
        d.hotkey(codes)
    return f"Raccourci « {keys.strip()} » envoyé à « {w.title} »."


@tool
def fill_form(values: list, window: str = "", submit: bool = False) -> str:
    """Remplit un formulaire champ par champ : tape chaque valeur puis passe au champ suivant avec Tab (cliquez d'abord dans le premier champ, ou nommez la fenêtre). Une valeur vide saute le champ. submit appuie sur Entrée à la fin."""
    if not isinstance(values, list) or not values:
        return "Erreur: liste de valeurs vide."
    if len(values) > MAX_FORM_FIELDS:
        return f"Erreur: {MAX_FORM_FIELDS} champs maximum."
    texts = ["" if v is None else str(v) for v in values]
    if sum(len(t) for t in texts) > MAX_TYPED_CHARS:
        return "Erreur: formulaire trop long."
    try:
        d, w = _target(window if isinstance(window, str) else "")
    except (RuntimeError, LookupError) as e:
        return str(e)
    d.activate(w)
    for i, value in enumerate(texts):
        if value:
            d.type_text(value)
        if i < len(texts) - 1:
            d.hotkey([0x09])  # Tab → champ suivant
    if submit:
        d.hotkey([0x0D])
    filled = sum(1 for t in texts if t)
    return f"{filled} champ(s) rempli(s) dans « {w.title} »{', formulaire envoyé' if submit else ''}."
