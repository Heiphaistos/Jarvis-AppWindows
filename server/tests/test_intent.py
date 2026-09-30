from core.intent import fast_route


def test_calcul_formulations_naturelles():
    assert fast_route("calcule 17*23") == ("calculate", {"expression": "17*23"})
    assert fast_route("combien font 391 divisé par 17 ?") == ("calculate", {"expression": "391/17"})
    assert fast_route("Combien fait 5 plus 3") == ("calculate", {"expression": "5+3"})
    assert fast_route("calcule 2 puissance 10") == ("calculate", {"expression": "2**10"})
    assert fast_route("17x23") == ("calculate", {"expression": "17*23"})
    assert fast_route("calcule 3,5 * 2") == ("calculate", {"expression": "3.5*2"})


def test_calcul_non_matche():
    # Pas de nombre ou pas d'opérateur → laisser l'agent décider
    assert fast_route("calcule mon empreinte carbone") is None
    assert fast_route("combien font les courses en moyenne") is None


def test_meteo():
    assert fast_route("quelle est la météo à Paris ?") == ("get_weather", {"city": "Paris"})
    assert fast_route("météo à Lyon") == ("get_weather", {"city": "Lyon"})
    assert fast_route("quel temps fait-il à Aix-en-Provence ?") == (
        "get_weather", {"city": "Aix-en-Provence"},
    )


def test_datetime():
    assert fast_route("quelle heure est-il ?") == ("get_datetime", {})
    assert fast_route("on est quel jour ?") == ("get_datetime", {})
    assert fast_route("quelle est la date ?") == ("get_datetime", {})


def test_batterie_et_ip():
    assert fast_route("quel est le niveau de batterie ?") == ("get_battery", {})
    assert fast_route("quelle est mon ip publique ?") == ("get_public_ip", {})


def test_conversation_passe_au_llm():
    assert fast_route("bonjour Jarvis") is None
    assert fast_route("raconte-moi une blague") is None
    assert fast_route("pourquoi mon pc est lent ?") is None
    # Phrase longue avec contexte → jamais de fast-path
    assert fast_route("dans le rapport que je prépare, calcule 2+2 puis explique "
                      "la méthode utilisée et compare avec l'an dernier s'il te plaît") is None


def test_briefing():
    from core.intent import fast_route
    assert fast_route("Jarvis, fais-moi le point") == ("briefing", {})
    assert fast_route("quoi de neuf ce matin ?") == ("briefing", {})
