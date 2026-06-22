"""Wallet Tracker — discovers, tracks, and scores Polymarket wallets."""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger

from src.api.polymarket_api import api
from src.db import models as db
from src.utils.config import get_config
from src.wallet.scoring import (
    calculate_win_rate,
    compute_smart_score,
    classify_tier,
    should_unfollow,
)


class WalletTracker:
    """Tracks and scores Polymarket wallet addresses."""

    def __init__(self):
        self.config = get_config()

    @property
    def tier_config(self) -> dict:
        return self.config.get_tier_config()

    async def track_wallet(self, address: str) -> Optional[dict]:
        """Fetch trade history for a wallet and compute its score."""
        trades = await api.get_wallet_trades(address, limit=200)

        if not trades:
            logger.debug(f"No trades found for {address[:10]}...")
            return None

        # Separate trades by time window
        now = datetime.now(timezone.utc)
        cutoff_30d = now - timedelta(days=30)
        cutoff_90d = now - timedelta(days=90)

        trades_30d = []
        trades_90d = []
        for t in trades:
            trade_time = self._parse_trade_time(t)
            if trade_time and trade_time >= cutoff_30d:
                trades_30d.append(t)
            if trade_time and trade_time >= cutoff_90d:
                trades_90d.append(t)

        # Compute 30d stats
        wins_30d, losses_30d, roi_30d = self._compute_trade_stats(trades_30d)

        # Compute 90d stats
        wins_90d, losses_90d, roi_90d = self._compute_trade_stats(trades_90d)

        total_trades = len(trades_90d)
        if total_trades < self.tier_config.get("min_trades", 20):
            logger.debug(f"Wallet {address[:10]}... has only {total_trades} trades (< minimum)")
            return None

        wr_30d = calculate_win_rate(wins_30d, wins_30d + losses_30d)
        wr_90d = calculate_win_rate(wins_90d, wins_90d + losses_90d)
        avg_roi = (roi_30d + roi_90d) / 2 if (roi_30d + roi_90d) > 0 else 0

        # Compute smart score
        weights = self.config.get("wallet_tracker.wr_period_weights", {"days_30": 0.6, "days_90": 0.4})
        score_data = compute_smart_score(
            wr_30d=wr_30d,
            wr_90d=wr_90d,
            total_trades=total_trades,
            avg_roi_pct=avg_roi,
            wr_30d_weight=weights.get("days_30", 0.6),
            wr_90d_weight=weights.get("days_90", 0.4),
        )

        tier = classify_tier(score_data["smart_score"], self.tier_config)

        # Check consecutive losses
        consecutive = self._count_consecutive_losses(trades)

        wallet_data = {
            "address": address,
            "win_rate_30d": wr_30d,
            "win_rate_90d": wr_90d,
            "avg_roi_pct": avg_roi,
            "smart_score": score_data["smart_score"],
            "tier": tier,
            "total_trades": total_trades,
            "wins_30d": wins_30d,
            "losses_30d": losses_30d,
            "peak_wr": max(wr_30d, wr_90d),
            "consecutive_losses": consecutive,
            "last_trade_at": self._get_last_trade_time(trades),
            "is_following": 0,  # default, not auto-following
        }

        await db.upsert_wallet(wallet_data)

        # Auto-unfollow check
        if self.config.get("wallet_tracker.auto_unfollow.enabled", True):
            unfollow, reason = should_unfollow(
                current_wr=wr_30d,
                peak_wr=wallet_data["peak_wr"],
                trailing_drop=self.config.get("wallet_tracker.auto_unfollow.trailing_wr_drop", 15),
                consecutive_losses=consecutive,
                max_consecutive=self.config.get("wallet_tracker.auto_unfollow.consecutive_losses", 5),
            )
            if unfollow and await db.get_wallet(address):
                existing = await db.get_wallet(address)
                if existing and existing.get("is_following"):
                    await db.set_wallet_follow(address, False)
                    logger.info(f"Auto-unfollowed {address[:10]}... — {reason}")

        return wallet_data

    async def discover_wallets_from_markets(self, market_ids: list[str]) -> set[str]:
        """Discover wallet addresses from recent trades in given markets."""
        discovered = set()
        for mid in market_ids[:10]:  # Limit to top 10 markets
            trades = await api.get_trades(mid, limit=50)
            for t in trades:
                addr = t.get("user", t.get("maker"))
                if addr:
                    discovered.add(addr)
            await asyncio.sleep(0.2)  # Rate limit spacing
        return discovered

    async def refresh_all_followed(self) -> list[dict]:
        """Re-score all currently followed wallets."""
        followed = await db.get_followed_wallets()
        results = []
        for w in followed:
            result = await self.track_wallet(w["address"])
            if result:
                results.append(result)
            await asyncio.sleep(0.3)
        return results

    async def scan_discover_and_track(self, market_ids: list[str]) -> list[dict]:
        """Full pipeline: discover wallets from markets, then track & score them."""
        addresses = await self.discover_wallets_from_markets(market_ids)

        results = []
        for addr in addresses:
            try:
                result = await self.track_wallet(addr)
                if result and result.get("tier") in ("ELITE", "SMART"):
                    results.append(result)
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Error tracking {addr[:10]}...: {e}")

        # Sort by smart_score descending
        results.sort(key=lambda x: x.get("smart_score", 0), reverse=True)
        return results

    # ── Helpers ──

    @staticmethod
    def _parse_trade_time(trade: dict) -> Optional[datetime]:
        raw = trade.get("timestamp", trade.get("createdAt", trade.get("time")))
        if not raw:
            return None
        try:
            if isinstance(raw, (int, float)):
                return datetime.fromtimestamp(raw / 1000 if raw > 1e12 else raw, tz=timezone.utc)
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _compute_trade_stats(trades: list[dict]) -> tuple[int, int, float]:
        """Return (wins, losses, avg_roi_pct) from a list of trades."""
        wins = 0
        losses = 0
        total_roi = 0.0
        roi_count = 0

        for t in trades:
            side = t.get("side", "").upper()
            outcome = t.get("outcome", "")
            price = float(t.get("price", 0))
            # Polymarket: "Yes" side wins if outcome is positive
            if outcome in ("Yes", "YES", "true", True, 1):
                if side == "BUY":
                    wins += 1
                    roi = ((1.0 - price) / price) * 100 if price > 0 else 0
                else:
                    losses += 1
                    roi = -100
            elif outcome in ("No", "NO", "false", False, 0):
                if side == "BUY":
                    losses += 1
                    roi = -100
                else:
                    wins += 1
                    roi = (price / (1.0 - price)) * 100 if price < 1.0 else 0
            else:
                continue  # Unknown outcome, skip

            total_roi += roi
            roi_count += 1

        avg_roi = (total_roi / roi_count) if roi_count > 0 else 0.0
        return wins, losses, avg_roi

    @staticmethod
    def _count_consecutive_losses(trades: list[dict]) -> int:
        """Count recent consecutive losses."""
        consecutive = 0
        for t in trades:
            outcome = t.get("outcome", "")
            if outcome in ("Yes", "YES", "true", True, 1):
                break
            consecutive += 1
        return consecutive

    @staticmethod
    def _get_last_trade_time(trades: list[dict]) -> Optional[str]:
        if not trades:
            return None
        latest = None
        for t in trades:
            ts = t.get("timestamp", t.get("createdAt"))
            if ts and (latest is None or ts > latest):
                latest = ts
        return str(latest) if latest else None


# Global instance
tracker = WalletTracker()
