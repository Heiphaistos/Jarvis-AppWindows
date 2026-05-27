from __future__ import annotations
import shutil
import tempfile
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("file_tools")

_SAFE_TEMP_DIRS = [
    tempfile.gettempdir(),
    str(Path.home() / "AppData" / "Local" / "Temp"),
]


def delete_temp_files() -> str:
    count = 0
    errors = 0
    for dir_path in _SAFE_TEMP_DIRS:
        for item in Path(dir_path).iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                count += 1
            except PermissionError:
                errors += 1
    return f"{count} éléments supprimés ({errors} erreurs de permission)."


def create_file(path: str, content: str = "") -> str:
    safe_path = Path(path).expanduser()
    if safe_path.is_absolute() and not str(safe_path).startswith(str(Path.home())):
        return "Erreur: création limitée au répertoire home."
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.write_text(content, encoding="utf-8")
    return f"Fichier créé: {safe_path}"


def move_file(src: str, dst: str) -> str:
    src_path = Path(src).expanduser()
    dst_path = Path(dst).expanduser()
    if not src_path.exists():
        return f"Fichier source introuvable: {src}"
    shutil.move(str(src_path), str(dst_path))
    return f"Fichier déplacé: {src} → {dst}"
