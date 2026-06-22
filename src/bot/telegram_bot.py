"""Telegram Bot — main bot setup with long polling."""
import os
import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from loguru import logger

from src.bot.commands import (
    start, help_cmd, scan_markets, show_wallets,
    follow_wallet, unfollow_wallet, show_positions, show_pnl,
    show_leaderboard, settings_menu, set_tp, set_sl, set_size, set_tier,
    handle_callback, handle_message,
)
from src.utils.config import get_config


class PolyBot:
    """Main Telegram bot application."""

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._app: Application | None = None

    @property
    def app(self) -> Application:
        if self._app is None:
            raise RuntimeError("Bot not built. Call build() first.")
        return self._app

    def build(self):
        """Build the Application with all handlers."""
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

        self._app = Application.builder().token(self.token).build()

        # Command handlers
        self._app.add_handler(CommandHandler("start", start))
        self._app.add_handler(CommandHandler("help", help_cmd))
        self._app.add_handler(CommandHandler("scan", scan_markets))
        self._app.add_handler(CommandHandler("wallets", show_wallets))
        self._app.add_handler(CommandHandler("follow", follow_wallet))
        self._app.add_handler(CommandHandler("unfollow", unfollow_wallet))
        self._app.add_handler(CommandHandler("positions", show_positions))
        self._app.add_handler(CommandHandler("pnl", show_pnl))
        self._app.add_handler(CommandHandler("leaderboard", show_leaderboard))
        self._app.add_handler(CommandHandler("settings", settings_menu))
        self._app.add_handler(CommandHandler("set_tp", set_tp))
        self._app.add_handler(CommandHandler("set_sl", set_sl))
        self._app.add_handler(CommandHandler("set_size", set_size))
        self._app.add_handler(CommandHandler("set_tier", set_tier))

        # Callback query handler (inline buttons)
        self._app.add_handler(CallbackQueryHandler(handle_callback))

        # Fallback message handler
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        logger.info("Bot handlers registered")
        return self

    async def start_polling(self):
        """Start long polling."""
        logger.info("Starting Telegram bot polling...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(
            poll_interval=1.0,
            timeout=30,
        )
        logger.info("Bot polling started")

    async def stop(self):
        """Graceful shutdown."""
        if self._app:
            logger.info("Stopping bot...")
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Bot stopped")

    async def send_alert(self, user_id: int, text: str, **kwargs):
        """Send an alert to a specific user."""
        try:
            await self.app.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")


# Global bot instance
bot = PolyBot()
