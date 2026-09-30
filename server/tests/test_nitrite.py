import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from core import nitrite
import tools.pc_tools as pc

TOKEN = "t" * 64

RESPONSES = {
    "get_battery_detailed": [{"name": "BAT0", "status": "OK", "estimated_charge_remaining": 81,
                              "design_capacity": 50000, "full_charge_capacity": 34000,
                              "battery_health_percent": 68.0, "chemistry": "Li-ion", "cycle_count": 912}],
    "get_disks_smart": [{"disk_index": 0, "label": "Samsung 980", "health": "Healthy", "temperature": 41,
                         "power_on_hours": 5120, "media_type": "SSD", "reallocated_sectors": 0},
                        {"disk_index": 1, "label": "WD Blue", "health": "Warning", "temperature": 38,
                         "media_type": "HDD", "reallocated_sectors": 24}],
    "get_temperatures": [{"sensor_name": "CPU Package", "sensor_type": "CPU", "temp_celsius": 92.0, "source": "LHM"}],
    "get_gpu_temps": [],
    "get_bsod_history": {"entries": [], "total_count": 2, "last_bsod": "2026-09-12", "dump_count": 2},
    "get_event_logs": [{"level": "Error", "source": "disk", "message": "bloc défectueux"}],
    "get_startup_programs": [{"name": f"App{i}"} for i in range(18)],
    "check_system_health": {"dism_health": "Healthy", "pending_reboot": True, "disk_errors": []},
    "get_perf_snapshot": {"cpu_percent": 12.5, "ram_percent": 71.0, "uptime_hours": 49.2},
    "get_top_processes_by_cpu": [{"name": "chrome.exe", "cpu": 8.1}],
    "get_system_info": {"os": "Windows 11", "cpu": "Ryzen 7"},
    "get_ram_detailed": {"total_gb": 32},
    "get_gpu_detailed": [{"name": "RTX 4070"}],
}


class FakeAgent(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *a):
        pass

    def _reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        return self.headers.get("x-nitrite-token") == TOKEN

    def do_GET(self):
        if not self._authorized():
            return self._reply(401, "Jeton manquant")
        self._reply(200, {"name": "NiTriTe Agent"})

    def do_POST(self):
        if not self._authorized():
            return self._reply(401, "Jeton manquant")
        cmd = self.path.rsplit("/", 1)[-1]
        args = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        FakeAgent.calls.append((cmd, args))
        if cmd not in RESPONSES:
            return self._reply(404, f"Commande inconnue : {cmd}")
        self._reply(200, RESPONSES[cmd])


@pytest.fixture
def agent(tmp_path, monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), FakeAgent)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    session = tmp_path / "session.json"
    session.write_text(json.dumps({"port": server.server_port, "token": TOKEN, "pid": 1}))
    monkeypatch.setenv("JARVIS_NITRITE_SESSION", str(session))
    FakeAgent.calls = []
    yield session
    server.shutdown()


def test_invoke_avec_jeton(agent):
    assert nitrite.is_running()
    assert nitrite.invoke("get_perf_snapshot")["ram_percent"] == 71.0


def test_commandes_dangereuses_refusees(agent):
    for cmd in ("disk_wipe", "install_driver", "toggle_defender_realtime", "remove_startup_program"):
        with pytest.raises(PermissionError):
            nitrite.invoke(cmd)
    assert FakeAgent.calls == []  # jamais envoyées à l'agent


def test_jeton_perime(agent):
    agent.write_text(json.dumps({"port": json.loads(agent.read_text())["port"], "token": "vieux"}))
    with pytest.raises(nitrite.NitriteUnavailable, match="jeton"):
        nitrite.invoke("get_perf_snapshot")


def test_diagnostic_complet_et_alertes(agent):
    out = pc.pc_diagnostic("all")
    alertes = out.split("\n\n")[0]
    assert "batterie usée" not in alertes and "batterie fatiguée : 68 %" in alertes
    assert "912 cycles" in alertes
    assert "WD Blue : état SMART « Warning »" in alertes
    assert "24 secteurs réalloués" in alertes
    assert "CRITIQUE — CPU Package à 92 °C" in alertes
    assert "2 écran(s) bleu(s)" in alertes
    assert "redémarrage est en attente" in alertes
    assert "18 programmes" in alertes
    assert "Samsung 980" in out and "RTX 4070" in out
    assert ("get_event_logs", {"logName": "System", "count": 15}) in FakeAgent.calls


def test_diagnostic_par_sujet(agent):
    out = pc.pc_diagnostic("batterie")
    assert "## Batterie" in out and "Disques" not in out
    assert [c for c, _ in FakeAgent.calls] == ["get_battery_detailed"]
    assert "Sujet inconnu" in pc.pc_diagnostic("cafetière")


def test_rapport_enregistre(agent, tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "_reports_dir", lambda: tmp_path / "Rapports")
    out = pc.pc_health_report()
    [report] = list((tmp_path / "Rapports").glob("rapport-pc-*.md"))
    assert "Rapport enregistré" in out and str(report) in out
    assert "# Rapport de santé du PC" in report.read_text(encoding="utf-8")


def test_sans_agent_diagnostic_de_base(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_NITRITE_SESSION", str(tmp_path / "absent.json"))
    out = pc.pc_diagnostic("all")
    assert "NiTriTe Agent n'est pas lancé" in out and "lance NiTriTe" in out


def test_compact():
    lines = pc.compact({"a_b": 1.234, "vide": "", "liste": [{"x": 1}] * 15})
    assert lines[0] == "a b: 1.2"
    assert "  … 3 de plus" in lines
