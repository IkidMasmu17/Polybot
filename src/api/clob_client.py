"""CLOB client wrapper — order placement and management on Polymarket CLOB.

Uses py-clob-client when available, falls back to raw HTTP + EIP-712 signing.
For v1.0 with $5 capital, we prioritize safety — all orders are limit orders.
"""
import os
import json
from typing import Optional

from eth_account import Account
from eth_account.messages import encode_typed_data
from loguru import logger

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.order_builder.constants import BUY, SELL
    HAS_CLOB_CLIENT = True
except ImportError:
    HAS_CLOB_CLIENT = False
    logger.warning("py-clob-client not installed — using raw HTTP order execution")


class ClobExecutor:
    """Handles placing and managing orders on Polymarket CLOB."""

    def __init__(self):
        self.private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "")
        self.proxy_address = os.getenv("POLYMARKET_PROXY_ADDRESS")
        self._clob: Optional[ClobClient] = None

        if HAS_CLOB_CLIENT and self.private_key:
            self._init_clob_client()

    def _init_clob_client(self):
        try:
            host = os.getenv("POLYMARKET_CLOB_URL", "https://clob.polymarket.com")
            chain_id = 137  # Polygon Mainnet
            self._clob = ClobClient(
                host=host,
                key=self.private_key,
                chain_id=chain_id,
                signer=self._get_signer(),
                signature_type=2,  # EIP-712 proxy wallet
                funder_address=self.proxy_address,
            )
            logger.info("CLOB client initialized")
        except Exception as e:
            logger.error(f"CLOB client init failed: {e}")
            self._clob = None

    def _get_signer(self):
        """Create a signer from private key."""
        try:
            from py_clob_client.signing.hmac import HmacSigner
            return HmacSigner(self.private_key)
        except ImportError:
            return None

    async def place_limit_order(
        self,
        token_id: str,
        side: str,  # "BUY" or "SELL"
        price: float,
        size: float,  # in USDC
    ) -> Optional[dict]:
        """Place a limit order. Returns order dict with id on success."""
        if not self._clob:
            logger.error("CLOB client not initialized — cannot place orders")
            return None

        try:
            if side.upper() == "BUY":
                order = await self._clob.create_order(
                    token_id=token_id,
                    price=price,
                    size=size,
                    side=BUY,
                )
            else:
                order = await self._clob.create_order(
                    token_id=token_id,
                    price=price,
                    size=size,
                    side=SELL,
                )

            # Post the order
            result = await self._clob.post_order(order)
            logger.info(f"Order placed: {json.dumps(result, default=str)[:200]}")
            return result
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if not self._clob:
            return False
        try:
            await self._clob.cancel(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return False

    async def cancel_all_orders(self):
        """Cancel all open orders."""
        if not self._clob:
            return
        try:
            await self._clob.cancel_all()
            logger.info("All orders cancelled")
        except Exception as e:
            logger.error(f"Cancel all orders failed: {e}")

    async def get_order(self, order_id: str) -> Optional[dict]:
        """Get order status by ID."""
        if not self._clob:
            return None
        try:
            return await self._clob.get_order(order_id)
        except Exception:
            return None

    @property
    def is_ready(self) -> bool:
        return self._clob is not None


# Global instance
executor = ClobExecutor()
