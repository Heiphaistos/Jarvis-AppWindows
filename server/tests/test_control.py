import pytest

from core import desktop as dk
from core.desktop import Window
import tools.control_tools as ct


class FakeDesktop:
    available = True

    def __init__(self, windows):
        self._windows = windows
        self.log = []

    def windows(self):
        return list(self._windows)

    def activate(self, w):
        self.log.append(("activate", w.title))
        return True

    def show(self, w, cmd):
        self.log.append(("show", w.title, cmd))

    def close(self, w):
        self.log.append(("close", w.title))

    def hotkey(self, codes):
        self.log.append(("keys", tuple(codes)))

    def type_text(self, text):
        self.log.append(("type", text))


@pytest.fixture
def fake():
    d = FakeDesktop([
        Window(1, "J.A.R.V.I.S."),
        Window(2, "Sans titre - Bloc-notes"),
        Window(3, "Inscription - Google Chrome"),
        Window(4, "Spotify Premium", minimized=True),
    ])
    dk.set_desktop(d)
    yield d
    dk.set_desktop(None)


def test_parse_keys():
    assert dk.parse_keys("ctrl+shift+s") == [0x11, 0x10, ord("S")]
    assert dk.parse_keys("Alt + Tab") == [0x12, 0x09]
    assert dk.parse_keys("f5") == [0x74]
    assert dk.parse_keys("entrée") == [0x0D]
    with pytest.raises(ValueError):
        dk.parse_keys("ctrl+licorne")
    with pytest.raises(ValueError):
        dk.parse_keys("ctrl+alt+suppr")


def test_liste(fake):
    out = ct.list_windows()
    assert "- Sans titre - Bloc-notes" in out and "Spotify Premium (réduite)" in out


def test_cible_par_defaut_n_est_jamais_jarvis(fake):
    out = ct.type_text("Bonjour, ça marche ? Été 2026 ✓", press_enter=True)
    assert "Bloc-notes" in out and "validé" in out
    assert fake.log == [("activate", "Sans titre - Bloc-notes"), ("type", "Bonjour, ça marche ? Été 2026 ✓\n")]


def test_fenetre_nommee(fake):
    ct.type_text("hello", window="chrome")
    assert fake.log[0] == ("activate", "Inscription - Google Chrome")
    assert "Aucune fenêtre ne contient « word »" in ct.type_text("x", window="word")


def test_actions_fenetre(fake):
    assert "premier plan" in ct.window_action("spotify", "focus")
    assert "Agrandie" in ct.window_action("bloc-notes", "agrandir")
    assert fake.log[-1] == ("show", "Sans titre - Bloc-notes", 3)
    assert "Fermeture demandée" in ct.window_action("chrome", "fermer")
    assert fake.log[-1] == ("close", "Inscription - Google Chrome")
    assert "Action inconnue" in ct.window_action("chrome", "exploser")
    # JARVIS ne se ferme pas lui-même sur une requête partielle.
    assert "Aucune fenêtre" in ct.window_action("jarvis", "close")


def test_raccourcis(fake):
    assert "envoyé" in ct.press_keys("ctrl+s, alt+f4", window="bloc")
    assert fake.log[1:] == [("keys", (0x11, ord("S"))), ("keys", (0x12, 0x73))]
    assert ct.press_keys("ctrl+truc").startswith("Erreur")


def test_formulaire(fake):
    out = ct.fill_form(["Tony", "Stark", "", "tony@stark.com"], window="inscription", submit=True)
    assert "3 champ(s) rempli(s)" in out and "envoyé" in out
    assert fake.log == [
        ("activate", "Inscription - Google Chrome"),
        ("type", "Tony"), ("keys", (0x09,)),
        ("type", "Stark"), ("keys", (0x09,)),
        ("keys", (0x09,)),  # champ vide : sauté
        ("type", "tony@stark.com"),
        ("keys", (0x0D,)),
    ]


def test_limites(fake):
    assert "trop long" in ct.type_text("x" * 6000)
    assert "20 champs" in ct.fill_form(["a"] * 21)


def test_hors_windows():
    class NoDesktop:
        available = False

    dk.set_desktop(NoDesktop())
    try:
        assert "demande Windows" in ct.list_windows()
    finally:
        dk.set_desktop(None)


def test_x11_desktop_parses_wmctrl_and_drives_xdotool(monkeypatch):
    """Linux : fenêtres via wmctrl (ordre d'empilement xprop), clavier via xdotool."""
    calls: list[tuple] = []
    outputs = {
        "wmctrl -l": "0x03a00007  0 pc  Document - LibreOffice\n0x04200003  0 pc  Firefox\n0x01000001 -1 pc  Bureau\n",
        "xprop -root _NET_CLIENT_LIST_STACKING": "_NET_CLIENT_LIST_STACKING(WINDOW): window id # 0x3a00007, 0x4200003\n",
    }

    def fake_run(self, *args, timeout=5):
        calls.append(args)
        key = " ".join(a.rsplit("/", 1)[-1] for a in args[:3]).strip()
        for k, v in outputs.items():
            if key.startswith(k):
                return v
        return ""

    monkeypatch.setattr(dk.X11Desktop, "_run", fake_run)
    d = dk.X11Desktop.__new__(dk.X11Desktop)
    d._xdotool, d._wmctrl, d.available = "/usr/bin/xdotool", "/usr/bin/wmctrl", True
    wins = d.windows()
    assert [w.title for w in wins] == ["Firefox", "Document - LibreOffice"]  # le plus haut d'abord
    d.hotkey(dk.parse_keys("ctrl+shift+s"))
    assert calls[-1][1:] == ("key", "--clearmodifiers", "ctrl+shift+s")
    d.type_text("Été ✓")
    assert calls[-1][-2:] == ("--", "Été ✓")
    d.show(wins[0], 3)
    assert "add,maximized_vert,maximized_horz" in calls[-1]
