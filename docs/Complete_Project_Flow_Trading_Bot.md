# 🤖 Complete Project Flow - Trading Bot

## 📊 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           RAILWAY CLOUD (24/7)                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │   cloud_bot.py  │◄──►│  dashboard.py   │◄──►│  analytics_db   │          │
│  │   (Trading)     │    │  (Web UI)       │    │  (SQLite)       │          │
│  └────────┬────────┘    └────────┬────────┘    └─────────────────┘          │
│           │                      │                                          │
│           ▼                      ▼                                          │
│  ┌─────────────────┐    ┌─────────────────┐                                 │
│  │  Angel One API  │    │ Port 5050 HTTP  │ ◄─── You view on browser       │
│  │  (Broker)       │    │ (Dashboard)     │                                 │
│  └─────────────────┘    └─────────────────┘                                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## ⏰ Daily Timeline

| TIME (IST) | WHAT HAPPENS |
|------------|--------------|
| **06:00 AM** | 🔄 Bot wakes up, authenticates with Angel One<br>- Logs in using TOTP + API credentials<br>- Saves "Connected" status to file |
| **08:00 AM (Mondays)** | 📊 Weekly Stock Optimization<br>- Runs backtest on last 14 days<br>- Selects stocks with 80%+ win rate<br>- Updates watchlist for the week |
| **09:00 AM** | 📈 Market Opens (Pre-market)<br>- Bot starts fetching live prices<br>- Analyzes 15-minute candles |
| **09:45 AM** | 🟢 TRADING WINDOW STARTS<br>- Bot actively looks for signals<br>- Applies all strategy indicators |
| **09:45 - 14:15** | 🔥 ACTIVE TRADING<br>- Scans every 15 minutes for signals<br>- Executes BUY orders when conditions match<br>- Places SL and Target orders<br>- Monitors positions<br>- Updates trailing stop loss |
| **14:15 PM** | 🟡 TRADING WINDOW ENDS<br>- No new entries after this time<br>- Still monitors existing positions |
| **14:30 PM** | 🔄 First CNC Conversion Check<br>- Evaluates profitable MIS positions<br>- Converts to CNC if profit potential > ₹100 |
| **15:00 PM** | 🔄 Second CNC Conversion Check<br>- Final chance to convert before market close |
| **15:20 PM** | 📊 Daily Summary<br>- Calculates total trades, P&L, win rate<br>- Sends Telegram summary<br>- Saves to database |
| **15:30 PM** | 🔴 Market Closes<br>- MIS positions auto-squared by broker<br>- CNC positions carry forward<br>- Bot enters sleep mode |
| **15:30 - 06:00** | 😴 Bot in Sleep Mode<br>- Dashboard still accessible<br>- API calls may fail (AB1004 error)<br>- Trade history preserved in database |

---

## 🎯 Strategy Flow (Gold 93% Win Rate)

### Every 15 Minutes During Trading Window:

```
STEP 1: FETCH DATA
┌─────────────────┐
│ Get 15-min      │  ← From Angel One API
│ candlesticks    │  ← Last 50 candles for each stock
└────────┬────────┘
         ▼
STEP 2: CALCULATE INDICATORS
┌─────────────────────────────────────────────────────────────────┐
│ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐         │
│ │  RSI (2)  │ │ Stoch     │ │  CCI (20) │ │   MACD    │         │
│ │           │ │ (10,3,3)  │ │           │ │ (12,26,9) │         │
│ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘         │
│       ▼             ▼             ▼             ▼               │
│   Oversold?    %K > %D?     Below -100?   Bullish Cross?        │
└───────────────────────────────────────────────────────────────────┘
         ▼
STEP 3: CANDLE FLOW CONFIRMATION
┌─────────────────────────────────────────────────────────────────┐
│ Check last 3 candles:                                           │
│ - Are they making higher highs?                                 │
│ - Is volume increasing?                                         │
│ - Is current candle green (close > open)?                       │
└─────────────────────────────────────────────────────────────────┘
         ▼
STEP 4: SIGNAL GENERATION
┌─────────────────────────────────────────────────────────────────┐
│ IF (3+ indicators agree) AND (candle flow confirms):            │
│    → Generate BUY signal ✅                                      │
│ ELSE:                                                            │
│    → No trade ⏸️                                                 │
└─────────────────────────────────────────────────────────────────┘
         ▼
STEP 5: RISK MANAGEMENT
┌─────────────────────────────────────────────────────────────────┐
│ Calculate:                                                       │
│   Entry = Current LTP (Last Traded Price)                       │
│   Stop Loss = Entry - 1.5% (protective)                         │
│   Target = Entry + 3% (profit goal)                             │
│   Quantity = Capital / Entry (max ₹10,000 per trade)            │
└─────────────────────────────────────────────────────────────────┘
         ▼
STEP 6: ORDER EXECUTION (if auto mode)
┌─────────────────────────────────────────────────────────────────┐
│ 1. Place MARKET BUY order                                        │
│ 2. Place SL-M (Stop Loss Market) order at SL price              │
│ 3. Place LIMIT SELL order at Target price                       │
│ 4. Save position to database                                     │
│ 5. Send Telegram notification                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Files Explained

```
zeroda_trading/
│
├── cloud_bot.py          ← 🧠 BRAIN: Main trading logic
│   ├── authenticate()         - Login to Angel One
│   ├── run()                   - Main loop
│   ├── process_signal()       - Execute trades
│   ├── refresh_balance()      - Update broker status
│   └── smart_cnc_conversion() - Convert MIS to CNC
│
├── dashboard.py          ← 🖥️ WEB UI: Visual dashboard
│   ├── get_dashboard_data()   - Fetch all data for UI
│   ├── /api/dashboard         - REST API endpoint
│   ├── /api/trading-dates     - Get trade dates
│   └── HTML/CSS/JS            - Beautiful dark theme UI
│
├── analytics_db.py       ← 💾 DATABASE: SQLite storage
│   ├── save_position()        - Record new trade
│   ├── close_position()       - Update exit details
│   ├── get_positions_by_date()- Date-wise history
│   └── get_all_time_stats()   - Performance metrics
│
├── strategies/
│   ├── multi_confirmation.py  ← 📊 Gold 93% Strategy logic
│   │   ├── analyze()          - Calculate all indicators
│   │   ├── generate_signals() - Check for BUY signals
│   │   └── calculate_sl_target() - Risk calculation
│   │
│   └── commodity_scanner.py   ← (For future use)
│
├── core/
│   ├── risk_manager.py        ← ⚠️ Position limits, capital
│   ├── data_fetcher.py        ← 📈 Get price data
│   └── zerodha_client.py      ← 🔌 Broker connections
│
├── utils/
│   ├── notifications.py       ← 📱 Telegram alerts
│   ├── position_manager.py    ← 📋 Track open positions
│   ├── trade_journal.py       ← 📓 Log all trades
│   └── capital_manager.py     ← 💰 Track capital growth
│
├── config/
│   └── settings.py            ← ⚙️ Configuration
│
├── data/
│   ├── trading_analytics.db   ← SQLite database file
│   ├── zerodha_status.json    ← Broker connection status
│   ├── trades.json            ← Today's trades
│   └── positions.json         ← Current positions
│
└── Procfile                   ← 🚀 Railway deployment config
```

---

## 🔄 Trade Lifecycle

### Complete Trade Flow Example

```
1️⃣ SIGNAL GENERATION (10:15 AM)
   ┌─────────────────────────────────────────────────┐
   │ BPCL: RSI ✓ | Stoch ✓ | CCI ✓ | MACD ✓         │
   │ Candle Flow: ✓ Higher highs, Bullish           │
   │                                                 │
   │ → 🟢 BUY SIGNAL GENERATED!                     │
   └─────────────────────────────────────────────────┘
                         │
                         ▼
2️⃣ ORDER EXECUTION
   ┌─────────────────────────────────────────────────┐
   │ Entry Price: ₹364.75                            │
   │ Stop Loss:   ₹359.28 (-1.5%)                    │
   │ Target:      ₹375.69 (+3%)                      │
   │ Quantity:    27 shares                          │
   │                                                 │
   │ Angel One API: MARKET BUY order placed          │
   │ Order ID: 251226000296028                       │
   └─────────────────────────────────────────────────┘
                         │
                         ▼
3️⃣ POSITION MONITORING (10:15 AM - 3:00 PM)
   ┌─────────────────────────────────────────────────┐
   │ Every 15 seconds:                               │
   │   - Fetch current LTP from Angel One           │
   │   - Check if SL hit (₹359.28)                  │
   │   - Check if Target hit (₹375.69)              │
   │   - Update trailing SL if price moves up       │
   │                                                 │
   │ Price now: ₹365.70                              │
   │ Unrealized P&L: +₹25.65                         │
   └─────────────────────────────────────────────────┘
                         │
                         ▼
4️⃣ CNC CHECK (2:30 PM & 3:00 PM)
   ┌─────────────────────────────────────────────────┐
   │ Current Profit: ₹25.65                          │
   │ Distance to Target: ₹9.99 (₹270 potential)     │
   │                                                 │
   │ Potential Profit > ₹100?  ✅ YES               │
   │ Currently in Profit?      ✅ YES               │
   │                                                 │
   │ Decision: CONVERT to CNC ✅ (if criteria met)   │
   └─────────────────────────────────────────────────┘
                         │
                         ▼
5️⃣ POSITION CLOSE (3:18 PM - Market Close)
   ┌─────────────────────────────────────────────────┐
   │ Exit Reason: MARKET_CLOSE                       │
   │ Exit Price: ₹365.70                             │
   │ Exit Time: 15:18:08                             │
   │                                                 │
   │ REALIZED P&L: +₹51.00 ✅                        │
   │                                                 │
   │ → Saved to SQLite database                      │
   │ → Telegram notification sent                    │
   └─────────────────────────────────────────────────┘
                         │
                         ▼
6️⃣ POST-MARKET (After 3:30 PM)
   ┌─────────────────────────────────────────────────┐
   │ Database stores:                                │
   │   - Entry: ₹364.75 @ 10:15                      │
   │   - SL: ₹359.28                                 │
   │   - Target: ₹375.69                             │
   │   - Trail: ₹362.50                              │
   │   - Exit: ₹365.70 @ 15:18                       │
   │   - P&L: +₹51                                   │
   │   - Product: MIS                                │
   │   - Exit Reason: MARKET_CLOSE                   │
   │                                                 │
   │ → Viewable in Trade History (Dec 26 tab)        │
   └─────────────────────────────────────────────────┘
```

---

## 📱 Dashboard Data Flow

```
         USER BROWSER                     RAILWAY SERVER
        (Your Phone/PC)                   (dashboard.py)
              │                                │
              │  1. HTTP GET /api/dashboard    │
              │────────────────────────────────►
              │                                │
              │                    ┌───────────┴───────────┐
              │                    │  get_dashboard_data() │
              │                    │                       │
              │                    │ - Read positions.json │
              │                    │ - Read trades.json    │
              │                    │ - Query SQLite DB     │
              │                    │ - Get broker status   │
              │                    │ - Calculate P&L       │
              │                    └───────────┬───────────┘
              │                                │
              │  2. JSON Response              │
              │◄────────────────────────────────
              │  {                             │
              │    "broker": {...},           │
              │    "positions": {...},        │
              │    "trades": [...],           │
              │    "analytics": {...},        │
              │    "activity_logs": [...]     │
              │  }                             │
              │                                │
              │  3. JavaScript updates UI      │
              │  ┌─────────────────────────┐  │
              │  │ updateDashboard(data)   │  │
              │  │ updatePnLChart(data)    │  │
              │  │ updateActivityLog(data) │  │
              │  └─────────────────────────┘  │
              │                                │
              │  4. Repeat every 3 seconds     │
              │────────────────────────────────►
              │                                │
```

---

## 📊 Database Tables

### `positions` table (Trade History)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| date | TEXT | Trade date (2025-12-26) |
| symbol | TEXT | Stock name (BPCL) |
| signal | TEXT | BUY or SELL |
| entry_price | REAL | Entry price (364.75) |
| entry_time | TEXT | Entry time (10:15:23) |
| quantity | INTEGER | Shares (27) |
| stop_loss | REAL | SL price (359.28) |
| target | REAL | Target price (375.69) |
| trail_sl | REAL | Trailing SL (362.50) |
| exit_price | REAL | Exit price (365.70) |
| exit_time | TEXT | Exit time (15:18:08) |
| exit_reason | TEXT | TARGET_HIT / SL_HIT / MARKET_CLOSE |
| product_type | TEXT | MIS or CNC |
| pnl | REAL | Profit/Loss (+51.00) |
| status | TEXT | OPEN or CLOSED |

### `daily_summary` table

| Column | Type | Description |
|--------|------|-------------|
| date | TEXT | Date |
| total_trades | INTEGER | Number of trades |
| winning_trades | INTEGER | Profitable trades |
| losing_trades | INTEGER | Loss trades |
| total_pnl | REAL | Total P&L for the day |
| win_rate | REAL | Win percentage |

---

## 🔐 Environment Variables (Railway)

| Variable | Description |
|----------|-------------|
| `ANGEL_API_KEY` | Angel One API key |
| `ANGEL_CLIENT_ID` | Your Angel One client ID |
| `ANGEL_PASSWORD` | Login password |
| `ANGEL_TOTP_TOKEN` | TOTP secret for 2FA |
| `TRADING_MODE` | `auto` for live trading, `paper` for simulation |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications |
| `TELEGRAM_CHAT_ID` | Telegram chat ID |

---

## 🚀 Version History

| Tag | Date | Features |
|-----|------|----------|
| `v1.0-stable` | Dec 26, 2025 | Core trading, dashboard, position tracking |
| `v1.1-smart-conversion` | Dec 26, 2025 | Added Smart CNC Conversion (MIS→CNC at 2:30 PM & 3:00 PM) |
| `v1.2-trade-history` | Dec 27, 2025 | Persistent SQLite database, date-wise history viewing |

---

## 🔧 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard HTML page |
| `/api/dashboard` | GET | All dashboard data (JSON) |
| `/api/trading-dates` | GET | List of dates with trades |
| `/api/positions/<date>` | GET | Positions for specific date |
| `/api/analytics` | GET | Performance statistics |
| `/api/health` | GET | Server health check |

---

## ⚠️ Known Limitations

1. **After Market Hours (AB1004 Error)**: Angel One API returns errors for balance/RMS after 4 PM. This is normal and the bot preserves the last known state.

2. **TOTP Expiry**: The TOTP token needs to be regenerated if Angel One requires re-login (rare).

3. **Railway Ephemeral Storage**: SQLite database resets on new deployments. Consider external database for production.

---

## ✅ Summary

**What We Built:**
1. ✅ Automated trading bot using Gold 93% Win Rate strategy
2. ✅ Real-time web dashboard with live updates
3. ✅ SQLite database for persistent trade history
4. ✅ Smart CNC conversion to protect profitable positions
5. ✅ Telegram notifications for trade alerts
6. ✅ Sunday weekly stock optimization
7. ✅ Full trade history with date picker

**Running On:**
- Railway Cloud (24/7 uptime)
- Angel One API (broker)
- Dashboard: https://worker-production-65d3.up.railway.app

---

*Last Updated: December 27, 2025*
