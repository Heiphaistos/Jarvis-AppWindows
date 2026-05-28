from __future__ import annotations
import shutil
import tempfile
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("file_tools")

_HOME = Path.home()
_SAFE_TEMP_DIRS: list[str] = list({
    tempfile.gettempdir(),
    str(_HOME / "AppData" / "Local" / "Temp"),
})
_MAX_CONTENT_BYTES = 1 * 1024 * 1024  # 1 MB


def _resolve_safe(path_str: str) -> Path | None:
    """Resolve path and verify it stays within the user home directory."""
    try:
        p = Path(path_str).expanduser().resolve()
        if p.is_relative_to(_HOME):
            return p
        return None
    except Exception:
        return None


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
    safe_path = _resolve_safe(path)
    if safe_path is None:
        return "Erreur: création limitée au répertoire home."
    if len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
        return "Erreur: contenu trop volumineux (max 1 MB)."
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.write_text(content, encoding="utf-8")
    return f"Fichier créé: {safe_path}"


def move_file(src: str, dst: str) -> str:
    src_path = _resolve_safe(src)
    dst_path = _resolve_safe(dst)
    if src_path is None or dst_path is None:
        return "Erreur: déplacement limité au répertoire home."
    if not src_path.exists():
        return f"Fichier source introuvable: {src}"
    shutil.move(str(src_path), str(dst_path))
    return f"Fichier déplacé: {src_path.name} → {dst_path}"
