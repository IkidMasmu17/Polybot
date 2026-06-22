"""Polymarket API client — market data, trades, CLOB order execution."""
import asyncio
import os
import time
from typing import Optional

import aiohttp
import httpx
from loguru import logger

from src.utils.config import get_config

# Endpoints
GAMMA_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"
DATA_URL = "https://data-api.polymarket.com"


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, max_rps: int = 10):
        self.max_rps = max_rps
        self.tokens = max_rps
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_rps, self.tokens + elapsed * self.max_rps)
            self.last_refill = now
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.max_rps
                await asyncio.sleep(wait)
                self.tokens = 1
            self.tokens -= 1


class PolymarketAPI:
    """Async wrapper around Polymarket APIs (Gamma, CLOB, Data)."""

    def __init__(self):
        config = get_config()
        self.rate_limiter = RateLimiter(
            int(os.getenv("API_RATE_LIMIT_RPS", config.get("api_rate_limit_rps", 10)))
        )
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "PolyBot/1.0"},
                timeout=aiohttp.ClientTimeout(total=30),
            )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, url: str, params: dict = None) -> dict | list:
        await self.rate_limiter.acquire()
        await self._ensure_session()
        async with self._session.get(url, params=params) as resp:
            if resp.status == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                await asyncio.sleep(retry_after)
                return await self._get(url, params)
            resp.raise_for_status()
            return await resp.json()

    # ── Gamma Markets API (read-only, no auth) ──

    async def get_markets(
        self,
        tag: str = "soccer",
        active: bool = True,
        liquidity_min: float = 500,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch markets from Gamma API with filters."""
        params = {
            "tag": tag,
            "active": str(active).lower(),
            "liquidity_min": liquidity_min,
            "limit": limit,
            "order": "liquidity",
            "ascending": False,
        }
        try:
            result = await self._get(f"{GAMMA_URL}/markets", params)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Gamma API error: {e}")
            return []

    async def get_market(self, market_id: str) -> Optional[dict]:
        """Get single market details."""
        try:
            result = await self._get(f"{GAMMA_URL}/markets/{market_id}")
            return result
        except Exception as e:
            logger.error(f"Gamma market detail error: {e}")
            return None

    # ── Data API (trades, prices) ──

    async def get_trades(
        self, market_id: str, limit: int = 100
    ) -> list[dict]:
        """Fetch recent trades for a market."""
        try:
            return await self._get(
                f"{DATA_URL}/trades",
                {"market": market_id, "limit": limit},
            )
        except Exception as e:
            logger.error(f"Data API trades error: {e}")
            return []

    async def get_wallet_trades(
        self, wallet_address: str, limit: int = 50
    ) -> list[dict]:
        """Fetch trades made by a specific wallet address."""
        try:
            # Polymarket data API supports filtering by user
            result = await self._get(
                f"{DATA_URL}/trades",
                {"user": wallet_address, "limit": limit},
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Wallet trades error: {e}")
            return []

    async def get_prices(self, market_id: str) -> Optional[dict]:
        """Get current prices (bid/ask) for a market from CLOB."""
        try:
            # CLOB price endpoint
            result = await self._get(
                f"{CLOB_URL}/book",
                {"token_id": market_id},
            )
            return result
        except Exception as e:
            logger.error(f"CLOB price error: {e}")
            return None

    async def get_midpoint_price(self, token_id: str) -> Optional[float]:
        """Get the midpoint price from the CLOB order book."""
        try:
            book = await self._get(f"{CLOB_URL}/book", {"token_id": token_id})
            if not book:
                return None
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            if bids and asks:
                best_bid = float(bids[0].get("price", 0))
                best_ask = float(asks[0].get("price", 0))
                return (best_bid + best_ask) / 2
            return None
        except Exception:
            return None


# Global instance
api = PolymarketAPI()
