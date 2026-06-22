"""Market Scanner — discovers and filters Polymarket betting markets.

Focus: World Cup 2026 (soccer), expandable to other sports.
Filters: liquidity, volume, spread, upcoming match window.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger

from src.api.polymarket_api import api
from src.db import models as db
from src.utils.config import get_config


class MarketScanner:
    """Scans Polymarket for tradable markets matching configured filters."""

    def __init__(self):
        self.config = get_config()

    @property
    def sport_tags(self) -> list[str]:
        return self.config.get("scanner.sport_categories", ["soccer"])

    @property
    def min_liquidity(self) -> float:
        return float(self.config.get("scanner.min_liquidity_usd", 500))

    @property
    def min_volume(self) -> float:
        return float(self.config.get("scanner.min_volume_24h_usd", 200))

    @property
    def max_spread(self) -> float:
        return float(self.config.get("scanner.max_spread_pct", 5.0))

    @property
    def upcoming_hours(self) -> int:
        return int(self.config.get("scanner.upcoming_window_hours", 2))

    async def scan_all(self) -> list[dict]:
        """Scan all configured sport categories and return filtered markets."""
        all_markets = []
        for tag in self.sport_tags:
            markets = await self._scan_tag(tag)
            all_markets.extend(markets)
            logger.info(f"Scanned '{tag}': {len(markets)} qualifying markets")
        return all_markets

    async def _scan_tag(self, tag: str) -> list[dict]:
        """Scan a single sport tag. Returns filtered markets."""
        raw_markets = await api.get_markets(
            tag=tag,
            active=True,
            liquidity_min=self.min_liquidity,
            limit=100,
        )

        filtered = []
        for m in raw_markets:
            if not self._passes_filters(m):
                continue

            # Normalize market data
            market_data = self._normalize(m, tag)
            await db.upsert_market(market_data)
            filtered.append(market_data)

        return filtered

    def _passes_filters(self, market: dict) -> bool:
        """Apply all configured filters to a market."""
        # Volume check
        volume = float(market.get("volume24hr", market.get("volume", 0)))
        if volume < self.min_volume:
            return False

        # Spread check (if bid/ask available)
        best_bid = float(market.get("bestBid", 0) or 0)
        best_ask = float(market.get("bestAsk", 0) or 0)
        if best_bid > 0 and best_ask > 0:
            spread_pct = ((best_ask - best_bid) / best_ask) * 100
            if spread_pct > self.max_spread:
                return False

        # Upcoming window check
        close_time_str = market.get("endDate", market.get("closeTime"))
        if close_time_str:
            try:
                close_time = self._parse_time(close_time_str)
                now = datetime.now(timezone.utc)
                if close_time < now:
                    return False  # Already closed
                if (close_time - now) > timedelta(hours=self.upcoming_hours + 48):
                    # Too far in the future (allow 48h buffer for pre-match)
                    return False
            except (ValueError, TypeError):
                pass  # Can't parse time, include it

        return True

    def _normalize(self, raw: dict, sport_tag: str) -> dict:
        """Convert raw API response to our database format."""
        best_bid = float(raw.get("bestBid", 0) or 0)
        best_ask = float(raw.get("bestAsk", 0) or 0)
        spread = 0.0
        if best_bid > 0 and best_ask > 0:
            spread = ((best_ask - best_bid) / best_ask) * 100

        # Determine tournament from tags or description
        tournament = None
        raw_tags = raw.get("tags", [])
        if raw_tags:
            tournament = raw_tags[0].get("label") if isinstance(raw_tags[0], dict) else str(raw_tags[0])

        return {
            "id": raw.get("id", ""),
            "question": raw.get("question", raw.get("title", "")),
            "slug": raw.get("slug"),
            "sport_tag": sport_tag,
            "tournament": tournament,
            "yes_price": float(raw.get("outcomePrices", [0.5, 0.5])[0]) if raw.get("outcomePrices") else 0.5,
            "no_price": float(raw.get("outcomePrices", [0.5, 0.5])[1]) if raw.get("outcomePrices") else 0.5,
            "liquidity": float(raw.get("liquidity", 0)),
            "volume_24h": float(raw.get("volume24hr", raw.get("volume", 0))),
            "spread_pct": spread,
            "close_time": raw.get("endDate", raw.get("closeTime")),
            "status": "active",
            "raw_json": str(raw),
        }

    @staticmethod
    def _parse_time(time_str: str) -> datetime:
        """Parse various timestamp formats from Polymarket."""
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(time_str.replace("Z", "+00:00"), fmt)
            except ValueError:
                continue
        # Fallback: try ISO format
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))

    async def get_market_summary(self, market_id: str) -> Optional[dict]:
        """Get detailed summary of a specific market for display."""
        market = await db.get_market(market_id)
        if not market:
            m = await api.get_market(market_id)
            if m:
                market = self._normalize(m, m.get("tag", "soccer"))
        return market


# Global instance
scanner = MarketScanner()
