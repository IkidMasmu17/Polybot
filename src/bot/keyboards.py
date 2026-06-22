"""Inline keyboards for Telegram bot interactions."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def copy_trade_keyboard(signal: dict) -> InlineKeyboardMarkup:
    """Generate the copy trade confirmation keyboard with sizing options."""
    wallet_short = signal.get("wallet_address", "")[:10] + "..."
    tier_emoji = "🟢" if signal.get("wallet_tier") == "ELITE" else "🟡"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ COPY $1.00", callback_data=f"copy_{signal['trade_id']}_1.00"),
            InlineKeyboardButton("⚡ COPY $0.50", callback_data=f"copy_{signal['trade_id']}_0.50"),
        ],
        [
            InlineKeyboardButton("📊 Lihat Wallet", callback_data=f"wallet_{signal['wallet_address']}"),
            InlineKeyboardButton("❌ Skip", callback_data=f"skip_{signal['trade_id']}"),
        ],
    ])


def market_detail_keyboard(market_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Detail Market", callback_data=f"market_{market_id}"),
            InlineKeyboardButton("🔍 Scan Wallets", callback_data=f"scanwallets_{market_id}"),
        ],
    ])


def wallet_action_keyboard(address: str, is_following: bool) -> InlineKeyboardMarkup:
    action = "Unfollow" if is_following else "Follow"
    emoji = "🔕" if is_following else "👁️"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{emoji} {action}", callback_data=f"follow_{address}"),
            InlineKeyboardButton("📊 Detail", callback_data=f"wallet_{address}"),
        ],
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Profit Target", callback_data="set_tp")],
        [InlineKeyboardButton("🛑 Stop Loss", callback_data="set_sl")],
        [InlineKeyboardButton("💰 Position Size", callback_data="set_size")],
        [InlineKeyboardButton("📊 Tier Mode", callback_data="set_tier")],
        [InlineKeyboardButton("🔔 Alert Level", callback_data="set_alert")],
    ])


def positions_keyboard(position_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ Close Position", callback_data=f"close_{position_id}"),
        ],
    ])


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 /scan", callback_data="cmd_scan"),
            InlineKeyboardButton("👛 /wallets", callback_data="cmd_wallets"),
        ],
        [
            InlineKeyboardButton("📊 /positions", callback_data="cmd_positions"),
            InlineKeyboardButton("💰 /pnl", callback_data="cmd_pnl"),
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="cmd_leaderboard"),
            InlineKeyboardButton("⚙️ /settings", callback_data="cmd_settings"),
        ],
    ])
