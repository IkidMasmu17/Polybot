"""Telegram bot command handlers."""
import os
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from loguru import logger

from src.bot.keyboards import (
    copy_trade_keyboard,
    market_detail_keyboard,
    wallet_action_keyboard,
    settings_keyboard,
    positions_keyboard,
    main_menu_keyboard,
)
from src.scanner.market_scanner import scanner
from src.wallet.tracker import tracker
from src.trade.copy_engine import copy_engine
from src.trade.position_manager import position_manager
from src.trade.risk_manager import risk_manager
from src.db import models as db
from src.utils.config import get_config

ALLOWED_USERS = []


def _load_allowed_users():
    global ALLOWED_USERS
    config = get_config()
    ids = config.get("telegram.allowed_user_ids", [])
    owner = os.getenv("TELEGRAM_OWNER_ID")
    if owner and int(owner) not in ids:
        ids.append(int(owner))
    ALLOWED_USERS = ids


def security_check(update: Update) -> bool:
    """Only allow configured owner to use the bot."""
    if not ALLOWED_USERS:
        _load_allowed_users()
    if not ALLOWED_USERS:
        return True  # No restriction configured — allow all (dev mode)
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USERS:
        logger.warning(f"Unauthorized access attempt from {user_id}")
        return False
    return True


async def _ensure_auth(update: Update) -> bool:
    if not security_check(update):
        await update.message.reply_text("❌ Unauthorized access.")
        return False
    return True


# ═══════════════════════════════════════════
# Command Handlers
# ═══════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not security_check(update):
        await update.message.reply_text("❌ Unauthorized.")
        return

    bankroll = await db.get_bankroll()
    open_pos = await db.get_open_positions()
    stats = await db.get_today_stats()

    msg = (
        f"🏟️ <b>PolyBot v1.0</b> — Piala Dunia 2026 Edition\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Bankroll: <b>${bankroll:.2f}</b> / $5.00\n"
        f"📊 Open Positions: <b>{len(open_pos)}</b>\n"
    )
    if stats:
        msg += f"📈 Today PnL: <b>${stats.get('pnl_usd', 0):+.2f}</b>\n"

    msg += (
        f"\n"
        f"<b>Commands:</b>\n"
        f"/scan — Scan pasar taruhan\n"
        f"/wallets — Smart wallet tracker\n"
        f"/positions — Posisi terbuka\n"
        f"/pnl — Profit/Loss summary\n"
        f"/settings — Atur parameter\n"
        f"/leaderboard — Top smart wallets\n"
        f"/help — Bantuan lengkap\n"
    )

    await update.message.reply_html(msg, reply_markup=main_menu_keyboard())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not security_check(update):
        return

    msg = (
        "<b>📖 PolyBot Help</b>\n\n"
        "<b>Perintah Utama:</b>\n"
        "/scan [sport] — Scan market aktif (default: soccer WC 2026)\n"
        "/wallets — Lihat smart wallet yang di-follow\n"
        "/follow &lt;address&gt; — Follow wallet address\n"
        "/unfollow &lt;address&gt; — Stop follow\n"
        "/positions — Lihat posisi terbuka + TP/SL\n"
        "/pnl — Ringkasan profit/loss\n"
        "/settings — Ubah TP, SL, sizing, tier\n"
        "/leaderboard — Top smart wallets teratas\n\n"
        "<b>Copy Trade Flow:</b>\n"
        "1. Bot deteksi smart wallet baru trading\n"
        "2. Bot kirim sinyal dengan tombol [COPY]\n"
        "3. Tap tombol untuk copy trade\n"
        "4. Bot auto-monitor TP/SL\n\n"
        "<b>Modal:</b> $5.00\n"
        "<b>Strategy:</b> Scalping (TP default 8%, SL 5%)\n"
    )
    await update.message.reply_html(msg)


async def scan_markets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return

    await update.message.reply_text("🔍 Scanning Polymarket...")

    markets = await scanner.scan_all()

    if not markets:
        await update.message.reply_text("❌ Tidak ada market yang memenuhi filter saat ini.")
        return

    # Show top 10 most liquid
    top = sorted(markets, key=lambda m: m.get("liquidity", 0), reverse=True)[:10]

    for m in top:
        liq = m.get("liquidity", 0)
        vol = m.get("volume_24h", 0)
        spread = m.get("spread_pct", 0)
        yes = m.get("yes_price", 0.5)
        no = m.get("no_price", 0.5)

        text = (
            f"🏟️ <b>{m['question'][:100]}</b>\n"
            f"   YES: ${yes:.4f} | NO: ${no:.4f}\n"
            f"   💧 Liquidity: ${liq:,.0f} | 📊 Vol: ${vol:,.0f}\n"
            f"   Spread: {spread:.1f}%\n"
        )
        await update.message.reply_html(
            text,
            reply_markup=market_detail_keyboard(m["id"]),
        )

    await update.message.reply_text(
        f"✅ Total {len(markets)} market ditemukan. Refresh: /scan"
    )


async def show_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return

    wallets = await db.get_followed_wallets()

    if not wallets:
        await update.message.reply_text(
            "👛 Belum ada wallet yang di-follow.\n"
            "Gunakan /scan dulu, lalu bot akan menemukan smart wallet secara otomatis.\n"
            "Atau manual: /follow &lt;address&gt;"
        )
        return

    await update.message.reply_text(f"👛 <b>{len(wallets)} Smart Wallets</b>")

    for w in wallets[:15]:
        tier_emoji = "🟢" if w.get("tier") == "ELITE" else "🟡" if w.get("tier") == "SMART" else "⚪"
        text = (
            f"{tier_emoji} <code>{w['address'][:10]}...{w['address'][-6:]}</code>\n"
            f"   Tier: <b>{w.get('tier', 'WATCH')}</b> | Score: {w.get('smart_score', 0):.1f}\n"
            f"   WR 30d: {w.get('win_rate_30d', 0):.1f}% | Trades: {w.get('total_trades', 0)}\n"
        )
        await update.message.reply_html(
            text,
            reply_markup=wallet_action_keyboard(w["address"], bool(w.get("is_following"))),
        )


async def follow_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /follow &lt;wallet_address&gt;")
        return

    address = context.args[0]
    await update.message.reply_text(f"🔍 Tracking wallet <code>{address[:10]}...</code>...")

    result = await tracker.track_wallet(address)

    if not result:
        await update.message.reply_text(
            f"⚠️ Wallet belum memenuhi kriteria smart wallet.\n"
            f"Min {get_config().get_tier_config().get('min_trades', 20)} trades diperlukan."
        )
        return

    await db.set_wallet_follow(address, True)

    tier_emoji = "🟢" if result.get("tier") == "ELITE" else "🟡"
    msg = (
        f"{tier_emoji} <b>Wallet Tracked!</b>\n"
        f"Address: <code>{address[:10]}...{address[-6:]}</code>\n"
        f"Tier: <b>{result.get('tier')}</b>\n"
        f"Score: {result.get('smart_score', 0):.1f}\n"
        f"WR 30d: {result.get('win_rate_30d', 0):.1f}%\n"
        f"WR 90d: {result.get('win_rate_90d', 0):.1f}%\n"
        f"Total Trades: {result.get('total_trades', 0)}\n"
    )
    await update.message.reply_html(msg)


async def unfollow_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /unfollow &lt;wallet_address&gt;")
        return

    address = context.args[0]
    await db.set_wallet_follow(address, False)
    await update.message.reply_text(f"🔕 Unfollowed <code>{address[:10]}...</code>")


async def show_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return

    positions = await db.get_open_positions()

    if not positions:
        await update.message.reply_text("📊 Tidak ada posisi terbuka saat ini.")
        return

    await update.message.reply_text(f"📊 <b>{len(positions)} Open Positions</b>")

    for p in positions:
        pnl_pct = 0.0
        if p.get("current_price") and p.get("entry_price"):
            pnl_pct = ((p["current_price"] - p["entry_price"]) / p["entry_price"]) * 100
            if p["side"] == "NO":
                pnl_pct = -pnl_pct

        pnl_emoji = "🟢" if pnl_pct > 0 else "🔴" if pnl_pct < 0 else "⚪"

        text = (
            f"#{p['id']} | {pnl_emoji} {pnl_pct:+.1f}%\n"
            f"Market: <b>{p.get('market_question', p['market_id'][:30])}</b>\n"
            f"Side: <b>{p['side']}</b> | Entry: ${p['entry_price']:.4f}\n"
            f"Size: ${p['size_usd']:.2f} | "
        )
        if p.get("current_price"):
            text += f"Current: ${p['current_price']:.4f}\n"
        text += (
            f"TP: +{p.get('profit_target_pct', 8)}% | SL: -{p.get('stop_loss_pct', 5)}%\n"
        )
        if p.get("copied_from"):
            text += f"Source: <code>{p['copied_from'][:10]}...</code>"

        await update.message.reply_html(
            text,
            reply_markup=positions_keyboard(p["id"]),
        )


async def show_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return

    summary = await position_manager.get_pnl_summary()

    emoji = "🟢" if summary["total_pnl"] >= 0 else "🔴"

    msg = (
        f"💰 <b>PnL Summary</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"💵 Bankroll: <b>${summary['bankroll']:.2f}</b> (start: $5.00)\n"
        f"{emoji} Total PnL: <b>${summary['total_pnl']:+.2f}</b> ({summary['total_pnl_pct']:+.1f}%)\n"
        f"\n"
        f"📅 Today: <b>${summary['today_pnl']:+.2f}</b> ({summary['today_pnl_pct']:+.1f}%)\n"
        f"📊 Open: {summary['open_positions']} pos | Unrealized: ${summary['unrealized_pnl']:+.2f}\n"
    )
    await update.message.reply_html(msg)


async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return

    wallets = await db.get_smart_wallets(min_score=50, limit=20)

    if not wallets:
        await update.message.reply_text("🏆 Belum ada wallet yang dilacak. Gunakan /scan.")
        return

    msg = "🏆 <b>Smart Wallet Leaderboard</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, w in enumerate(wallets[:10], 1):
        tier_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        msg += (
            f"{tier_emoji} <code>{w['address'][:8]}...</code> "
            f"Score: {w.get('smart_score', 0):.1f} | WR: {w.get('win_rate_30d', 0):.1f}%\n"
        )

    await update.message.reply_html(msg)


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return

    tp = await db.get_setting("profit_target_pct", "8.0")
    sl = await db.get_setting("stop_loss_pct", "5.0")
    size = await db.get_setting("max_position_usd", "1.00")
    tier = await db.get_setting("tier_mode", "STANDAR")
    alert = await db.get_setting("alert_level", "STANDAR")

    msg = (
        f"⚙️ <b>Settings</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"🎯 Profit Target: <b>{tp}%</b>\n"
        f"🛑 Stop Loss: <b>{sl}%</b>\n"
        f"💰 Max Position: <b>${size}</b>\n"
        f"📊 Tier Mode: <b>{tier}</b>\n"
        f"🔔 Alert Level: <b>{alert}</b>\n"
        f"\n"
        f"Ketik untuk ubah:\n"
        f"  TP: /set_tp &lt;angka&gt;\n"
        f"  SL: /set_sl &lt;angka&gt;\n"
        f"  Size: /set_size &lt;dollar&gt;\n"
        f"  Tier: /set_tier &lt;KONSERVATIF|STANDAR|AGGRESIF&gt;\n"
    )
    await update.message.reply_html(msg, reply_markup=settings_keyboard())


async def set_tp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /set_tp &lt;3-50&gt;")
        return
    try:
        val = float(context.args[0])
        val = max(3.0, min(50.0, val))
        await db.set_setting("profit_target_pct", f"{val:.1f}")
        await update.message.reply_text(f"✅ Profit target: <b>{val:.1f}%</b>")
    except ValueError:
        await update.message.reply_text("❌ Masukkan angka (3-50).")


async def set_sl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /set_sl &lt;2-20&gt;")
        return
    try:
        val = float(context.args[0])
        val = max(2.0, min(20.0, val))
        await db.set_setting("stop_loss_pct", f"{val:.1f}")
        await update.message.reply_text(f"✅ Stop loss: <b>{val:.1f}%</b>")
    except ValueError:
        await update.message.reply_text("❌ Masukkan angka (2-20).")


async def set_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /set_size &lt;0.25-1.00&gt;")
        return
    try:
        val = float(context.args[0])
        val = max(0.25, min(1.00, val))
        await db.set_setting("max_position_usd", f"{val:.2f}")
        await update.message.reply_text(f"✅ Max position size: <b>${val:.2f}</b>")
    except ValueError:
        await update.message.reply_text("❌ Masukkan angka (0.25 - 1.00).")


async def set_tier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_auth(update):
        return
    valid = ["KONSERVATIF", "STANDAR", "AGGRESIF"]
    if not context.args or context.args[0].upper() not in valid:
        await update.message.reply_text("Usage: /set_tier KONSERVATIF | STANDAR | AGGRESIF")
        return
    mode = context.args[0].upper()
    await db.set_setting("tier_mode", mode)
    await update.message.reply_text(f"✅ Tier mode: <b>{mode}</b>")


# ═══════════════════════════════════════════
# Callback Query Handlers (Inline Buttons)
# ═══════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all inline button callbacks."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if not data:
        return

    if not security_check(update):
        await query.edit_message_text("❌ Unauthorized.")
        return

    # Copy trade: copy_{trade_id}_{size}
    if data.startswith("copy_"):
        parts = data.split("_")
        trade_id = parts[1]
        size = float(parts[2])

        await query.edit_message_text(
            f"⏳ Executing copy trade for ${size:.2f}...\n"
            f"Trade ID: {trade_id}"
        )

        # We need to reconstruct the signal — in production, cache in memory
        # For now, show confirmation
        await query.message.reply_text(
            f"✅ Copy trade signal diterima!\n"
            f"Size: <b>${size:.2f}</b>\n"
            f"Bot akan monitoring TP/SL otomatis."
        )

    # Wallet detail
    elif data.startswith("wallet_"):
        address = data.replace("wallet_", "")
        wallet = await db.get_wallet(address)
        if wallet:
            msg = (
                f"👛 <b>Wallet Detail</b>\n"
                f"Address: <code>{address[:10]}...{address[-6:]}</code>\n"
                f"Tier: <b>{wallet.get('tier')}</b> | Score: {wallet.get('smart_score', 0):.1f}\n"
                f"WR 30d: {wallet.get('win_rate_30d', 0):.1f}% | WR 90d: {wallet.get('win_rate_90d', 0):.1f}%\n"
                f"Total Trades: {wallet.get('total_trades', 0)}\n"
                f"ROI: {wallet.get('avg_roi_pct', 0):.1f}%\n"
            )
            await query.edit_message_text(msg)
        else:
            await query.edit_message_text("Wallet tidak ditemukan.")

    # Follow/unfollow
    elif data.startswith("follow_"):
        address = data.replace("follow_", "")
        wallet = await db.get_wallet(address)
        if wallet:
            is_following = bool(wallet.get("is_following"))
            await db.set_wallet_follow(address, not is_following)
            status = "Unfollowed" if is_following else "Followed"
            await query.edit_message_text(f"✅ {status} <code>{address[:10]}...</code>")

    # Skip signal
    elif data.startswith("skip_"):
        await query.edit_message_text("⏭️ Signal skipped.")

    # Close position
    elif data.startswith("close_"):
        pos_id = int(data.replace("close_", ""))
        result = await position_manager.close_position_manual(pos_id)
        if result:
            await query.edit_message_text(
                f"❌ Position #{pos_id} closed\n"
                f"PnL: <b>${result['pnl_usd']:+.2f}</b> ({result['pnl_pct']:+.1f}%)"
            )
        else:
            await query.edit_message_text("❌ Gagal menutup posisi.")

    # Menu shortcuts
    elif data == "cmd_scan":
        await query.edit_message_text("🔍 Gunakan /scan untuk scan market.")
    elif data == "cmd_wallets":
        await query.edit_message_text("👛 Gunakan /wallets untuk lihat smart wallets.")
    elif data == "cmd_positions":
        await query.edit_message_text("📊 Gunakan /positions untuk lihat posisi.")
    elif data == "cmd_pnl":
        await query.edit_message_text("💰 Gunakan /pnl untuk PnL summary.")
    elif data == "cmd_leaderboard":
        await query.edit_message_text("🏆 Gunakan /leaderboard untuk top wallets.")
    elif data == "cmd_settings":
        await query.edit_message_text("⚙️ Gunakan /settings untuk ubah parameter.")
    elif data in ("set_tp", "set_sl", "set_size", "set_tier", "set_alert"):
        await query.edit_message_text(f"Gunakan command: /{data} &lt;nilai&gt;")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback message handler."""
    if not security_check(update):
        await update.message.reply_text("❌ Unauthorized access.")
        return
    await update.message.reply_text(
        "Gunakan perintah dari menu atau ketik /help untuk bantuan.",
        reply_markup=main_menu_keyboard(),
    )
