# PolyBot — Dokumen Opsi Lengkap
> Berdasarkan PRD PolyBot v1.0 · Piala Dunia 2026 Edition  
> Disusun oleh: Engineering Lead · Juni 2026

---

## Daftar Isi

- [01 · Opsi Tech Stack](#01--opsi-tech-stack)
- [02 · Opsi Arsitektur Sistem](#02--opsi-arsitektur-sistem)
- [03 · Opsi Market Scanner](#03--opsi-market-scanner)
- [04 · Opsi Smart Wallet Tracker](#04--opsi-smart-wallet-tracker)
- [05 · Opsi Copy Trade Engine](#05--opsi-copy-trade-engine)
- [06 · Opsi Scalping Parameters](#06--opsi-scalping-parameters)
- [07 · Opsi Wallet Scoring Algorithm](#07--opsi-wallet-scoring-algorithm)
- [08 · Opsi Risk Management](#08--opsi-risk-management)
- [09 · Opsi Telegram Bot Interface](#09--opsi-telegram-bot-interface)
- [10 · Opsi Polymarket API Integration](#10--opsi-polymarket-api-integration)
- [11 · Opsi On-Chain Data Source](#11--opsi-on-chain-data-source)
- [12 · Opsi Deployment & Infrastruktur](#12--opsi-deployment--infrastruktur)
- [13 · Opsi Database](#13--opsi-database)
- [14 · Opsi Security](#14--opsi-security)
- [15 · Opsi Development Approach](#15--opsi-development-approach)
- [16 · Opsi Feature Priority (MVP vs Full)](#16--opsi-feature-priority-mvp-vs-full)
- [17 · Matriks Keputusan Final](#17--matriks-keputusan-final)

---

## 01 · Opsi Tech Stack

### Runtime & Language

| # | Opsi | Pro | Kontra | Rekomendasi |
|---|------|-----|--------|-------------|
| A | **Python 3.11+** | Ekosistem crypto terlengkap, `py-clob-client` resmi tersedia, asyncio matang | GIL bisa jadi bottleneck di high-concurrency | ✅ **Pilih ini** |
| B | Node.js / TypeScript | Non-blocking by default, `@polymarket/clob-client` tersedia | Library wallet analysis lebih sedikit | ⚠️ Alternatif jika tim lebih familiar JS |
| C | Go | Performa sangat tinggi, goroutine efisien | Tidak ada SDK Polymarket resmi, harus buat sendiri | ❌ Overkill untuk v1.0 |

### Async Framework

| # | Opsi | Pro | Kontra | Rekomendasi |
|---|------|-----|--------|-------------|
| A | **asyncio + aiohttp** | Native Python, zero overhead, cocok untuk I/O bound | Curve learning lebih tinggi | ✅ **Pilih ini** |
| B | Celery + Redis | Bagus untuk task queue terdistribusi | Over-engineered untuk single-user bot | ❌ Terlalu berat |
| C | Threading biasa | Mudah dipahami | Race condition rawan, tidak efisien | ❌ Tidak disarankan |

### Telegram Library

| # | Opsi | Pro | Kontra | Rekomendasi |
|---|------|-----|--------|-------------|
| A | **python-telegram-bot v21** | Library resmi, support inline keyboard, webhook & polling, dokumentasi lengkap | — | ✅ **Pilih ini** |
| B | aiogram v3 | Fully async, lebih modern | Komunitas lebih kecil, contoh lebih sedikit | ⚠️ Alternatif solid |
| C | Telethon | Lebih untuk user-bot, bukan bot API | Bukan untuk Telegram Bot API standar | ❌ Salah use case |

### Scheduler

| # | Opsi | Pro | Kontra | Rekomendasi |
|---|------|-----|--------|-------------|
| A | **APScheduler** | Simple, support cron & interval, mudah integrasi asyncio | — | ✅ **Pilih ini** |
| B | Celery Beat | Power besar, cocok untuk distributed | Butuh Redis/RabbitMQ, overkill | ❌ |
| C | asyncio.create_task() manual | Lightweight, zero dependency | Tidak ada retry & error handling built-in | ⚠️ Untuk task sederhana saja |

---

## 02 · Opsi Arsitektur Sistem

### Opsi A — Monolith Async (Rekomendasi v1.0)

```
┌─────────────────────────────────────────┐
│             PolyBot Monolith            │
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │  Scanner │  │  Wallet  │  │  Tele │ │
│  │  Module  │  │  Tracker │  │  gram │ │
│  └────┬─────┘  └────┬─────┘  └───┬───┘ │
│       │              │            │     │
│  ┌────▼──────────────▼────────────▼───┐ │
│  │         Core Event Bus (asyncio)   │ │
│  └────────────────┬───────────────────┘ │
│               ┌───▼────┐                │
│               │  SQLite │               │
│               └─────────┘               │
└─────────────────────────────────────────┘
```

- **Cocok untuk:** v1.0, single-user, modal $5
- **Biaya infra:** $5–10/bulan (1 VPS)
- **Complexity:** Rendah ✅

---

### Opsi B — Microservices (Untuk v2.0+)

```
┌──────────┐   ┌──────────┐   ┌──────────┐
│  Scanner │   │  Wallet  │   │  Order   │
│  Service │   │  Service │   │  Service │
└────┬─────┘   └────┬─────┘   └────┬─────┘
     │               │              │
     └───────────────▼──────────────┘
                ┌────────┐
                │  Redis │  (Message Queue)
                └────┬───┘
                ┌────▼───┐
                │  Bot   │  (Telegram Gateway)
                └────────┘
```

- **Cocok untuk:** Multi-user, scale besar
- **Biaya infra:** $30–80/bulan
- **Complexity:** Tinggi ❌ Belum perlu di v1.0

---

### Opsi C — Serverless (Lambda/Cloud Functions)

- **Pro:** Bayar per eksekusi, murah jika traffic rendah
- **Kontra:** Cold start latency tinggi → **fatal untuk scalping real-time**
- **Verdict:** ❌ Tidak cocok untuk use case ini

---

## 03 · Opsi Market Scanner

### Metode Polling

| # | Opsi | Interval | Pro | Kontra | Rekomendasi |
|---|------|----------|-----|--------|-------------|
| A | **REST Polling reguler** | 30 detik | Simple, reliable, tidak perlu setup extra | Bukan real-time sempurna | ✅ **v1.0** |
| B | WebSocket streaming | Real-time | Latency sangat rendah | Koneksi harus selalu dijaga, reconnect logic kompleks | ⚠️ v2.0 |
| C | Webhook dari Polymarket | Push-based | Paling efisien | Polymarket belum punya webhook publik | ❌ Tidak tersedia |

### Filter Market

| Parameter | Opsi Nilai | Default PRD | Keterangan |
|-----------|-----------|-------------|------------|
| Minimum Liquidity | $100 / $300 / **$500** / $1000 | **$500** | Semakin tinggi = market lebih liquid, spread lebih kecil |
| Max Spread | 3% / **5%** / 10% | **5%** | Spread < 5% = entry/exit lebih efisien |
| Min Volume 24h | $100 / **$200** / $500 | **$200** | Volume rendah = susah exit posisi |
| Window Upcoming | 30 mnt / **2 jam** / 6 jam | **2 jam** | Pertandingan dalam 2 jam ke depan |

### Kategori Sport yang Di-scan

```yaml
# Opsi konfigurasi sport_categories di config.yaml
sport_categories:
  # Fase MVP — Piala Dunia 2026
  - soccer          # ✅ AKTIF - Piala Dunia 2026
  
  # Fase 2 — Ekspansi
  - basketball      # NBA, FIBA
  - tennis          # Grand Slam, ATP/WTA
  - baseball        # MLB
  - american_football  # NFL
  - mma             # UFC
  - cricket         # IPL, World Cup
```

---

## 04 · Opsi Smart Wallet Tracker

### Sumber Data Wallet

| # | Opsi | Latency | Biaya | Kedalaman Data | Rekomendasi |
|---|------|---------|-------|----------------|-------------|
| A | **The Graph — Polymarket Subgraph** | ~5 detik | Gratis (rate limited) | Lengkap: semua trades historis | ✅ **Utama** |
| B | Alchemy / QuickNode RPC langsung | ~1 detik | $49–199/bulan | Butuh indexing sendiri | ⚠️ Mahal untuk v1.0 |
| C | Polymarket REST API `/trades` | ~3 detik | Gratis | Cukup untuk basic tracking | ✅ **Fallback** |
| D | Dune Analytics | Batch query | Gratis (terbatas) | Sangat lengkap | ❌ Terlalu lambat untuk real-time |

### Threshold Win Rate — Opsi Konfigurasi

```python
# Opsi threshold — bisa disesuaikan via /settings
WALLET_TIERS = {
    "KONSERVATIF": {
        "elite_threshold": 90,    # WR ≥ 90%
        "smart_threshold": 80,    # WR 80–89%
        "min_trades": 30,
    },
    "STANDAR": {                  # ← Default PRD
        "elite_threshold": 85,    # WR ≥ 85%
        "smart_threshold": 70,    # WR 70–84%
        "min_trades": 20,
    },
    "AGRESIF": {
        "elite_threshold": 75,    # WR ≥ 75%
        "smart_threshold": 65,    # WR 65–74%
        "min_trades": 15,
    },
}
```

### Opsi Periode Kalkulasi Win Rate

| Opsi | Periode | Bobot | Keterangan |
|------|---------|-------|------------|
| A | 7 hari saja | 100% | Terlalu sensitif, sampel kecil |
| B | 30 hari saja | 100% | Cukup, tapi tidak capture long-term |
| **C (Default)** | **30d × 60% + 90d × 40%** | **Weighted** | **Balance recency vs stabilitas** ✅ |
| D | 90 hari saja | 100% | Terlalu lambat deteksi perubahan |
| E | 7d × 40% + 30d × 40% + 90d × 20% | Weighted | Lebih sensitif ke performa terkini |

---

## 05 · Opsi Copy Trade Engine

### Mode Eksekusi

| # | Mode | Deskripsi | Risiko | Rekomendasi |
|---|------|-----------|--------|-------------|
| A | **Semi-Auto (Konfirmasi 1-tap)** | Bot kirim sinyal → User tap [COPY] → Eksekusi | Rendah | ✅ **Default v1.0** |
| B | Full-Auto | Bot langsung eksekusi tanpa konfirmasi | **Tinggi — BAHAYA untuk modal $5** | ❌ Tidak di v1.0 |
| C | Shadow Mode | Track sinyal tapi tidak eksekusi, cuma catat | Nol | ✅ Bagus untuk paper trading fase awal |
| D | Schedule Delay | Eksekusi N detik setelah sinyal (anti-frontrun) | Rendah-Medium | ⚠️ Opsional untuk v1.1 |

### Order Type

| # | Tipe Order | Pro | Kontra | Rekomendasi |
|---|-----------|-----|--------|-------------|
| A | **Limit Order** | Harga terjamin, tidak ada slippage | Bisa tidak terisi jika harga bergerak | ✅ **Utama** |
| B | Market Order | Pasti terisi | Slippage tidak terkontrol, buruk untuk modal kecil | ❌ Hanya sebagai fallback |
| C | Limit → fallback Market | Best of both worlds | Butuh timeout logic | ⚠️ v1.1 |

### Sizing Calculator — Opsi Formula

```python
# Opsi A: Fixed Amount (Paling Simpel)
position_size = 1.00  # Selalu $1 per trade

# Opsi B: Fixed Percentage (Recommended)
position_size = bankroll * 0.20  # 20% dari modal tersedia

# Opsi C: Kelly Criterion (Paling Optimal tapi Kompleks)
kelly_fraction = (win_rate - (1 - win_rate) / odds_ratio)
position_size = bankroll * kelly_fraction * 0.5  # Half-Kelly lebih aman

# Opsi D: Martingale (TIDAK DIREKOMENDASIKAN)
# position_size = last_loss_amount * 2  ← BAHAYA untuk modal $5
```

> ⚠️ **Catatan:** Dengan modal $5, Opsi B (Fixed Percentage 20% = $1.00 max) adalah pilihan paling aman.

---

## 06 · Opsi Scalping Parameters

### Profit Target

| Opsi | Target | Cocok Untuk | Risk/Reward |
|------|--------|------------|-------------|
| Ultra Conservative | 3–5% | Market sangat liquid, spread kecil | R/R 1:0.6 |
| **Conservative (Default)** | **8%** | **Market normal WC 2026** | **R/R 1:1.6** |
| Moderate | 12–15% | Market volatile, intraday | R/R 1:2.4 |
| Aggressive | 20–30% | High-confidence signal dari ELITE wallet | R/R 1:4 |
| Sangat Agresif | 40–50% | Hanya untuk event final/semi-final | R/R 1:8 |

```yaml
# config.yaml — scalping_settings
scalping:
  profit_target_pct: 8        # Bisa diubah via /settings 3–50
  stop_loss_pct: 5            # Bisa diubah via /settings 2–20
  max_position_usd: 1.00      # Max $1 per trade
  max_open_positions: 3       # Max 3 posisi simultan
  time_limit_minutes: 90      # Force close setelah 90 menit
  slippage_tolerance_pct: 1.0 # Max 1% slippage diterima
```

### Stop Loss — Opsi Konfigurasi

| Opsi | Stop Loss | Notes |
|------|-----------|-------|
| Ketat | 3% | Sering kena stop, butuh win rate tinggi |
| **Standar (Default)** | **5%** | **Balance antara proteksi dan ruang gerak** |
| Longgar | 10% | Memberi ruang lebih, tapi max loss besar |
| Trailing SL | Dynamic | Follow harga naik, tapi lebih kompleks implementasi |

### Time Limit per Trade

| Opsi | Waktu | Keterangan |
|------|-------|------------|
| Quick Scalp | 15–30 menit | Untuk live in-play markets |
| **Standar** | **90 menit** | **Default — cocok untuk pre-match** |
| Swing | 6 jam | Untuk early market sebelum kick-off |
| Hold sampai close | Sampai market tutup | Bukan scalping lagi, jadi swing |

---

## 07 · Opsi Wallet Scoring Algorithm

### Formula Confidence Adjustment

```python
# Opsi A: Linear Confidence (Default PRD)
confidence = min(total_trades / 50, 1.0)

# Opsi B: Square Root (Lebih cepat mencapai confidence penuh)
confidence = min(math.sqrt(total_trades / 30), 1.0)

# Opsi C: Logarithmic (Paling smooth, sedikit lebih konservatif)
confidence = min(math.log(total_trades + 1) / math.log(51), 1.0)

# Opsi D: Hard threshold (Binary — lebih simpel)
confidence = 1.0 if total_trades >= 20 else 0.5
```

### ROI Factor — Opsi Inklusi

| Opsi | Formula | Keterangan |
|------|---------|------------|
| A | WR saja | Paling simpel, tapi tidak capture besar kecil profit |
| **B (Default)** | **WR × avg_roi_factor** | **Balance antara frekuensi win dan besar profit** |
| C | Expected Value (EV) | `WR × avg_win_size - (1-WR) × avg_loss_size` — paling akurat |
| D | Sharpe-like Score | Pertimbangkan volatilitas — paling kompleks |

### Auto-Unfollow Trigger

```python
# Opsi konfigurasi kapan wallet otomatis di-unfollow
AUTO_UNFOLLOW_OPTIONS = {
    "STRICT": {
        "trailing_wr_drop": 10,   # Unfollow jika WR turun 10% dari peak
        "consecutive_losses": 3,   # Unfollow setelah 3 kalah berturut-turut
        "check_interval_days": 7,
    },
    "STANDAR": {                   # ← Default PRD
        "trailing_wr_drop": 15,    # Unfollow jika WR turun < 65%
        "consecutive_losses": 5,
        "check_interval_days": 14,
    },
    "LONGGAR": {
        "trailing_wr_drop": 20,
        "consecutive_losses": 7,
        "check_interval_days": 30,
    },
}
```

---

## 08 · Opsi Risk Management

### Daily Loss Limit

| Opsi | Limit | Efek pada Modal $5 | Rekomendasi |
|------|-------|-------------------|-------------|
| Ultra Ketat | 10% ($0.50) | Bot lock setelah loss $0.50 | Terlalu sering lock |
| Ketat | 20% ($1.00) | Masih ada $4.00 untuk besok | Safe tapi mungkin miss opportunity |
| **Standar (Default)** | **30% ($1.50)** | **Masih ada $3.50 setelah worst day** | ✅ **Recommended** |
| Longgar | 50% ($2.50) | Risiko tinggal $2.50 dalam sehari | ❌ Terlalu agresif |

### Drawdown Consecutive Loss — Opsi Sizing Reduction

```python
# Opsi A: Step-down (Default PRD)
if consecutive_losses >= 2:
    position_size *= 0.5   # Turun ke 10% dari bankroll

# Opsi B: Gradual Reduction
sizing_multipliers = {
    0: 1.0,   # Normal: 20% bankroll
    1: 0.75,  # 1 kalah: 15% bankroll
    2: 0.50,  # 2 kalah: 10% bankroll
    3: 0.25,  # 3 kalah: 5% bankroll
    4: 0.0,   # 4 kalah berturut: STOP
}

# Opsi C: Flat Stop
# Langsung stop trading setelah N loss berturut-turut
MAX_CONSECUTIVE_LOSSES = 3  # Tidak ada sizing reduction, langsung halt
```

### Opsi Manajemen Posisi Simultan

| Max Posisi | Total Exposure | Per-Trade Max | Keterangan |
|-----------|----------------|---------------|------------|
| 1 posisi | $1.00 / $5.00 | $1.00 | Ultra konservatif, tidak ada diversifikasi |
| **3 posisi** | **$3.00 / $5.00** | **$1.00** | **Default PRD — balance diversifikasi** |
| 5 posisi | $5.00 / $5.00 | $1.00 | Semua in, risiko tinggi |
| 3 posisi | $2.25 / $5.00 | $0.75 | Lebih konservatif, 45% total exposure |

---

## 09 · Opsi Telegram Bot Interface

### Metode Koneksi Bot

| # | Metode | Latency | Cocok Untuk | Rekomendasi |
|---|--------|---------|------------|-------------|
| A | **Long Polling** | ~1–2 detik | Server tanpa public IP, development | ✅ **v1.0 — lebih simpel setup** |
| B | Webhook | ~200ms | VPS dengan public IP & HTTPS | ⚠️ v1.1 untuk produksi |

### Opsi Notifikasi Alert

```
# Opsi level notifikasi — bisa diatur via /alerts

[MINIMAL]
  - Hanya sinyal copy trade dari ELITE wallet
  
[STANDAR] ← Default
  - Sinyal copy trade (ELITE + SMART)
  - Konfirmasi order filled
  - TP/SL triggered
  - Daily PnL summary

[VERBOSE]
  - Semua di atas +
  - New market detected
  - Wallet tier change
  - Price movement alert (setiap 5%)
  - Hourly portfolio update
```

### Opsi Menu Inline Keyboard

```
# Saat menerima sinyal copy trade:
┌────────────────────────────────────┐
│ 🟢 ELITE Signal — Brazil vs France │
│ Wallet: 0x...abc (WR 89%, 47 trades)│
│ Position: YES @ $0.42              │
│ Market: Brazil Win                  │
├────────────────────────────────────┤
│ [✅ COPY $1.00] [⚡ COPY $0.50]    │
│ [🔍 Lihat Wallet] [❌ Skip]        │
└────────────────────────────────────┘

# Opsi sizing di inline keyboard:
  - Fixed: $0.25 / $0.50 / $1.00
  - Atau: tombol input custom amount
  - Atau: persentase bankroll (10% / 20% / max)
```

### Command List — Opsi Tambahan (v1.1+)

| Command | Status | Deskripsi |
|---------|--------|-----------|
| `/start` | ✅ MVP | Onboarding |
| `/scan [sport]` | ✅ MVP | Scan market aktif |
| `/wallets` | ✅ MVP | Daftar smart wallet |
| `/follow [addr]` | ✅ MVP | Follow wallet |
| `/positions` | ✅ MVP | Posisi terbuka |
| `/pnl` | ✅ MVP | Profit/Loss summary |
| `/settings` | ✅ MVP | Atur parameter |
| `/alerts` | ✅ MVP | Toggle notifikasi |
| `/leaderboard` | ✅ MVP | Top smart wallets |
| `/unfollow [addr]` | ✅ MVP | Stop follow wallet |
| `/backtest [addr]` | ⚠️ v1.1 | Backtest wallet historis |
| `/heatmap` | ⚠️ v1.1 | Heatmap market aktif per sport |
| `/report` | ⚠️ v1.1 | Export laporan harian ke PDF |
| `/journal [notes]` | ⚠️ v1.1 | Catat catatan trade manual |
| `/simulate` | ⚠️ v2.0 | Paper trading mode tanpa dana nyata |

---

## 10 · Opsi Polymarket API Integration

### CLOB Client — Opsi Implementasi

```python
# Opsi A: Official py-clob-client (Recommended)
# pip install py-clob-client
from py_clob_client.client import ClobClient

client = ClobClient(
    host="https://clob.polymarket.com",
    key=PRIVATE_KEY,
    chain_id=137,               # Polygon Mainnet
    signature_type=2,           # EIP-712
)

# Opsi B: Raw HTTP dengan httpx (Lebih kontrol, lebih kerja)
import httpx
# Butuh implementasi EIP-712 signing manual

# Opsi C: Gamma API (lebih simpel tapi read-only)
# Cocok untuk scanner saja, tidak bisa place order
```

### Opsi Endpoint untuk Market Discovery

```
# Prioritas endpoint untuk market scanner:

1. Gamma Markets API (read-only, no auth needed)
   GET https://gamma-api.polymarket.com/markets
   ?tag=soccer&active=true&liquidity_min=500
   → Paling mudah, cocok untuk scanner

2. CLOB API (butuh auth untuk write, read bisa tanpa auth)
   GET https://clob.polymarket.com/markets
   → Lebih real-time untuk pricing

3. Polymarket.com API (unofficial, bisa berubah)
   → Gunakan hanya sebagai fallback
```

### Rate Limit Strategy

| Opsi | Approach | Max RPS | Risiko Ban |
|------|----------|---------|------------|
| A | No rate limit | Unlimited | ❌ Tinggi |
| B | **Token bucket 10 RPS** | 10/detik | ✅ Aman |
| C | Conservative 5 RPS + backoff | 5/detik | ✅ Sangat aman |
| D | Adaptive (mundur saat 429) | Dynamic | ✅ Paling robust |

---

## 11 · Opsi On-Chain Data Source

### Sumber Data untuk Wallet Tracking

| # | Sumber | Latency | Biaya | Setup Difficulty | Rekomendasi |
|---|--------|---------|-------|-----------------|-------------|
| A | **The Graph — Polymarket Subgraph** | ~5–10 detik | Gratis (1000 query/hari) | Mudah (GraphQL) | ✅ **Utama** |
| B | Alchemy Enhanced APIs | ~1–3 detik | Free tier: 300M CU/bulan | Sedang | ✅ **Fallback & enrichment** |
| C | QuickNode Polygon RPC | ~1 detik | $9/bulan starter | Sedang | ⚠️ Jika butuh lebih cepat |
| D | Polygon Public RPC | ~3–10 detik | Gratis | Mudah | ⚠️ Tidak reliable untuk produksi |
| E | Dune Analytics API | Menit | $349/bulan Pro | Mudah | ❌ Terlalu mahal & lambat |
| F | **Polymarket REST `/trades`** | ~3 detik | Gratis | Sangat mudah | ✅ **Paling praktis untuk v1.0** |

> **Strategi Rekomendasi:**  
> Primary: `Polymarket REST API` untuk data trade  
> Secondary: `The Graph` untuk query historis mendalam  
> Enrichment: `Alchemy` untuk verifikasi on-chain

---

## 12 · Opsi Deployment & Infrastruktur

### Platform Hosting

| # | Platform | Harga/Bulan | Uptime | Setup | Rekomendasi |
|---|----------|-------------|--------|-------|-------------|
| A | **Railway.app** | $5 (Hobby) | 99.9% | Sangat mudah, deploy via GitHub | ✅ **Terbaik untuk mulai** |
| B | VPS DigitalOcean (Droplet $6) | $6 | 99.9% | Sedang — butuh konfigurasi manual | ✅ Lebih kontrol |
| C | VPS Vultr / Hetzner | $3.5–5 | 99.9% | Sedang | ✅ Lebih murah dari DO |
| D | Oracle Cloud Free Tier | Gratis | 99.9% | Sedang-Sulit | ✅ Gratis tapi setup lumayan |
| E | Heroku | $7 (Eco Dyno) | 99.5% | Mudah | ⚠️ Lebih mahal vs Railway |
| F | Fly.io | $1.94+ | 99.9% | Sedang | ✅ Alternatif Railway |
| G | Raspberry Pi lokal | Listrik saja | Tergantung koneksi rumah | Tinggi | ❌ Tidak reliable |

### Process Manager

| Opsi | Tool | Keterangan |
|------|------|------------|
| A | **systemd** (di VPS Linux) | Standard, reliable, restart otomatis | ✅ |
| B | **PM2** (Node ecosystem tapi support Python) | Dashboard bagus | ⚠️ |
| C | **Supervisor** | Lightweight Python process manager | ✅ |
| D | Docker + docker-compose | Isolation, reproducible | ✅ Recommended untuk v1.1+ |

### Opsi Monitoring

```yaml
# Pilih minimal satu:

monitoring_options:
  uptime_check:
    - UptimeRobot (Gratis — ping setiap 5 menit)    ✅ Recommended
    - Better Uptime ($0 tier tersedia)
    
  logging:
    - File logging lokal (loguru)                   ✅ Minimal wajib
    - Papertrail (Gratis 50MB/bulan)
    - Telegram self-notification (kirim error ke diri sendiri) ✅ Simple & efektif
    
  metrics:
    - Grafana + Prometheus (selfhosted)              ⚠️ v2.0
    - Statsd                                         ⚠️ v2.0
```

---

## 13 · Opsi Database

### Pilihan Database

| # | Database | Cocok Untuk | Pro | Kontra | Rekomendasi |
|---|----------|------------|-----|--------|-------------|
| A | **SQLite** | Development, single-user | Zero setup, file-based, cukup untuk $5 bot | Tidak support concurrent write | ✅ **v1.0** |
| B | PostgreSQL | Production, multi-user | Robust, concurrent safe, full SQL | Butuh server terpisah atau managed | ✅ v2.0 |
| C | Redis | Cache & session saja | In-memory, sangat cepat | Bukan primary DB | ⚠️ Tambahan untuk cache |
| D | TinyDB | Ultra-lightweight JSON | Simpel, no SQL | Lambat untuk query kompleks | ⚠️ Alternatif SQLite |
| E | MongoDB | Flexible schema | Bagus untuk JSON-like data | Overkill untuk use case ini | ❌ |

### Schema Minimal (SQLite)

```sql
-- Tabel utama yang dibutuhkan v1.0

CREATE TABLE markets (
    id TEXT PRIMARY KEY,
    question TEXT,
    sport_tag TEXT,
    yes_price REAL,
    no_price REAL,
    liquidity REAL,
    volume_24h REAL,
    close_time TIMESTAMP,
    last_updated TIMESTAMP
);

CREATE TABLE wallets (
    address TEXT PRIMARY KEY,
    win_rate_30d REAL,
    win_rate_90d REAL,
    smart_score REAL,
    tier TEXT,          -- ELITE / SMART / WATCH
    total_trades INT,
    last_checked TIMESTAMP,
    is_following BOOLEAN DEFAULT FALSE
);

CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT,
    side TEXT,          -- YES / NO
    entry_price REAL,
    size_usd REAL,
    shares REAL,
    status TEXT,        -- OPEN / CLOSED / CANCELLED
    opened_at TIMESTAMP,
    closed_at TIMESTAMP,
    pnl_usd REAL,
    copied_from TEXT    -- wallet address jika copy trade
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

---

## 14 · Opsi Security

### Penyimpanan Private Key

| # | Opsi | Security Level | Kemudahan | Rekomendasi |
|---|------|---------------|-----------|-------------|
| A | `.env` file + python-dotenv | Medium | ✅ Sangat mudah | ✅ **Minimum untuk v1.0** |
| B | **Fernet encryption + `.env`** | High | Sedang | ✅ **Recommended v1.0** |
| C | HashiCorp Vault | Very High | Sulit | ❌ Overkill |
| D | OS Keyring (keyring library) | High | Sedang | ⚠️ Untuk desktop app |
| E | **Session-only (input tiap session)** | Highest | Repot | ✅ Paling aman tapi tidak praktis |

```python
# Opsi B: Implementasi Fernet Encryption
from cryptography.fernet import Fernet

# Generate key sekali, simpan di .env sebagai FERNET_KEY
FERNET_KEY = Fernet.generate_key()

# Encrypt private key sebelum simpan
f = Fernet(FERNET_KEY)
encrypted_pk = f.encrypt(PRIVATE_KEY.encode())

# Decrypt saat dibutuhkan
decrypted_pk = f.decrypt(encrypted_pk).decode()
```

### Opsi Whitelist User Telegram

```python
# Selalu aktifkan ini — hanya owner yang bisa gunakan bot

ALLOWED_USER_IDS = [
    123456789,   # Telegram user ID kamu
    # Tambahkan ID lain jika perlu di masa depan
]

async def security_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("❌ Unauthorized access.")
        return False
    return True
```

---

## 15 · Opsi Development Approach

### Urutan Build — 3 Jalur

#### Jalur A: Bottom-Up (Solid foundation, lambat)
```
Database schema → API client → Market scanner → 
Wallet tracker → Scoring engine → Telegram bot → 
Copy trade → TP/SL monitor
```
- **Timeline:** 12–14 minggu
- **Pro:** Setiap layer teruji sebelum layer atas dibangun
- **Cocok untuk:** Jika ini project jangka panjang

#### Jalur B: Top-Down / UX First (Cepat terasa nyata)
```
Telegram bot skeleton → /scan command (hardcoded data) →
Market scanner real → /wallets command → 
Wallet tracker real → Copy trade flow →
TP/SL → Database persistence
```
- **Timeline:** 8–10 minggu
- **Pro:** Bisa test UX lebih awal, motivasi lebih tinggi
- **Cocok untuk:** ✅ **Direkomendasikan untuk solo dev**

#### Jalur C: Feature Slice (Ship cepat, iterate)
```
Week 1-2: Bot bisa /scan dan tampilkan market (end-to-end)
Week 3-4: Bot bisa identify & display smart wallets
Week 5-6: Bot bisa copy trade 1 wallet
Week 7+:  TP/SL, multi-wallet, scoring refinement
```
- **Timeline:** 6–8 minggu ke MVP
- **Pro:** Paling cepat ke "working product"
- **Cocok untuk:** ✅ **Jika mau live sebelum WC 2026 mulai**

### Testing Strategy

| Level | Opsi | Tool | Prioritas |
|-------|------|------|-----------|
| Unit Test | Test wallet scoring algorithm | pytest | ✅ Wajib |
| Integration Test | Test API calls ke Polymarket | pytest + httpx mock | ✅ Wajib |
| E2E Test | Paper trading simulation | Script manual | ✅ Wajib sebelum real money |
| Load Test | Berapa market bisa discan simultan | locust | ⚠️ v1.1 |

---

## 16 · Opsi Feature Priority (MVP vs Full)

### Matriks Prioritas Fitur

| Fitur | Impact | Effort | Priority | Target Version |
|-------|--------|--------|----------|----------------|
| Market Scanner (WC 2026) | 🔴 Critical | Low | P0 | MVP |
| Telegram Bot Basic Commands | 🔴 Critical | Low | P0 | MVP |
| Smart Wallet Tracker | 🔴 Critical | Medium | P0 | MVP |
| Copy Trade (manual confirm) | 🔴 Critical | Medium | P0 | MVP |
| TP/SL Auto Monitor | 🟠 High | Medium | P1 | MVP |
| PnL Tracking `/pnl` | 🟠 High | Low | P1 | MVP |
| `/settings` configurator | 🟠 High | Low | P1 | MVP |
| Daily Loss Limit | 🟠 High | Low | P1 | MVP |
| Wallet Leaderboard | 🟡 Medium | Low | P2 | v1.1 |
| Multi-sport scanner | 🟡 Medium | Medium | P2 | v1.1 |
| Auto-unfollow trigger | 🟡 Medium | Low | P2 | v1.1 |
| Paper trading mode | 🟡 Medium | Medium | P2 | v1.1 |
| Backtest wallet historis | 🟢 Nice | High | P3 | v2.0 |
| Full-auto mode | 🟢 Nice | High | P3 | v2.0 |
| Multi-user support | 🟢 Nice | Very High | P3 | v2.0 |
| Web dashboard | 🟢 Nice | Very High | P3 | v2.0 |

### MVP Scope (6–8 Minggu)

```
✅ MASUK MVP
├── Market Scanner — World Cup 2026 soccer
├── /scan, /wallets, /follow, /positions, /pnl, /settings
├── Smart Wallet Tracker (WR ≥ 70%, min 20 trades)
├── Copy Trade — konfirmasi manual 1-tap
├── TP/SL auto-close
├── Daily loss limit ($1.50)
└── Position sizing (max $1.00 per trade)

❌ TIDAK DI MVP
├── Multi-sport (basketball, tennis, etc.)
├── Full-auto execute
├── Backtest feature
├── Web dashboard
└── Multi-user
```

---

## 17 · Matriks Keputusan Final

Ringkasan keputusan teknologi yang direkomendasikan untuk **PolyBot v1.0**:

| Kategori | Pilihan Terpilih | Versi |
|----------|-----------------|-------|
| **Language** | Python 3.11+ | v1.0 |
| **Async** | asyncio + aiohttp | v1.0 |
| **Telegram** | python-telegram-bot v21 | v1.0 |
| **Polymarket SDK** | py-clob-client (official) | v1.0 |
| **Market Data** | Polymarket REST API + Gamma API | v1.0 |
| **Wallet Data** | Polymarket `/trades` + The Graph fallback | v1.0 |
| **Database** | SQLite → migrate ke PostgreSQL | v1.0 → v1.1 |
| **Scheduler** | APScheduler | v1.0 |
| **Deployment** | Railway.app Hobby ($5/bulan) | v1.0 |
| **Secret Mgmt** | Fernet + .env | v1.0 |
| **Order Type** | Limit order (fallback: market) | v1.0 |
| **Execute Mode** | Semi-auto (konfirmasi 1-tap) | v1.0 |
| **Sizing Formula** | Fixed % — 20% bankroll ($1.00 max) | v1.0 |
| **Profit Target** | 8% default, configurable 3–50% | v1.0 |
| **Stop Loss** | 5% default, configurable 2–20% | v1.0 |
| **WR Threshold** | Elite ≥ 85%, Smart ≥ 70%, min 20 trades | v1.0 |
| **Daily Loss Limit** | 30% dari bankroll ($1.50 dari $5) | v1.0 |
| **Max Posisi** | 3 posisi simultan, max $1.00 each | v1.0 |
| **Build Approach** | Feature Slice (Jalur C) | v1.0 |
| **Bot Polling** | Long Polling → Webhook | v1.0 → v1.1 |
| **Monitoring** | UptimeRobot + Telegram self-alert | v1.0 |

---

> **Dokumen ini adalah living document** — update setiap sprint bersamaan dengan PRD.  
> Setiap keputusan yang berubah dari tabel ini harus didokumentasikan beserta alasannya.

---

*PolyBot Options Document v1.0 · Juni 2026 · Internal Engineering*
