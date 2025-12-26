# 🤖 Automated Trading Bot

## 📌 Current Version: `v1.0-stable`
> Created: December 26, 2025 | Tag: `v1.0-stable`

---

## ⚠️ IMPORTANT DISCLAIMER
- Trading in stock market involves **substantial risk of loss**
- This bot is for **educational purposes only**
- Past performance doesn't guarantee future results
- **Never risk money you can't afford to lose**
- Start with **paper trading** before using real money

---

## 🔗 QUICK LINKS (Bookmark These!)

| Purpose | Link |
|---------|------|
| 📊 **Live Dashboard** | [https://worker-production-65d3.up.railway.app](https://worker-production-65d3.up.railway.app) |
| ⚙️ **Railway Dashboard** | [https://railway.app/dashboard](https://railway.app/dashboard) |
| 📱 **Telegram Bot** | [@karthikeyantrades_bot](https://t.me/karthikeyantrades_bot) |
| 🏷️ **Stable Version Tag** | `v1.0-stable` |

---

## 🎯 v1.0-stable Features (Production Ready!)

### ✅ Premium Web Dashboard
- **Real-time Clock** - IST timezone display with live updating
- **Live Stats Cards** - Open positions count, today's trades, P&L
- **Broker Info** - Angel One account name and balance
- **Activity Log** - Live scrolling activity feed

### ✅ Position Cards with Full Details
| Field | Description |
|-------|-------------|
| **Entry Price** | Actual buy/entry price with entry time |
| **Stop Loss** | Auto-calculated 1.5% below entry (for BUY) |
| **Target** | Auto-calculated 3% above entry (for BUY) |
| **Trail SL** | Trailing stop loss that moves with profit |
| **Exit Price** | **Actual sell average price** (from Angel One API) |

### ✅ Exit Reason Display
| Badge | Meaning |
|-------|---------|
| 🎯 **TARGET HIT** | Position closed at target price |
| ⛔ **SL HIT** | Position closed at stop loss |
| ⏰ **MARKET CLOSE** | Position squared off at market close |

### ✅ Segment Tags
| Tag | Color | Meaning |
|-----|-------|---------|
| **EQUITY** | Green | Regular stock trading |
| **OPTIONS** | Purple | Options trading (CE/PE) |
| **COMMODITY** | Orange | MCX commodity trading |
| **FUTURES** | Blue | Futures trading |

### ✅ Accurate P&L Calculation
- Uses **actual sell price** (`sellavgprice`) from Angel One API
- NOT the LTP (Last Traded Price) which shows current market price
- Matches exactly with Angel One mobile app

---

## 🔄 Version Control & Rollback

### Git Tag System
This project uses Git tags for version control. Tags are permanent bookmarks to specific commits.

### Current Tags
```bash
git tag          # List all tags
# Output: v1.0-stable
```

### How to Rollback
If something breaks after an update:
```bash
# Switch to stable version
git checkout v1.0-stable

# Force deploy the stable version
git checkout -b temp-stable
git push origin main --force
```

### View Tag Details
```bash
git show v1.0-stable
```
Shows: creator, date, description, and code changes included.

### Creating New Version Tags
After making improvements:
```bash
git tag -a v1.1-stable -m "Added feature XYZ"
git push origin v1.1-stable
```

---

## 🏆 SUPPORTED BROKERS

| Broker | Status | Token Needed |
|--------|--------|--------------|
| **Angel One** | ✅ PRIMARY | Auto-login (TOTP) |
| Zerodha | 🔄 Backup | Daily token refresh |

---

## 📈 STOCK TRADING PIPELINE

### Smart Stock Selection
- **Automatic Stock Scanner** - Scans 40+ quality stocks
- **80%+ Win Rate Filter** - Only trades high-probability stocks
- **Weekly Refresh** - Updates watchlist every Monday 8 AM
- **Capital Aware** - Adjusts to your Angel One balance

### How It Works
```
Every Monday 8 AM:
1. Scanner runs → Tests each stock with our strategy
2. Filters 80%+ win rate stocks
3. Updates watchlist automatically
4. Sends Telegram alert with selected stocks

Monday - Friday (9:15 AM - 3:30 PM):
1. Bot scans watchlist for signals
2. Places orders on Angel One (MIS - Intraday)
3. Manages trailing stop loss
4. Sends trade alerts via Telegram
```

### Commands
```bash
# Run stock scanner now
python smart_stock_selector.py --capital 10000

# Manage watchlist
python manage_watchlist.py           # View watchlist
python manage_watchlist.py add TCS   # Add stock
python manage_watchlist.py remove TCS # Remove stock

# Start trading bot
python main.py                       # Full pipeline
python main.py --scan-now            # Scan and start
```

---

## 🚀 FEATURES

### ✅ AUTO Trading (Full Automation)
- **Automatic Order Execution** - Bot places real orders on Angel One
- **Auto Stop Loss (SL-M)** - Stop loss orders placed immediately after entry
- **Auto Target (LIMIT)** - Limit orders for automatic profit booking
- **OCO Logic** - When SL/Target hits, auto-cancels the other order
- **Position Tracking** - Knows all open positions
- **Duplicate Prevention** - Won't re-enter same stock

### ✅ Analytics & Tracking
- **🌐 Live Web Dashboard** - [https://worker-production-65d3.up.railway.app](https://worker-production-65d3.up.railway.app)
- **Balance Refresh** - Updates every 5 minutes
- **Trade Journal (SQLite)** - Database stores all trades for analysis
- **Performance Dashboard** - Win rate, P&L, best/worst trades
- **Daily Summary** - Beautiful end-of-day report

### ✅ Signal Detection
- **Multi-Confirmation Strategy** - 6 indicators for entry (VWAP, EMA, RSI, Supertrend, Volume, Price Action)
- **Automatic Weekly Stock Optimization** - Every Sunday at 6 PM
- **Real-time Telegram Alerts** - Trade signals, exits, P&L notifications
- **Brokerage Calculator** - Shows NET profit after all charges

### ✅ Angel One Brokerage Charges
- **Brokerage**: ₹20 flat per executed order
- **STT**: 0.025% on sell side
- **Transaction**: 0.00345% NSE
- **GST**: 18% on brokerage + transaction
- **SEBI**: ₹10 per crore
- **Stamp Duty**: 0.003% on buy side

### ✅ Professional Filters
- **Market Sentiment Filter** - Skips trades against NIFTY trend
- **Time-Based Filters** - Avoids volatile periods (9:15-9:45, 2:15-3:30)
- **Profitability Check** - Skips trades with <₹20 net profit
- **Trailing Stop Loss** - Moves SL to breakeven and locks profits

### ✅ Capital Growth Mode 📈
- **Dynamic Position Sizing** - Larger trades as capital grows
- **Weekly Compounding** - Profits reinvested every Sunday
- **Drawdown Protection** - Reduces size during losing streaks
- **High Water Mark Tracking** - Knows your peak equity

### ✅ Risk Management
- 2% max risk per trade
- 3% max daily loss limit
- Automatic position sizing
- Daily trade limits
- Max positions limit

---

## 🏗️ PROJECT ARCHITECTURE

### Key Files

| File | Purpose |
|------|---------|
| `cloud_bot.py` | Main trading bot with Angel One integration |
| `dashboard.py` | Premium web dashboard (Flask) |
| `smart_stock_selector.py` | Automatic stock screening |
| `manage_watchlist.py` | Watchlist management |
| `main.py` | Entry point for local trading |

### Backend Data Flow (cloud_bot.py)
```
1. _fetch_angel_positions()  → Fetches positions from Angel One API
2. _fetch_angel_trades()     → Fetches executed trades
3. _update_dashboard_files() → Saves JSON files for dashboard
4. refresh_balance()         → Updates broker balance
```

### Dashboard Data Flow (dashboard.py)
```
1. /api/dashboard        → Returns JSON with all dashboard data
2. updateDashboard()     → JavaScript function that fetches data
3. renderPositionCard()  → Renders each position with details
4. Auto-refresh          → Every 30 seconds
```

### Position Data Structure
```json
{
  "SYMBOL": {
    "symbol": "BPCL",
    "entry_price": 364.75,
    "ltp": 366.00,
    "exit_price": 365.70,      // Actual sell price (NEW in v1.0)
    "sl_price": 359.28,        // Auto-calculated 1.5%
    "target_price": 375.69,    // Auto-calculated 3%
    "trail_sl": 359.28,
    "pnl": 51.0,
    "realised_pnl": 51.0,
    "segment": "EQUITY",
    "exit_reason": "MARKET_CLOSE"  // TARGET_HIT, SL_HIT, or MARKET_CLOSE
  }
}
```

---

## 📊 Bot Schedule

| Time | Action |
|------|--------|
| 9:00 AM | Login to Zerodha, add token |
| 9:15 AM | Market opens |
| 9:45 AM | **Bot starts scanning** (avoids opening volatility) |
| 9:45 AM - 2:15 PM | Active trading + Telegram alerts |
| 2:15 PM | Trading stops (avoids closing volatility) |
| 3:30 PM | Daily summary on Telegram |
| **Sunday 6 PM** | **Weekly stock optimization** |

---

## 📌 Current Watchlist (Auto-optimized)
```
PNB, SAIL, IDEA, IRFC, PFC, BPCL, BHEL
```
*Updated automatically every Sunday based on performance*

---

## 📈 Expected Results

| Metric | Value |
|--------|-------|
| Signals/Day | 3-8 |
| Win Rate | 50-55% |
| Net Profit/Day | ₹50-200 (after brokerage) |
| Monthly Profit | ₹1,000-4,000 |

---

## 📱 Telegram Alerts
You'll receive alerts for:
- 🟢 Trade signals (BUY/SELL)
- 💚💔 Trade exits (profit/loss)
- 📊 Daily summary

---

## 🌅 DAILY MORNING ROUTINE (Zerodha Users)

### ⏰ Before 9:15 AM (Market Open):

#### Step 1: Open Login URL
👉 **Click this link:**
```
https://kite.zerodha.com/connect/login?api_key=b1coqi5fcj7stbf9&v=3
```

#### Step 2: Login with Your Credentials
- **User ID:** UW5364
- **Password:** Your password
- **PIN:** Your 6-digit PIN

#### Step 3: After Login, You'll Be Redirected To:
```
http://127.0.0.1:5000/callback?request_token=XXXXXXXX&action=login&status=success
```

#### Step 4: Copy the Request Token
- Look for `request_token=XXXXXXXX` in the URL
- Copy ONLY the value after `=` (e.g., `ABC123XYZ`)

#### Step 5: Add Token to Railway
1. Go to: **https://railway.app/dashboard**
2. Click on your **zerodha-trading-bot** project
3. Click **Variables** tab
4. Find `REQUEST_TOKEN` (or add new if not exists)
5. Paste your token value
6. Railway will auto-redeploy (wait 1-2 minutes)

#### Step 6: Check Logs
- Go to **Deployments** tab
- Click **View Logs**
- You should see: `✅ Zerodha authenticated successfully!`

---

## 🛠️ Prerequisites
1. **Zerodha Kite Connect API** subscription (₹2,000/month)
   - Sign up at: https://kite.trade
2. Python 3.8+
3. Active trading account (Angel One or Zerodha)

---

## 📁 Project Structure
```
zeroda_trading/
├── config/
│   └── settings.py          # API keys and configuration
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py     # Base strategy class
│   ├── vwap_bounce.py       # VWAP Bounce strategy
│   └── advanced_candle_flow.py  # Main trading strategy
├── best_strategies/
│   └── gold_93_winrate_strategy.py  # Gold trading strategy (93% win rate)
├── core/
│   ├── __init__.py
│   ├── zerodha_client.py    # Kite Connect wrapper
│   ├── risk_manager.py      # Position sizing & risk management
│   ├── order_manager.py     # Order execution
│   └── data_fetcher.py      # Market data fetching
├── utils/
│   ├── __init__.py
│   ├── indicators.py        # Technical indicators
│   ├── logger.py            # Logging utility
│   └── notifications.py     # Telegram/Email alerts
├── data/
│   ├── today_trades.json    # Today's trades (for dashboard)
│   ├── stock_positions.json # Current positions (for dashboard)
│   └── zerodha_status.json  # Broker connection status
├── cloud_bot.py             # Main cloud trading bot (Railway)
├── dashboard.py             # Premium web dashboard
├── smart_stock_selector.py  # Automatic stock screening
├── manage_watchlist.py      # Watchlist management
├── main.py                  # Main entry point
├── requirements.txt         # Dependencies
└── README.md                # This file
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd zeroda_trading
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
cp .env.example .env
# Edit .env with your API credentials
```

### 3. Run Paper Trading First (RECOMMENDED)
```bash
python paper_trade.py
```

### 4. Run Live Trading (After Testing)
```bash
python main.py
```

---

## 🔧 Troubleshooting

### Dashboard Not Showing Data
1. Check Railway logs for errors
2. Verify Angel One credentials are correct
3. Ensure bot is running (not in sleep mode)

### Exit Price Shows Wrong Value
- Fixed in v1.0-stable
- Now uses `sellavgprice` from Angel One API
- Matches mobile app exactly

### JavaScript Errors in Dashboard
- Fixed in v1.0-stable
- Template literal syntax errors resolved
- Defensive coding with try-catch blocks

---

## 📚 Learning Resources

### Git Commands Used in This Project
```bash
git tag                      # List all version tags
git tag -a v1.0 -m "msg"    # Create annotated tag
git push origin v1.0         # Push tag to GitHub
git checkout v1.0            # Switch to tagged version
git show v1.0                # View tag details
```

### API Data Fields (Angel One)
```python
# Position data from Angel One API:
pos.get('buyavgprice')   # Average buy price
pos.get('sellavgprice')  # Average sell price (EXIT PRICE)
pos.get('ltp')           # Last traded price (current market)
pos.get('pnl')           # Profit/Loss
pos.get('netqty')        # Net quantity (0 = closed)
```

---

## ⚙️ Risk Management Features
- ✅ Position sizing based on 1-2% risk per trade
- ✅ Maximum daily loss limit (3%)
- ✅ Maximum trades per day limit
- ✅ Automatic square-off before 3:15 PM
- ✅ No trading during high volatility events
- ✅ Real-time P&L monitoring

---

## 📈 Usage Modes

### Mode 1: Signal Only (Safest)
Bot sends you signals, you place trades manually
```bash
python main.py --mode signal
```

### Mode 2: Semi-Automatic
Bot asks for confirmation before each trade
```bash
python main.py --mode semi-auto
```

### Mode 3: Fully Automatic (Use with caution!)
Bot places trades automatically
```bash
python main.py --mode auto
```

---

## 📊 Backtesting
Test strategies with historical data:
```bash
python -m backtest.backtester --strategy vwap_bounce --days 30
```

---

## 🆘 Support
- Zerodha Kite Connect Docs: https://kite.trade/docs/connect/v3/
- Angel One SmartAPI Docs: https://smartapi.angelbroking.com/docs
- Issues: Create GitHub issue

---

## 📜 License
MIT License - Use at your own risk!

---

## 📝 Changelog

### v1.0-stable (December 26, 2025)
- ✅ Fixed exit price to use actual sell average price (not LTP)
- ✅ Added exit reason badges (Target Hit, SL Hit, Market Close)
- ✅ Auto-calculate SL (1.5%) and Target (3%) for all positions
- ✅ Added segment tags (Equity, Options, Commodity, Futures)
- ✅ Fixed JavaScript template literal syntax errors
- ✅ IST timezone for all timestamps
- ✅ Real-time position cards with Entry, SL, Target, Trail SL, Exit
- ✅ Defensive JavaScript coding with try-catch blocks
- ✅ Live activity log with scrolling
- ✅ Broker balance and user name display

---

*Last Updated: December 26, 2025*
