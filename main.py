"""PolyBot v1.0 — Main Entry Point

Polymarket Trading Bot for World Cup 2026
Connects to Telegram, scans markets, tracks smart wallets,
and executes copy trades via 1-tap confirmation.

Usage:
    python main.py
"""
import asyncio
import signal
import sys
import os
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from loguru import logger

from src.utils.config import get_config
from src.utils.logger import setup_logging
from src.db.database import init_db
from src.bot.telegram_bot import bot
from src.scheduler.jobs import scheduler
from src.api.polymarket_api import api


async def main():
    """Main application entry point."""
    # ── Initialize ──
    setup_logging()
    logger.info("=" * 50)
    logger.info("PolyBot v1.0 — Starting up...")
    logger.info("=" * 50)

    # Load config
    config = get_config()
    logger.info(f"Mode: {config.get('deployment.mode', 'development')}")

    # Validate required env vars
    required_vars = ["TELEGRAM_BOT_TOKEN"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(f"Missing required environment variables: {missing}")
        logger.error("Please copy .env.example to .env and fill in the values.")
        sys.exit(1)

    cnf_warning = not os.getenv("POLYMARKET_PRIVATE_KEY")
    if cnf_warning:
        logger.warning("POLYMARKET_PRIVATE_KEY not set — running in read-only mode")
        logger.warning("Market scanning and wallet tracking will work, but orders cannot be placed.")

    # ── Database ──
    try:
        await init_db()
        logger.info("Database ready")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        sys.exit(1)

    # ── Telegram Bot ──
    try:
        bot.build()
        await bot.start_polling()
        logger.info("Telegram bot online")
    except Exception as e:
        logger.error(f"Bot startup failed: {e}")
        sys.exit(1)

    # ── Scheduler ──
    scheduler.start(bot=bot)

    # ── Health check endpoint ──
    port = int(config.get("deployment.health_check_port", 8080))

    # ── Graceful shutdown ──
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received...")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler well
            signal.signal(sig, lambda *args: shutdown_event.set())

    logger.info("✅ PolyBot is running! Press Ctrl+C to stop.")
    logger.info(f"Health check: http://localhost:{port}")

    # ── Keep running ──
    try:
        await shutdown_event.wait()
    except KeyboardInterrupt:
        pass

    # ── Cleanup ──
    logger.info("Shutting down...")
    scheduler.stop()
    await bot.stop()
    await api.close()
    logger.info("PolyBot stopped. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
