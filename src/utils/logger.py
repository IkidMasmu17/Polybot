"""Structured logging with loguru."""
import sys
from pathlib import Path

from loguru import logger

from .config import get_config

_initialized = False


def setup_logging():
    """Configure loguru for file + console output."""
    global _initialized
    if _initialized:
        return

    config = get_config()
    log_cfg = config.logging_config

    # Remove default handler
    logger.remove()

    # Console handler — colorized
    logger.add(
        sys.stderr,
        level=log_cfg.get("level", "INFO"),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> — <level>{message}</level>",
        colorize=True,
    )

    # File handler — structured
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "polybot.log"

    logger.add(
        log_file,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} — {message}",
        rotation=log_cfg.get("rotation", "10 MB"),
        retention=log_cfg.get("retention", "30 days"),
        compression="zip",
    )

    _initialized = True
    logger.info("Logging initialized")


def get_logger(name: str = __name__):
    return logger.bind(module=name)
