"""Background jobs — scheduled tasks for scanning, tracking, and monitoring."""
import asyncio
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from src.scanner.market_scanner import scanner
from src.wallet.tracker import tracker
from src.trade.copy_engine import copy_engine
from src.trade.position_manager import position_manager
from src.trade.risk_manager import risk_manager
from src.db import models as db
from src.utils.config import get_config


class JobScheduler:
    """Manages all recurring background jobs."""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._signal_cache: list[dict] = []  # Store latest signals for bot to reference

    def start(self, bot=None):
        """Start all scheduled jobs."""
        config = get_config()

        # ── Market Scanner: every 30 seconds ──
        scan_interval = int(config.get("scanner.interval_seconds", 30))
        self._scheduler.add_job(
            self._scan_job,
            "interval",
            seconds=scan_interval,
            id="market_scanner",
            replace_existing=True,
        )
        logger.info(f"Market scanner scheduled every {scan_interval}s")

        # ── Wallet Tracker: every 15 minutes ──
        wallet_interval = int(config.get("wallet_tracker.interval_minutes", 15))
        self._scheduler.add_job(
            self._wallet_tracker_job,
            "interval",
            minutes=wallet_interval,
            id="wallet_tracker",
            replace_existing=True,
        )
        logger.info(f"Wallet tracker scheduled every {wallet_interval}min")

        # ── Position Monitor (TP/SL): every 15 seconds ──
        self._scheduler.add_job(
            self._position_monitor_job,
            "interval",
            seconds=15,
            id="position_monitor",
            replace_existing=True,
        )
        logger.info("Position monitor scheduled every 15s")

        # ── Signal Detection: every 5 minutes ──
        self._scheduler.add_job(
            self._signal_detection_job,
            "interval",
            minutes=5,
            id="signal_detection",
            replace_existing=True,
        )
        logger.info("Signal detection scheduled every 5min")

        # ── Daily Stats Reset: midnight ──
        self._scheduler.add_job(
            self._daily_reset_job,
            "cron",
            hour=0,
            minute=1,
            id="daily_reset",
            replace_existing=True,
        )
        logger.info("Daily stats reset scheduled at midnight")

        # Store bot reference for alerts
        self._bot = bot

        self._scheduler.start()
        logger.info("Scheduler started — all jobs running")

    def stop(self):
        """Shutdown scheduler."""
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    # ── Job Implementations ──

    async def _scan_job(self):
        """Periodically scan markets and discover new wallets."""
        try:
            markets = await scanner.scan_all()
            if markets:
                market_ids = [m["id"] for m in markets[:10]]
                # Discover wallets from these markets
                smart_wallets = await tracker.scan_discover_and_track(market_ids)
                if smart_wallets:
                    logger.info(f"Discovered {len(smart_wallets)} smart wallets")
        except Exception as e:
            logger.error(f"Scan job error: {e}")

    async def _wallet_tracker_job(self):
        """Refresh all followed wallet scores."""
        try:
            results = await tracker.refresh_all_followed()
            if results:
                logger.info(f"Refreshed {len(results)} wallet scores")
        except Exception as e:
            logger.error(f"Wallet tracker job error: {e}")

    async def _position_monitor_job(self):
        """Check open positions for TP/SL/Time conditions."""
        try:
            await position_manager.monitor_positions()
        except Exception as e:
            logger.error(f"Position monitor error: {e}")

    async def _signal_detection_job(self):
        """Detect new trades from followed wallets and generate signals."""
        try:
            signals = await copy_engine.detect_new_signals()
            if signals:
                self._signal_cache = signals
                logger.info(f"Detected {len(signals)} new copy trade signals")

                # Send alerts to owner via Telegram
                if self._bot:
                    owner_id = os.getenv("TELEGRAM_OWNER_ID")
                    if owner_id:
                        for sig in signals[:5]:  # Limit to top 5
                            await self._send_signal_alert(int(owner_id), sig)
        except Exception as e:
            logger.error(f"Signal detection error: {e}")

    async def _daily_reset_job(self):
        """Initialize daily stats for the new day."""
        try:
            bankroll = await db.get_bankroll()
            await db.update_daily_stats({
                "starting_balance": bankroll,
                "ending_balance": bankroll,
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "pnl_usd": 0,
                "pnl_pct": 0,
            })
            logger.info(f"Daily stats reset. Bankroll: ${bankroll:.2f}")
        except Exception as e:
            logger.error(f"Daily reset error: {e}")

    async def _send_signal_alert(self, user_id: int, signal: dict):
        """Send a copy trade signal alert to Telegram."""
        from src.bot.keyboards import copy_trade_keyboard

        tier_emoji = "🟢" if signal.get("wallet_tier") == "ELITE" else "🟡"
        text = (
            f"{tier_emoji} <b>Copy Trade Signal</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Wallet: <code>{signal['wallet_address'][:10]}...</code>\n"
            f"Tier: <b>{signal['wallet_tier']}</b> | WR: {signal['wallet_wr']:.1f}%\n"
            f"Trades: {signal['wallet_trades']} | Score: {signal['wallet_score']:.1f}\n"
            f"\n"
            f"Market: <b>{signal.get('market_question', 'Unknown')[:80]}</b>\n"
            f"Position: <b>{signal['side']}</b> @ ${signal['price']:.4f}\n"
        )

        try:
            await self._bot.send_alert(
                user_id,
                text,
                reply_markup=copy_trade_keyboard(signal),
            )
        except Exception as e:
            logger.error(f"Failed to send signal alert: {e}")

    @property
    def latest_signals(self) -> list[dict]:
        """Get the latest detected signals (for bot commands)."""
        return self._signal_cache


# Global instance
scheduler = JobScheduler()
