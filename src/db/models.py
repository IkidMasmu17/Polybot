"""Data access layer — async CRUD operations for all entities."""
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from .database import get_connection


# ──────────────────────────────────────────────
# Markets
# ──────────────────────────────────────────────

async def upsert_market(market_data: dict):
    conn = await get_connection()
    try:
        await conn.execute(
            """
            INSERT INTO markets (id, question, slug, sport_tag, tournament, yes_price, no_price,
                liquidity, volume_24h, spread_pct, close_time, status, first_seen, last_updated, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?)
            ON CONFLICT(id) DO UPDATE SET
                yes_price=excluded.yes_price, no_price=excluded.no_price,
                liquidity=excluded.liquidity, volume_24h=excluded.volume_24h,
                spread_pct=excluded.spread_pct, status=excluded.status,
                last_updated=datetime('now'), raw_json=excluded.raw_json
            """,
            (
                market_data.get("id"),
                market_data.get("question"),
                market_data.get("slug"),
                market_data.get("sport_tag", "soccer"),
                market_data.get("tournament"),
                market_data.get("yes_price", 0.5),
                market_data.get("no_price", 0.5),
                market_data.get("liquidity", 0),
                market_data.get("volume_24h", 0),
                market_data.get("spread_pct", 0),
                market_data.get("close_time"),
                market_data.get("status", "active"),
                market_data.get("raw_json"),
            ),
        )
        await conn.commit()
    finally:
        await conn.close()


async def get_active_markets(sport_tag: Optional[str] = None, limit: int = 50) -> list[dict]:
    conn = await get_connection()
    try:
        if sport_tag:
            cursor = await conn.execute(
                "SELECT * FROM markets WHERE status='active' AND sport_tag=? ORDER BY liquidity DESC LIMIT ?",
                (sport_tag, limit),
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM markets WHERE status='active' ORDER BY liquidity DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_market(market_id: str) -> Optional[dict]:
    conn = await get_connection()
    try:
        cursor = await conn.execute("SELECT * FROM markets WHERE id=?", (market_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


# ──────────────────────────────────────────────
# Wallets
# ──────────────────────────────────────────────

async def upsert_wallet(wallet_data: dict):
    conn = await get_connection()
    try:
        await conn.execute(
            """
            INSERT INTO wallets (address, win_rate_30d, win_rate_90d, avg_roi_pct, smart_score,
                tier, total_trades, wins_30d, losses_30d, peak_wr, consecutive_losses,
                last_trade_at, last_checked, is_following)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
            ON CONFLICT(address) DO UPDATE SET
                win_rate_30d=excluded.win_rate_30d, win_rate_90d=excluded.win_rate_90d,
                avg_roi_pct=excluded.avg_roi_pct, smart_score=excluded.smart_score,
                tier=excluded.tier, total_trades=excluded.total_trades,
                wins_30d=excluded.wins_30d, losses_30d=excluded.losses_30d,
                peak_wr=MAX(peak_wr, excluded.peak_wr),
                consecutive_losses=excluded.consecutive_losses,
                last_trade_at=excluded.last_trade_at, last_checked=datetime('now'),
                is_following=excluded.is_following
            """,
            (
                wallet_data.get("address"),
                wallet_data.get("win_rate_30d", 0),
                wallet_data.get("win_rate_90d", 0),
                wallet_data.get("avg_roi_pct", 0),
                wallet_data.get("smart_score", 0),
                wallet_data.get("tier", "WATCH"),
                wallet_data.get("total_trades", 0),
                wallet_data.get("wins_30d", 0),
                wallet_data.get("losses_30d", 0),
                wallet_data.get("peak_wr", 0),
                wallet_data.get("consecutive_losses", 0),
                wallet_data.get("last_trade_at"),
                wallet_data.get("is_following", 0),
            ),
        )
        await conn.commit()
    finally:
        await conn.close()


async def get_smart_wallets(min_score: float = 70, limit: int = 20) -> list[dict]:
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """SELECT * FROM wallets
               WHERE tier IN ('ELITE', 'SMART') AND is_following=1
               ORDER BY smart_score DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_followed_wallets() -> list[dict]:
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            "SELECT * FROM wallets WHERE is_following=1 ORDER BY smart_score DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def set_wallet_follow(address: str, follow: bool):
    conn = await get_connection()
    try:
        await conn.execute(
            "UPDATE wallets SET is_following=? WHERE address=?",
            (1 if follow else 0, address),
        )
        await conn.commit()
    finally:
        await conn.close()


async def get_wallet(address: str) -> Optional[dict]:
    conn = await get_connection()
    try:
        cursor = await conn.execute("SELECT * FROM wallets WHERE address=?", (address,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


# ──────────────────────────────────────────────
# Positions
# ──────────────────────────────────────────────

async def create_position(data: dict) -> int:
    conn = await get_connection()
    try:
        cursor = await conn.execute(
            """
            INSERT INTO positions (market_id, market_question, side, entry_price, current_price,
                size_usd, shares, status, profit_target_pct, stop_loss_pct,
                time_limit_minutes, opened_at, copied_from, order_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, datetime('now'), ?, ?)
            """,
            (
                data.get("market_id"),
                data.get("market_question"),
                data.get("side"),
                data.get("entry_price"),
                data.get("entry_price"),
                data.get("size_usd"),
                data.get("shares", 0),
                data.get("profit_target_pct", 8.0),
                data.get("stop_loss_pct", 5.0),
                data.get("time_limit_minutes", 90),
                data.get("copied_from"),
                data.get("order_id"),
            ),
        )
        await conn.commit()
        return cursor.lastrowid
    finally:
        await conn.close()


async def close_position(position_id: int, exit_price: float, pnl_usd: float, pnl_pct: float):
    conn = await get_connection()
    try:
        await conn.execute(
            """
            UPDATE positions SET status='CLOSED', current_price=?, closed_at=datetime('now'),
                pnl_usd=?, pnl_pct=?
            WHERE id=?
            """,
            (exit_price, pnl_usd, pnl_pct, position_id),
        )
        await conn.commit()
    finally:
        await conn.close()


async def get_open_positions() -> list[dict]:
    conn = await get_connection()
    try:
        cursor = await conn.execute("SELECT * FROM positions WHERE status='OPEN'")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_position(position_id: int) -> Optional[dict]:
    conn = await get_connection()
    try:
        cursor = await conn.execute("SELECT * FROM positions WHERE id=?", (position_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


# ──────────────────────────────────────────────
# Settings
# ──────────────────────────────────────────────

async def get_setting(key: str, default: str = "") -> str:
    conn = await get_connection()
    try:
        cursor = await conn.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else default
    finally:
        await conn.close()


async def set_setting(key: str, value: str):
    conn = await get_connection()
    try:
        await conn.execute(
            """INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')""",
            (key, value),
        )
        await conn.commit()
    finally:
        await conn.close()


async def get_bankroll() -> float:
    val = await get_setting("bankroll", "5.00")
    return float(val)


async def update_bankroll(new_balance: float):
    await set_setting("bankroll", f"{new_balance:.2f}")


# ──────────────────────────────────────────────
# Daily Stats
# ──────────────────────────────────────────────

async def get_today_stats() -> Optional[dict]:
    conn = await get_connection()
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor = await conn.execute("SELECT * FROM daily_stats WHERE date=?", (today,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def update_daily_stats(data: dict):
    conn = await get_connection()
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await conn.execute(
            """INSERT INTO daily_stats (date, starting_balance, ending_balance, total_trades,
                wins, losses, pnl_usd, pnl_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                ending_balance=excluded.ending_balance, total_trades=excluded.total_trades,
                wins=excluded.wins, losses=excluded.losses,
                pnl_usd=excluded.pnl_usd, pnl_pct=excluded.pnl_pct""",
            (
                today,
                data.get("starting_balance", 5.0),
                data.get("ending_balance", 5.0),
                data.get("total_trades", 0),
                data.get("wins", 0),
                data.get("losses", 0),
                data.get("pnl_usd", 0),
                data.get("pnl_pct", 0),
            ),
        )
        await conn.commit()
    finally:
        await conn.close()


# ──────────────────────────────────────────────
# Signals Log
# ──────────────────────────────────────────────

async def log_signal(wallet_address: str, market_id: str, side: str, price: float, action: str):
    conn = await get_connection()
    try:
        await conn.execute(
            "INSERT INTO signals_log (wallet_address, market_id, side, price, action, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (wallet_address, market_id, side, price, action),
        )
        await conn.commit()
    finally:
        await conn.close()
