"""Génère latest.json (manifeste du plugin updater Tauri) pour une release Windows.

Usage : python scripts/make-latest-json.py [notes.txt]
Lit la version dans client/src-tauri/tauri.conf.json, l'installeur NSIS et son .sig
dans client/src-tauri/target/release/bundle/nsis/, écrit latest.json à côté.
À téléverser sur la release GitHub avec l'installeur et le .sig.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF = ROOT / "client" / "src-tauri" / "tauri.conf.json"
NSIS = ROOT / "client" / "src-tauri" / "target" / "release" / "bundle" / "nsis"
REPO = "Heiphaistos/Jarvis-AppWindows"


def build(version: str, exe_name: str, signature: str, notes: str) -> dict:
    return {
        "version": version,
        "notes": notes,
        "pub_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": {
            "windows-x86_64": {
                "signature": signature,
                "url": f"https://github.com/{REPO}/releases/download/v{version}/{exe_name}",
            }
        },
    }


if __name__ == "__main__":
    version = json.loads(CONF.read_text(encoding="utf-8"))["version"]
    exe = NSIS / f"JARVIS_{version}_x64-setup.exe"
    sig = Path(str(exe) + ".sig")
    if not exe.exists() or not sig.exists():
        sys.exit(f"Introuvable : {exe} ou son .sig (build signé requis, voir README).")
    notes = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1 else ""
    out = NSIS / "latest.json"
    out.write_text(
        json.dumps(build(version, exe.name, sig.read_text(encoding="utf-8").strip(), notes), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"OK : {out}")
