"""Async SQLite database connection and schema management."""
import aiosqlite
from pathlib import Path

from loguru import logger

from src.utils.config import get_config

DB_PATH: str = ""


async def get_db_path() -> str:
    global DB_PATH
    if not DB_PATH:
        config = get_config()
        db_rel = config.get("database.path", "data/polybot.db")
        db_path = Path(db_rel)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        DB_PATH = str(db_path.resolve())
    return DB_PATH


async def get_connection() -> aiosqlite.Connection:
    """Get an async SQLite connection with WAL mode and foreign keys enabled."""
    db_path = await get_db_path()
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def init_db():
    """Create all tables if they don't exist."""
    conn = await get_connection()
    try:
        await conn.executescript(SCHEMA)
        await conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        await conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS markets (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    slug TEXT,
    sport_tag TEXT DEFAULT 'soccer',
    tournament TEXT,
    yes_price REAL DEFAULT 0.5,
    no_price REAL DEFAULT 0.5,
    liquidity REAL DEFAULT 0.0,
    volume_24h REAL DEFAULT 0.0,
    spread_pct REAL DEFAULT 0.0,
    close_time TEXT,
    status TEXT DEFAULT 'active',
    first_seen TEXT,
    last_updated TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS wallets (
    address TEXT PRIMARY KEY,
    win_rate_30d REAL DEFAULT 0.0,
    win_rate_90d REAL DEFAULT 0.0,
    avg_roi_pct REAL DEFAULT 0.0,
    smart_score REAL DEFAULT 0.0,
    tier TEXT DEFAULT 'WATCH',
    total_trades INTEGER DEFAULT 0,
    wins_30d INTEGER DEFAULT 0,
    losses_30d INTEGER DEFAULT 0,
    peak_wr REAL DEFAULT 0.0,
    consecutive_losses INTEGER DEFAULT 0,
    last_trade_at TEXT,
    last_checked TEXT,
    is_following INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS wallet_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT NOT NULL,
    market_id TEXT,
    side TEXT,
    price REAL,
    shares REAL,
    outcome TEXT,
    profit_loss REAL,
    trade_time TEXT,
    FOREIGN KEY (wallet_address) REFERENCES wallets(address)
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    market_question TEXT,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    size_usd REAL NOT NULL,
    shares REAL DEFAULT 0.0,
    status TEXT DEFAULT 'OPEN',
    profit_target_pct REAL DEFAULT 8.0,
    stop_loss_pct REAL DEFAULT 5.0,
    time_limit_minutes INTEGER DEFAULT 90,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    pnl_usd REAL,
    pnl_pct REAL,
    copied_from TEXT,
    order_id TEXT,
    FOREIGN KEY (market_id) REFERENCES markets(id),
    FOREIGN KEY (copied_from) REFERENCES wallets(address)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,
    starting_balance REAL,
    ending_balance REAL,
    total_trades INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    pnl_usd REAL DEFAULT 0.0,
    pnl_pct REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS signals_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT,
    market_id TEXT,
    side TEXT,
    price REAL,
    action TEXT,
    created_at TEXT
);

-- Default settings
INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES
    ('bankroll', '5.00', datetime('now')),
    ('profit_target_pct', '8.0', datetime('now')),
    ('stop_loss_pct', '5.0', datetime('now')),
    ('max_position_usd', '1.00', datetime('now')),
    ('tier_mode', 'STANDAR', datetime('now')),
    ('alert_level', 'STANDAR', datetime('now'));
"""
