# 🤖 Automated Trading Bot

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

---

## 🏆 SUPPORTED BROKERS

| Broker | Status | Token Needed |
|--------|--------|--------------|
| **Angel One** | ✅ PRIMARY | Auto-login (TOTP) |
| Zerodha | 🔄 Backup | Daily token refresh |

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

## 🌅 DAILY MORNING ROUTINE (Do This Every Trading Day!)

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

## 📊 Bot Schedule:
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

## � Current Watchlist (Auto-optimized):
```
PNB, SAIL, IDEA, IRFC, PFC, BPCL, BHEL
```
*Updated automatically every Sunday based on performance*

---

## 📈 Expected Results:
| Metric | Value |
|--------|-------|
| Signals/Day | 3-8 |
| Win Rate | 50-55% |
| Net Profit/Day | ₹50-200 (after brokerage) |
| Monthly Profit | ₹1,000-4,000 |

---

## 📱 Telegram Alerts:
You'll receive alerts for:
- 🟢 Trade signals (BUY/SELL)
- 💚💔 Trade exits (profit/loss)
- 📊 Daily summary

---

## 🛠️ Prerequisites
1. **Zerodha Kite Connect API** subscription (₹2,000/month)
   - Sign up at: https://kite.trade
2. Python 3.8+
3. Active Zerodha trading account

## 📁 Project Structure
```
zeroda_trading/
├── config/
│   └── settings.py          # API keys and configuration
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py     # Base strategy class
│   ├── vwap_bounce.py       # VWAP Bounce strategy
│   ├── orb_strategy.py      # Opening Range Breakout
│   ├── ema_crossover.py     # EMA Crossover strategy
│   └── gap_and_go.py        # Gap and Go strategy
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
├── backtest/
│   ├── __init__.py
│   └── backtester.py        # Strategy backtesting
├── logs/                    # Trade logs
├── main.py                  # Main entry point
├── paper_trade.py           # Paper trading mode
├── requirements.txt         # Dependencies
└── .env.example             # Environment variables template
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd zeroda_trading
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
cp .env.example .env
# Edit .env with your Zerodha API credentials
```

### 3. Run Paper Trading First (RECOMMENDED)
```bash
python paper_trade.py
```

### 4. Run Live Trading (After Testing)
```bash
python main.py
```

## 🎯 Implemented Strategies
1. **Gap and Go** - Trade morning gaps with volume confirmation
2. **VWAP Bounce** - Buy/sell at VWAP support/resistance
3. **Opening Range Breakout** - Trade 15-min range breakouts
4. **EMA Crossover** - 9/21 EMA crossover signals

## ⚙️ Risk Management Features
- ✅ Position sizing based on 1-2% risk per trade
- ✅ Maximum daily loss limit (3%)
- ✅ Maximum trades per day limit
- ✅ Automatic square-off before 3:15 PM
- ✅ No trading during high volatility events
- ✅ Real-time P&L monitoring

## 📱 Notifications
- Telegram alerts for trade signals
- Email notifications for daily summary
- Audio alerts for entry/exit signals

## 🔒 Safety Features
- Paper trading mode for testing
- Manual approval mode (confirm before each trade)
- Kill switch for emergency stop
- Daily loss limit auto-stop

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

## 📊 Backtesting
Test strategies with historical data:
```bash
python -m backtest.backtester --strategy vwap_bounce --days 30
```

## 🆘 Support
- Zerodha Kite Connect Docs: https://kite.trade/docs/connect/v3/
- Issues: Create GitHub issue

## 📜 License
MIT License - Use at your own risk!
