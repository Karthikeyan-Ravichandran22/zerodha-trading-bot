# 🤖 Zerodha Automated Trading Bot

## ⚠️ IMPORTANT DISCLAIMER
- Trading in stock market involves **substantial risk of loss**
- This bot is for **educational purposes only**
- Past performance doesn't guarantee future results
- **Never risk money you can't afford to lose**
- Start with **paper trading** before using real money

---

## 🌅 DAILY MORNING ROUTINE (Do This Every Trading Day!)

### ⏰ Before 9:15 AM (Market Open):

#### Step 1: Open Login URL
👉 **Click this link:**
```
https://kite.zerodha.com/connect/login?api_key=1yn33ovqlmmlkxns&v=3
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

### 📊 Bot Schedule:
| Time | Action |
|------|--------|
| 9:00 AM | Login to Zerodha, add token |
| 9:15 AM | Market opens |
| 9:30 AM | Bot starts scanning for trades |
| 9:30 - 2:30 PM | Active trading |
| 3:10 PM | Auto square-off |
| 3:30 PM | Market closes |

---


## 📊 Realistic Expectations
| Capital | Realistic Daily Target | Risk Per Trade |
|---------|------------------------|----------------|
| ₹10,000 | ₹50-100 (0.5-1%) | ₹100-200 (1-2%) |
| ₹50,000 | ₹250-500 (0.5-1%) | ₹500-1000 (1-2%) |
| ₹1,00,000 | ₹500-1000 (0.5-1%) | ₹1000-2000 (1-2%) |

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
