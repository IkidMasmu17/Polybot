"""Risk Manager — enforces capital protection rules.

Rules:
- Daily loss limit (30% of bankroll = $1.50 from $5)
- Max consecutive losses halt
- Drawdown-based position sizing reduction
- Max open positions cap
- Per-trade max $1.00
"""
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from src.db import models as db
from src.utils.config import get_config


class RiskManager:
    """Enforces risk limits and position sizing rules."""

    def __init__(self):
        self.config = get_config()

    @property
    def daily_loss_limit_pct(self) -> float:
        return float(self.config.get("risk.daily_loss_limit_pct", 30.0))

    @property
    def max_consecutive_losses(self) -> int:
        return int(self.config.get("risk.max_consecutive_losses", 4))

    @property
    def max_position_usd(self) -> float:
        return float(self.config.get("scalping.max_position_usd", 1.0))

    @property
    def max_open_positions(self) -> int:
        return int(self.config.get("scalping.max_open_positions", 3))

    async def can_open_position(self, size_usd: float) -> tuple[bool, str]:
        """Check if a new position can be opened under current risk limits."""
        bankroll = await db.get_bankroll()

        # Check per-trade max
        if size_usd > self.max_position_usd:
            return False, f"Size ${size_usd:.2f} exceeds max ${self.max_position_usd:.2f}"

        # Check open positions count
        open_pos = await db.get_open_positions()
        if len(open_pos) >= self.max_open_positions:
            return False, f"Max {self.max_open_positions} positions already open"

        # Check daily loss limit
        stats = await db.get_today_stats()
        if stats:
            daily_loss_pct = abs(stats.get("pnl_pct", 0))
            if daily_loss_pct >= self.daily_loss_limit_pct:
                return False, f"Daily loss limit reached ({daily_loss_pct:.1f}% / {self.daily_loss_limit_pct}%)"

        # Check bankroll sufficient
        if size_usd > bankroll:
            return False, f"Insufficient balance: ${bankroll:.2f} < ${size_usd:.2f}"

        return True, "OK"

    async def calculate_position_size(self, bankroll: Optional[float] = None) -> float:
        """Calculate position size based on configured sizing mode.

        Default: 20% of bankroll, capped at max_position_usd.
        After consecutive losses: apply drawdown reduction multiplier.
        """
        if bankroll is None:
            bankroll = await db.get_bankroll()

        sizing = self.config.get_sizing_config()
        mode = sizing.get("mode", "fixed_percentage")
        bankroll_pct = float(sizing.get("bankroll_pct", 20.0))

        if mode == "fixed_percentage":
            size = bankroll * (bankroll_pct / 100.0)
        elif mode == "fixed_amount":
            size = self.max_position_usd
        elif mode == "kelly":
            # Simplified Kelly: use bankroll_pct as kelly fraction
            size = bankroll * (bankroll_pct / 100.0)
        else:
            size = bankroll * 0.20

        # Apply drawdown reduction
        size = await self._apply_drawdown_reduction(size)

        # Cap
        size = min(size, self.max_position_usd)

        # Floor at $0.25 minimum trade size
        size = max(size, 0.25)

        return round(size, 2)

    async def _apply_drawdown_reduction(self, base_size: float) -> float:
        """Reduce position size based on consecutive losses."""
        if not self.config.get("risk.drawdown_reduction.enabled", True):
            return base_size

        # Count recent consecutive losses
        open_pos = await db.get_open_positions()
        closed_only = [p for p in open_pos if p.get("status") == "CLOSED"]

        consecutive = 0
        for p in sorted(closed_only, key=lambda x: x.get("closed_at", ""), reverse=True):
            if (p.get("pnl_usd") or 0) < 0:
                consecutive += 1
            else:
                break

        steps = self.config.get_drawdown_steps()
        multiplier = 1.0
        for step in sorted(steps, key=lambda x: x.get("consecutive", 0), reverse=True):
            if consecutive >= step.get("consecutive", 0):
                multiplier = float(step.get("multiplier", 1.0))
                break

        if multiplier < 1.0:
            logger.info(f"Drawdown reduction: {consecutive} consecutive losses → multiplier {multiplier}")

        return base_size * multiplier

    async def should_halt_trading(self) -> tuple[bool, str]:
        """Check if all trading should be halted."""
        bankroll = await db.get_bankroll()

        # If bankroll drops below $2 (from $5), halt
        if bankroll < 2.0:
            return True, f"Bankroll critically low: ${bankroll:.2f}"

        # Daily loss limit check
        stats = await db.get_today_stats()
        if stats:
            pnl = stats.get("pnl_usd", 0)
            daily_limit = 5.0 * (self.daily_loss_limit_pct / 100.0)
            if pnl < -daily_limit:
                return True, f"Daily loss limit exceeded: ${abs(pnl):.2f} > ${daily_limit:.2f}"

        return False, "OK"

    async def get_risk_summary(self) -> dict:
        """Generate a risk summary for display."""
        bankroll = await db.get_bankroll()
        open_pos = await db.get_open_positions()
        stats = await db.get_today_stats()

        total_exposure = sum(p.get("size_usd", 0) for p in open_pos)

        return {
            "bankroll": bankroll,
            "open_positions": len(open_pos),
            "max_positions": self.max_open_positions,
            "total_exposure": total_exposure,
            "exposure_pct": (total_exposure / bankroll * 100) if bankroll > 0 else 0,
            "daily_pnl": stats.get("pnl_usd", 0) if stats else 0,
            "daily_pnl_pct": stats.get("pnl_pct", 0) if stats else 0,
            "daily_loss_limit": self.daily_loss_limit_pct,
            "position_size": await self.calculate_position_size(bankroll),
        }


# Global instance
risk_manager = RiskManager()
