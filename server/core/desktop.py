from __future__ import annotations

import sys
import time
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger("desktop")

# Contrôle du bureau Windows par l'API Win32 (ctypes, aucune dépendance) :
# fenêtres (lister, activer, réduire, agrandir, fermer), frappe de texte et
# raccourcis clavier. La frappe passe par SendInput en mode Unicode : accents,
# emoji et caractères spéciaux arrivent tels quels, sans toucher au
# presse-papiers ni dépendre de la disposition du clavier.

# Fenêtres de JARVIS lui-même : jamais la cible d'une frappe « à l'aveugle ».
_SELF_TITLES = ("j.a.r.v.i.s", "jarvis")


@dataclass(frozen=True)
class Window:
    handle: object  # HWND
    title: str
    minimized: bool = False


VK = {
    "ctrl": 0x11, "control": 0x11, "ctl": 0x11, "alt": 0x12, "shift": 0x10, "maj": 0x10,
    "win": 0x5B, "windows": 0x5B, "enter": 0x0D, "entrée": 0x0D, "entree": 0x0D, "return": 0x0D,
    "tab": 0x09, "esc": 0x1B, "escape": 0x1B, "echap": 0x1B, "échap": 0x1B, "space": 0x20,
    "espace": 0x20, "backspace": 0x08, "retour": 0x08, "delete": 0x2E, "suppr": 0x2E, "del": 0x2E,
    "insert": 0x2D, "home": 0x24, "end": 0x23, "fin": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "haut": 0x26, "down": 0x28, "bas": 0x28, "left": 0x25, "gauche": 0x25,
    "right": 0x27, "droite": 0x27, "printscreen": 0x2C, "capslock": 0x14,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
}
_MODIFIERS = {0x11, 0x12, 0x10, 0x5B}
# Ctrl+Alt+Suppr : réservé à Windows (SendInput ne peut de toute façon pas le simuler).
_BLOCKED = {frozenset({0x11, 0x12, 0x2E})}


def parse_keys(combo: str) -> list[int]:
    """« ctrl+shift+s » → codes virtuels [0x11, 0x10, 0x53]. ValueError si inconnu."""
    codes: list[int] = []
    for part in combo.lower().replace(" ", "").split("+"):
        if not part:
            continue
        if part in VK:
            codes.append(VK[part])
        elif len(part) == 1 and part.isalnum():
            codes.append(ord(part.upper()))
        else:
            raise ValueError(f"touche inconnue : {part}")
    if not codes:
        raise ValueError("aucune touche")
    if frozenset(codes) in _BLOCKED:
        raise ValueError("combinaison réservée à Windows")
    return codes


def is_self(title: str) -> bool:
    t = title.lower()
    return any(s in t for s in _SELF_TITLES)


def match_window(windows: list[Window], query: str) -> Window | None:
    """Fenêtre dont le titre contient la requête (insensible à la casse) ;
    le titre exact l'emporte, puis la plus haute dans la pile (ordre fourni)."""
    q = query.strip().lower()
    if not q:
        return None
    exact = [w for w in windows if w.title.lower() == q]
    if exact:
        return exact[0]
    partial = [w for w in windows if q in w.title.lower() and not is_self(w.title)]
    return partial[0] if partial else None


def last_user_window(windows: list[Window]) -> Window | None:
    """La fenêtre qui était au premier plan avant JARVIS (ordre Z, du haut vers le bas)."""
    return next((w for w in windows if not is_self(w.title) and not w.minimized), None)


class Desktop:
    """Accès Win32. Remplaçable dans les tests par un faux bureau."""

    available = sys.platform == "win32"

    def __init__(self) -> None:
        if not self.available:
            return
        import ctypes
        from ctypes import wintypes

        self._ct = ctypes
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        ULONG_PTR = ctypes.c_size_t

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        self._KEYBDINPUT, self._INPUT = KEYBDINPUT, INPUT
        self._enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        # Signatures explicites : sans elles ctypes passe les HWND en int 32 bits.
        u, H = self._user32, wintypes.HWND
        for name, args, res in [
            ("EnumWindows", [self._enum_proc, wintypes.LPARAM], wintypes.BOOL),
            ("IsWindowVisible", [H], wintypes.BOOL),
            ("IsIconic", [H], wintypes.BOOL),
            ("GetWindow", [H, wintypes.UINT], H),
            ("GetWindowTextLengthW", [H], ctypes.c_int),
            ("GetWindowTextW", [H, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            ("ShowWindow", [H, ctypes.c_int], wintypes.BOOL),
            ("SetForegroundWindow", [H], wintypes.BOOL),
            ("PostMessageW", [H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL),
            ("GetForegroundWindow", [], H),
            ("SendInput", [wintypes.UINT, ctypes.c_void_p, ctypes.c_int], wintypes.UINT),
        ]:
            fn = getattr(u, name)
            fn.argtypes, fn.restype = args, res

    # ── Fenêtres ─────────────────────────────────────────────────────────────

    def windows(self) -> list[Window]:
        """Fenêtres visibles avec un titre, de la plus haute à la plus basse."""
        found: list[Window] = []
        u = self._user32

        def _cb(hwnd, _):
            if u.IsWindowVisible(hwnd) and not u.GetWindow(hwnd, 4):  # 4 = GW_OWNER : pas les popups
                length = u.GetWindowTextLengthW(hwnd)
                if length:
                    buf = self._ct.create_unicode_buffer(length + 1)
                    u.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.strip()
                    if title and title not in ("Program Manager", "Paramètres", "Settings"):
                        found.append(Window(hwnd, title, bool(u.IsIconic(hwnd))))
            return True

        u.EnumWindows(self._enum_proc(_cb), 0)
        return found

    def activate(self, w: Window) -> bool:
        u = self._user32
        if u.IsIconic(w.handle):
            u.ShowWindow(w.handle, 9)  # SW_RESTORE
        # Windows refuse SetForegroundWindow à un processus en arrière-plan :
        # un appui sur Alt débloque la règle (technique documentée et courante).
        self._key(0x12, down=True)
        self._key(0x12, down=False)
        ok = bool(u.SetForegroundWindow(w.handle))
        time.sleep(0.15)
        return ok

    def show(self, w: Window, command: int) -> None:
        self._user32.ShowWindow(w.handle, command)

    def close(self, w: Window) -> None:
        # WM_CLOSE : l'application peut demander d'enregistrer, rien n'est tué de force.
        self._user32.PostMessageW(w.handle, 0x0010, 0, 0)

    def foreground_title(self) -> str:
        hwnd = self._user32.GetForegroundWindow()
        length = self._user32.GetWindowTextLengthW(hwnd)
        buf = self._ct.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value

    # ── Clavier ──────────────────────────────────────────────────────────────

    def _send(self, inputs: list) -> None:
        arr = (self._INPUT * len(inputs))(*inputs)
        self._user32.SendInput(len(inputs), arr, self._ct.sizeof(self._INPUT))

    def _key(self, vk: int, down: bool) -> None:
        ki = self._KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0 if down else 0x0002, time=0, dwExtraInfo=0)
        self._send([self._INPUT(type=1, ki=ki)])

    def hotkey(self, codes: list[int]) -> None:
        for vk in codes:
            self._key(vk, True)
        for vk in reversed(codes):
            self._key(vk, False)

    def type_text(self, text: str) -> None:
        for ch in text:
            if ch == "\n":
                self.hotkey([0x0D])
            elif ch == "\t":
                self.hotkey([0x09])
            else:
                # KEYEVENTF_UNICODE (0x4) : le caractère lui-même, indépendant du clavier.
                units = ch.encode("utf-16-le")
                for i in range(0, len(units), 2):
                    code = int.from_bytes(units[i:i + 2], "little")
                    down = self._KEYBDINPUT(wVk=0, wScan=code, dwFlags=0x4, time=0, dwExtraInfo=0)
                    up = self._KEYBDINPUT(wVk=0, wScan=code, dwFlags=0x4 | 0x2, time=0, dwExtraInfo=0)
                    self._send([self._INPUT(type=1, ki=down), self._INPUT(type=1, ki=up)])
            time.sleep(0.004)  # certaines applis perdent des caractères envoyés trop vite


_desktop: Desktop | None = None


def get_desktop() -> Desktop:
    global _desktop
    if _desktop is None:
        _desktop = Desktop()
    return _desktop


def set_desktop(desktop: Desktop | None) -> None:
    """Tests : injecter un faux bureau."""
    global _desktop
    _desktop = desktop
