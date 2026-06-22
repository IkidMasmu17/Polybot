"""Position Manager — monitors open positions, enforces TP/SL, and tracks PnL."""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger

from src.api.polymarket_api import api
from src.db import models as db
from src.utils.config import get_config


class PositionManager:
    """Manages open positions: TP/SL enforcement, time-based closure, PnL tracking."""

    def __init__(self):
        self.config = get_config()

    async def monitor_positions(self):
        """Check all open positions against TP/SL and time limits."""
        positions = await db.get_open_positions()
        if not positions:
            return

        for pos in positions:
            try:
                await self._check_position(pos)
            except Exception as e:
                logger.error(f"Error monitoring position {pos['id']}: {e}")

    async def _check_position(self, pos: dict):
        """Check a single position for TP/SL/time conditions."""
        pos_id = pos["id"]
        market_id = pos["market_id"]
        side = pos["side"]
        entry_price = pos["entry_price"]
        tp_pct = pos.get("profit_target_pct", 8.0)
        sl_pct = pos.get("stop_loss_pct", 5.0)
        time_limit = pos.get("time_limit_minutes", 90)

        # Get current price
        current_price = await api.get_midpoint_price(market_id)
        if current_price is None:
            # Try market-specific endpoint
            market = await db.get_market(market_id)
            if market:
                current_price = market.get("yes_price") if side == "YES" else market.get("no_price")
            if current_price is None:
                return  # Can't determine price, skip

        # Update current price in DB
        await db.get_connection()
        conn = await db.get_connection()
        try:
            await conn.execute("UPDATE positions SET current_price=? WHERE id=?", (current_price, pos_id))
            await conn.commit()
        finally:
            await conn.close()

        pnl_pct = self._calc_pnl_pct(entry_price, current_price, side)
        should_close = False
        reason = ""

        # Check TP
        if pnl_pct >= tp_pct:
            should_close = True
            reason = f"TP hit: +{pnl_pct:.1f}% (target: +{tp_pct:.1f}%)"

        # Check SL
        elif pnl_pct <= -sl_pct:
            should_close = True
            reason = f"SL hit: {pnl_pct:.1f}% (limit: -{sl_pct:.1f}%)"

        # Check time limit
        elif pos.get("opened_at"):
            opened = self._parse_time(pos["opened_at"])
            if opened:
                elapsed = (datetime.now(timezone.utc) - opened).total_seconds() / 60
                if elapsed >= time_limit:
                    should_close = True
                    reason = f"Time limit reached: {elapsed:.0f} min (limit: {time_limit} min)"

        if should_close:
            pnl_usd = (pnl_pct / 100) * pos["size_usd"]
            await db.close_position(pos_id, current_price, pnl_usd, pnl_pct)

            # Update bankroll
            bankroll = await db.get_bankroll()
            new_balance = bankroll + pnl_usd
            await db.update_bankroll(new_balance)

            logger.info(f"Position #{pos_id} closed — {reason} | PnL: ${pnl_usd:+.2f}")
            return True

        return False

    async def close_position_manual(self, pos_id: int) -> Optional[dict]:
        """Manually close a position at current market price."""
        pos = await db.get_position(pos_id)
        if not pos:
            return None

        market_id = pos["market_id"]
        side = pos["side"]
        entry_price = pos["entry_price"]

        current_price = await api.get_midpoint_price(market_id)
        if current_price is None:
            return None

        pnl_pct = self._calc_pnl_pct(entry_price, current_price, side)
        pnl_usd = (pnl_pct / 100) * pos["size_usd"]

        await db.close_position(pos_id, current_price, pnl_usd, pnl_pct)

        # Update bankroll
        bankroll = await db.get_bankroll()
        new_balance = bankroll + pnl_usd
        await db.update_bankroll(new_balance)

        return {
            "position_id": pos_id,
            "exit_price": current_price,
            "pnl_usd": pnl_usd,
            "pnl_pct": pnl_pct,
        }

    @staticmethod
    def _calc_pnl_pct(entry: float, current: float, side: str) -> float:
        """Calculate unrealized PnL percentage."""
        if entry == 0:
            return 0.0
        if side.upper() == "YES":
            return ((current - entry) / entry) * 100
        else:
            return ((entry - current) / entry) * 100

    @staticmethod
    def _parse_time(ts: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    async def get_pnl_summary(self) -> dict:
        """Generate a PnL summary for the /pnl command."""
        bankroll = await db.get_bankroll()
        positions = await db.get_open_positions()
        stats = await db.get_today_stats()

        unrealized_pnl = 0.0
        for p in positions:
            if p.get("current_price") and p.get("entry_price"):
                pnl_pct = self._calc_pnl_pct(p["entry_price"], p["current_price"], p["side"])
                unrealized_pnl += (pnl_pct / 100) * p["size_usd"]

        return {
            "bankroll": bankroll,
            "starting_capital": 5.00,
            "total_pnl": bankroll - 5.00,
            "total_pnl_pct": ((bankroll - 5.00) / 5.00) * 100,
            "today_pnl": stats.get("pnl_usd", 0) if stats else 0,
            "today_pnl_pct": stats.get("pnl_pct", 0) if stats else 0,
            "open_positions": len(positions),
            "unrealized_pnl": round(unrealized_pnl, 2),
        }


# Global instance
position_manager = PositionManager()
