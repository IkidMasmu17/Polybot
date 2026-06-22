"""Copy Trade Engine — monitors smart wallets and generates copy-trade signals.

Mode: Semi-Auto (default v1.0)
- Detects new trades from followed smart wallets
- Sends signal to Telegram with [COPY] button
- User confirms with 1-tap → engine executes the trade
"""
from typing import Optional

from loguru import logger

from src.api.polymarket_api import api
from src.api.clob_client import executor
from src.db import models as db
from src.trade.risk_manager import risk_manager
from src.utils.config import get_config


class CopyTradeEngine:
    """Detects wallet trades, generates signals, executes copy trades."""

    def __init__(self):
        self.config = get_config()
        self._known_trades: set[str] = set()  # Track already-seen trades

    async def detect_new_signals(self) -> list[dict]:
        """Check followed wallets for new trades and return signals."""
        wallets = await db.get_smart_wallets(
            min_score=self.config.get("copy_trade.min_confidence_score", 70)
        )

        signals = []
        for wallet in wallets:
            try:
                trades = await api.get_wallet_trades(wallet["address"], limit=10)
                for trade in trades:
                    trade_id = trade.get("id", trade.get("transactionHash"))
                    if trade_id and trade_id in self._known_trades:
                        continue
                    if trade_id:
                        self._known_trades.add(trade_id)

                    signal = self._parse_signal(wallet, trade)
                    if signal:
                        signals.append(signal)
                        await db.log_signal(
                            wallet["address"],
                            signal["market_id"],
                            signal["side"],
                            signal["price"],
                            "DETECTED",
                        )
            except Exception as e:
                logger.error(f"Signal detection error for {wallet['address'][:10]}...: {e}")

        # Keep known_trades bounded
        if len(self._known_trades) > 1000:
            self._known_trades = set(list(self._known_trades)[-500:])

        return signals

    def _parse_signal(self, wallet: dict, trade: dict) -> Optional[dict]:
        """Parse a trade into a copy-trade signal."""
        side = trade.get("side", "").upper()
        if side not in ("BUY", "SELL"):
            return None

        market_id = trade.get("market", trade.get("conditionId"))
        if not market_id:
            return None

        price = float(trade.get("price", 0))
        if price <= 0:
            return None

        return {
            "wallet_address": wallet["address"],
            "wallet_tier": wallet.get("tier", "SMART"),
            "wallet_wr": wallet.get("win_rate_30d", 0),
            "wallet_trades": wallet.get("total_trades", 0),
            "wallet_score": wallet.get("smart_score", 0),
            "market_id": market_id,
            "market_question": trade.get("title", ""),
            "side": "YES" if side == "BUY" else "NO",
            "price": price,
            "size": float(trade.get("size", 0)),
            "trade_id": trade.get("id", trade.get("transactionHash")),
        }

    async def execute_copy(
        self,
        signal: dict,
        size_usd: Optional[float] = None,
    ) -> Optional[dict]:
        """Execute a copy trade based on a signal.

        Args:
            signal: The trade signal dict from detect_new_signals()
            size_usd: Override position size (None = use calculated size)

        Returns:
            Result dict with position_id and order details
        """
        # Risk check
        if size_usd is None:
            size_usd = await risk_manager.calculate_position_size()

        can_open, reason = await risk_manager.can_open_position(size_usd)
        if not can_open:
            logger.warning(f"Trade blocked by risk: {reason}")
            return {"error": reason}

        # Get market details
        market = await db.get_market(signal["market_id"])
        if not market:
            # Try fetching
            from src.scanner.market_scanner import scanner
            market = await scanner.get_market_summary(signal["market_id"])

        entry_price = signal["price"]
        shares = size_usd / entry_price if entry_price > 0 else 0

        # Place limit order
        tp_pct = float(await db.get_setting("profit_target_pct", "8.0"))
        sl_pct = float(await db.get_setting("stop_loss_pct", "5.0"))

        order_id = None
        if executor.is_ready:
            result = await executor.place_limit_order(
                token_id=signal["market_id"],
                side="BUY" if signal["side"] == "YES" else "SELL",
                price=entry_price,
                size=size_usd,
            )
            if result:
                order_id = result.get("orderID", result.get("id"))

        # Record position in DB
        pos_id = await db.create_position({
            "market_id": signal["market_id"],
            "market_question": signal.get("market_question", market.get("question", "") if market else ""),
            "side": signal["side"],
            "entry_price": entry_price,
            "size_usd": size_usd,
            "shares": shares,
            "profit_target_pct": tp_pct,
            "stop_loss_pct": sl_pct,
            "copied_from": signal["wallet_address"],
            "order_id": order_id,
        })

        logger.info(
            f"Copy trade executed: #{pos_id} | {signal['side']} @ ${entry_price:.4f} "
            f"| Size: ${size_usd:.2f} | From: {signal['wallet_address'][:10]}..."
        )

        return {
            "position_id": pos_id,
            "order_id": order_id,
            "market_id": signal["market_id"],
            "side": signal["side"],
            "entry_price": entry_price,
            "size_usd": size_usd,
            "shares": shares,
            "wallet_source": signal["wallet_address"][:10] + "...",
        }

    async def skip_signal(self, signal: dict):
        """Log a skipped signal."""
        await db.log_signal(
            signal["wallet_address"],
            signal["market_id"],
            signal["side"],
            signal["price"],
            "SKIPPED",
        )


# Global instance
copy_engine = CopyTradeEngine()
