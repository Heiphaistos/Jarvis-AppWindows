import logging
import sys
from pathlib import Path
from datetime import datetime

def _resolve_logs_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / ".logs"
    return Path(__file__).parents[2] / ".logs"

LOGS_DIR = _resolve_logs_dir()
LOGS_DIR.mkdir(exist_ok=True)


def _build_handler() -> logging.FileHandler:
    log_file = LOGS_DIR / f"jarvis_{datetime.now():%Y-%m-%d}.log"
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    ))
    return handler


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(_build_handler())
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(stream)
    return logger
