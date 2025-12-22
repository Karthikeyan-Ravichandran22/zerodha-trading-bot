"""
Configuration settings for the trading bot
Load from environment variables with sensible defaults
"""

import os
from datetime import time
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# =============================================================================
# ZERODHA API CREDENTIALS
# =============================================================================
KITE_API_KEY = os.getenv("KITE_API_KEY", "")
KITE_API_SECRET = os.getenv("KITE_API_SECRET", "")
ZERODHA_USER_ID = os.getenv("ZERODHA_USER_ID", "")
ZERODHA_PASSWORD = os.getenv("ZERODHA_PASSWORD", "")
ZERODHA_PIN = os.getenv("ZERODHA_PIN", "")

# =============================================================================
# TELEGRAM NOTIFICATIONS
# =============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
NOTIFICATIONS_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

# =============================================================================
# TRADING CAPITAL & RISK MANAGEMENT
# =============================================================================
TRADING_CAPITAL = float(os.getenv("TRADING_CAPITAL", "10000"))
MAX_RISK_PER_TRADE_PERCENT = float(os.getenv("MAX_RISK_PER_TRADE_PERCENT", "2"))
MAX_DAILY_LOSS_PERCENT = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "3"))
MAX_WEEKLY_LOSS_PERCENT = float(os.getenv("MAX_WEEKLY_LOSS_PERCENT", "5"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "5"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "2"))

# Calculated values
MAX_RISK_PER_TRADE = TRADING_CAPITAL * (MAX_RISK_PER_TRADE_PERCENT / 100)  # ₹200 for 10k
MAX_DAILY_LOSS = TRADING_CAPITAL * (MAX_DAILY_LOSS_PERCENT / 100)  # ₹300 for 10k
MAX_POSITION_SIZE = TRADING_CAPITAL * 1.0  # 100% of capital per trade - MAXIMUM PROFIT!

# =============================================================================
# TRADING MODE
# =============================================================================
# paper: No real orders, just simulation
# signal: Only sends signals, no orders
# semi-auto: Asks confirmation before each order
# auto: Fully automatic (DANGEROUS!)
TRADING_MODE = os.getenv("TRADING_MODE", "paper")

# =============================================================================
# MARKET TIMING (Indian Standard Time)
# =============================================================================
def parse_time(time_str: str) -> time:
    """Parse time string to time object"""
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))

MARKET_OPEN = parse_time(os.getenv("MARKET_OPEN_TIME", "09:15"))
MARKET_CLOSE = parse_time(os.getenv("MARKET_CLOSE_TIME", "15:30"))
SQUARE_OFF_TIME = parse_time(os.getenv("SQUARE_OFF_TIME", "15:10"))
NO_NEW_TRADES_AFTER = parse_time(os.getenv("NO_NEW_TRADES_AFTER", "14:30"))
FIRST_CANDLE_TIME = parse_time("09:30")  # After first 15 mins

# Trading windows
MORNING_SESSION_START = parse_time("09:30")
MORNING_SESSION_END = parse_time("11:30")
AFTERNOON_SESSION_START = parse_time("13:00")
AFTERNOON_SESSION_END = parse_time("14:30")

# =============================================================================
# ACTIVE STRATEGIES
# =============================================================================
ACTIVE_STRATEGIES = os.getenv("ACTIVE_STRATEGIES", "vwap_bounce,orb").split(",")

# =============================================================================
# STOCK WATCHLIST
# =============================================================================
# OPTIMIZED WATCHLIST - Only stocks that showed consistent profits in backtesting
DEFAULT_WATCHLIST = [
    "PNB", "SAIL", "IDEA", "IRFC", "PFC", "BPCL", "BHEL"
]
STOCK_WATCHLIST = os.getenv("STOCK_WATCHLIST", ",".join(DEFAULT_WATCHLIST)).split(",")

# Backup watchlist for additional opportunities
BACKUP_WATCHLIST = [
    "TATAMOTORS", "SBIN", "TATASTEEL", "ITC", "COALINDIA",
    "ONGC", "NHPC", "IOC", "GAIL"
]

# =============================================================================
# INDICATOR SETTINGS
# =============================================================================
# EMA Settings
EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 50

# RSI Settings
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Supertrend Settings
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3

# VWAP (calculated automatically)

# =============================================================================
# PATHS
# =============================================================================
BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# Create directories if they don't exist
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# =============================================================================
# ORDER SETTINGS
# =============================================================================
ORDER_TYPE_ENTRY = "LIMIT"  # LIMIT or MARKET
ORDER_TYPE_SL = "SL-M"  # Stop Loss Market
ORDER_TYPE_TARGET = "LIMIT"
PRODUCT_TYPE = "MIS"  # MIS for intraday, CNC for delivery

# Slippage allowance for limit orders (percentage)
SLIPPAGE_PERCENT = 0.1

# =============================================================================
# EVENTS TO AVOID TRADING
# =============================================================================
AVOID_TRADING_EVENTS = [
    "RBI_POLICY",
    "BUDGET",
    "ELECTION_RESULTS",
    "FO_EXPIRY",  # Every Thursday
    "QUARTERLY_RESULTS"
]

# Days to avoid (0 = Monday, 4 = Friday)
AVOID_DAYS = []  # Can add specific days if needed

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_TO_FILE = True
LOG_TO_CONSOLE = True

# =============================================================================
# VALIDATION
# =============================================================================
def validate_config():
    """Validate critical configuration"""
    errors = []
    
    if TRADING_MODE == "auto" and not KITE_API_KEY:
        errors.append("KITE_API_KEY is required for auto trading mode")
    
    if TRADING_CAPITAL < 5000:
        errors.append("TRADING_CAPITAL should be at least ₹5,000")
    
    if MAX_RISK_PER_TRADE_PERCENT > 5:
        errors.append("MAX_RISK_PER_TRADE_PERCENT should not exceed 5%")
    
    if MAX_DAILY_LOSS_PERCENT > 10:
        errors.append("MAX_DAILY_LOSS_PERCENT should not exceed 10%")
    
    return errors

# Print configuration summary
def print_config():
    """Print current configuration"""
    print("\n" + "="*60)
    print("📊 TRADING BOT CONFIGURATION")
    print("="*60)
    print(f"💰 Capital: ₹{TRADING_CAPITAL:,.0f}")
    print(f"⚠️  Max Risk/Trade: ₹{MAX_RISK_PER_TRADE:,.0f} ({MAX_RISK_PER_TRADE_PERCENT}%)")
    print(f"🛑 Daily Loss Limit: ₹{MAX_DAILY_LOSS:,.0f} ({MAX_DAILY_LOSS_PERCENT}%)")
    print(f"📈 Max Trades/Day: {MAX_TRADES_PER_DAY}")
    print(f"🤖 Trading Mode: {TRADING_MODE.upper()}")
    print(f"📋 Active Strategies: {', '.join(ACTIVE_STRATEGIES)}")
    print(f"📊 Watchlist: {len(STOCK_WATCHLIST)} stocks")
    print(f"🔔 Notifications: {'Enabled' if NOTIFICATIONS_ENABLED else 'Disabled'}")
    print("="*60 + "\n")
