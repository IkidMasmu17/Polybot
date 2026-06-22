# 🏟️ PolyBot v1.0

**Polymarket Trading Bot — Piala Dunia 2026 Edition**

Bot Telegram untuk trading di [Polymarket](https://polymarket.com) khusus event olahraga (World Cup 2026, NBA, UFC, dll). Melacak **smart wallet** dengan win rate ≥70%, lalu **copy trade** secara semi-otomatis via tombol di Telegram.

---

## 📋 Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| 🔍 **Market Scanner** | Scan pasar taruhan Polymarket — filter liquidity ≥$500, spread ≤5%, volume ≥$200 |
| 👛 **Smart Wallet Tracker** | Deteksi & klasifikasi wallet: 🟢 ELITE (WR ≥85%), 🟡 SMART (WR ≥70%), ⚪ WATCH |
| 📊 **Wallet Scoring** | Algoritma: Weighted WR × Confidence × ROI Factor |
| 📋 **Copy Trade** | Semi-auto 1-tap confirm via inline keyboard Telegram |
| 🎯 **TP/SL Auto** | Take Profit & Stop Loss monitor otomatis setiap 15 detik |
| ⏱️ **Time-Based Close** | Force close posisi setelah 90 menit |
| 🛡️ **Risk Manager** | Daily loss limit 30%, max 3 posisi, drawdown reduction, max $1/trade |
| 🔔 **Signal Alert** | Notifikasi Telegram saat smart wallet entry posisi baru |

---

## 🏗️ Tech Stack

| Layer | Teknologi |
|-------|-----------|
| **Language** | Python 3.11+ |
| **Async** | asyncio + aiohttp |
| **Telegram** | python-telegram-bot v21 |
| **Polymarket** | py-clob-client (official SDK) + Gamma API + Data API |
| **Database** | SQLite (WAL mode, async) |
| **Scheduler** | APScheduler |
| **Security** | Fernet encryption untuk private key |
| **Logging** | Loguru (console + rotating file) |

---

## 📁 Struktur Project

```
Polybot/
├── main.py                        # Entry point
├── config.yaml                    # Parameter trading
├── requirements.txt               # Dependencies
├── .env.example                   # Template environment
│
├── src/
│   ├── api/                       # Polymarket API wrapper + CLOB client
│   ├── scanner/                   # Market scanner & filter
│   ├── wallet/                    # Smart wallet tracker + scoring algorithm
│   ├── trade/                     # Copy engine + position manager + risk manager
│   ├── bot/                       # Telegram bot (commands, keyboards, handlers)
│   ├── scheduler/                 # Background jobs (scan, track, monitor, signal)
│   ├── db/                        # SQLite database + CRUD models
│   └── utils/                     # Config, logger, security
│
└── tests/                         # Unit tests
    └── test_scoring.py            # 15 tests — wallet scoring algorithm
```

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/IkidMasmu17/Polybot.git
cd Polybot
pip install -r requirements.txt
```

### 2. Konfigurasi

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_OWNER_ID=123456789
POLYMARKET_PRIVATE_KEY=0x_your_polygon_wallet_private_key
FERNET_KEY=generated_fernet_key
```

Generate Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> ⚠️ **PENTING:** Gunakan wallet Polygon terpisah khusus bot. Jangan gunakan wallet utama. Deposit $5 saja.

### 3. Jalankan

```bash
python main.py
```

Bot akan start long polling dan scheduler background jobs.

---

## 📱 Telegram Commands

| Command | Fungsi |
|---------|--------|
| `/start` | Onboarding + ringkasan akun |
| `/help` | Bantuan lengkap |
| `/scan` | Scan market aktif |
| `/wallets` | Daftar smart wallet yang di-follow |
| `/follow <addr>` | Follow wallet address |
| `/unfollow <addr>` | Stop follow wallet |
| `/positions` | Lihat posisi terbuka + TP/SL |
| `/pnl` | Ringkasan Profit/Loss |
| `/leaderboard` | Top smart wallets |
| `/settings` | Lihat parameter saat ini |
| `/set_tp <3-50>` | Ubah profit target (%) |
| `/set_sl <2-20>` | Ubah stop loss (%) |
| `/set_size <0.25-1.00>` | Ubah max position size ($) |
| `/set_tier <mode>` | Ubah tier: KONSERVATIF / STANDAR / AGGRESIF |

---

## 🧠 Wallet Scoring Algorithm

```
Smart Score = Weighted_WR × Confidence × ROI_Factor

Weighted_WR = WR_30d × 0.6 + WR_90d × 0.4
Confidence  = min(total_trades / 50, 1.0)
ROI_Factor  = clamp(1.0 + avg_roi / 100, 0.8, 1.3)

Tier:
  🟢 ELITE  = Score ≥ 85
  🟡 SMART  = Score ≥ 70
  ⚪ WATCH  = Score < 70
```

---

## 📊 Parameter Default

| Parameter | Default | Range |
|-----------|---------|-------|
| Profit Target | 8% | 3–50% |
| Stop Loss | 5% | 2–20% |
| Max Position | $1.00 | $0.25–$1.00 |
| Max Open Positions | 3 | — |
| Time Limit | 90 min | — |
| Daily Loss Limit | 30% ($1.50) | — |
| Bankroll | $5.00 | — |
| Position Sizing | 20% bankroll | — |

Semua parameter bisa diubah via `/settings` atau `/set_*` commands.

---

## 🛡️ Risk Management

- **Daily Loss Limit:** Trading auto-halt jika loss harian ≥30% ($1.50)
- **Drawdown Reduction:** Position size auto-kurang 50% setelah 2 consecutive loss
- **Max Positions:** Maksimal 3 posisi simultan
- **Auto-Unfollow:** Wallet di-unfollow jika WR turun 15% dari peak atau 5 loss berturut-turut

---

## ✅ Testing

```bash
pytest tests/ -v
```

```
tests/test_scoring.py::TestWinRate::test_basic PASSED
tests/test_scoring.py::TestSmartScore::test_elite_wallet PASSED
...
======================= 15 passed =======================
```

---

## 📝 Roadmap

- [x] Market Scanner (WC 2026)
- [x] Smart Wallet Tracker + Scoring
- [x] Copy Trade (semi-auto)
- [x] TP/SL Auto Monitor
- [x] Risk Manager
- [ ] Multi-sport scanner (basketball, tennis, MMA)
- [ ] Paper trading mode
- [ ] Web dashboard
- [ ] Full-auto mode (v2.0)
- [ ] Multi-user support (v2.0)

---

## ⚠️ Disclaimer

**PolyBot adalah bot trading eksperimental.** Polymarket trading mengandung risiko kehilangan dana. Bot ini dirancang untuk modal $5 sebagai proof-of-concept. Gunakan dengan bijak:

- Hanya deposit dana yang rela hilang 100%
- Selalu test dengan paper trading sebelum real money
- Parameter default adalah rekomendasi — sesuaikan dengan risk tolerance Anda
- Developer tidak bertanggung jawab atas kerugian finansial

---

## 📄 License

MIT License — Lihat file [LICENSE](LICENSE) (jika ada).

---

*PolyBot v1.0 · Juni 2026 · World Cup 2026 Edition*
