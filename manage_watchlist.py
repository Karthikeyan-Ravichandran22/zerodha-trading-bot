#!/usr/bin/env python3
"""
📈 STOCK WATCHLIST MANAGER
==========================

This utility helps you manage your stock watchlist easily.
You can add, remove, enable/disable stocks without editing JSON files.

Usage:
    python manage_watchlist.py                    # Show current watchlist
    python manage_watchlist.py add RELIANCE       # Add a new stock
    python manage_watchlist.py remove RELIANCE    # Remove a stock
    python manage_watchlist.py enable IRFC        # Enable a stock
    python manage_watchlist.py disable SBIN       # Disable a stock
    python manage_watchlist.py list               # List all stocks
    python manage_watchlist.py backtest           # Backtest enabled stocks
"""

import json
import os
import sys
from datetime import datetime

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "config", "stock_watchlist.json")

# Common stocks with pre-configured settings
STOCK_PRESETS = {
    "SBIN": {"name": "State Bank of India", "trail_percent": 0.3},
    "TATASTEEL": {"name": "Tata Steel", "trail_percent": 0.5},
    "TATAPOWER": {"name": "Tata Power", "trail_percent": 0.4},
    "IDEA": {"name": "Vodafone Idea", "trail_percent": 1.0},
    "YESBANK": {"name": "Yes Bank", "trail_percent": 0.8},
    "IRFC": {"name": "IRFC", "trail_percent": 0.5},
    "NHPC": {"name": "NHPC", "trail_percent": 0.5},
    "PNB": {"name": "Punjab National Bank", "trail_percent": 0.5},
    "SAIL": {"name": "Steel Authority", "trail_percent": 0.6},
    "BANKBARODA": {"name": "Bank of Baroda", "trail_percent": 0.4},
    "RELIANCE": {"name": "Reliance Industries", "trail_percent": 0.3},
    "TCS": {"name": "TCS", "trail_percent": 0.3},
    "INFY": {"name": "Infosys", "trail_percent": 0.3},
    "HDFCBANK": {"name": "HDFC Bank", "trail_percent": 0.3},
    "ICICIBANK": {"name": "ICICI Bank", "trail_percent": 0.3},
    "HINDUNILVR": {"name": "Hindustan Unilever", "trail_percent": 0.3},
    "ITC": {"name": "ITC", "trail_percent": 0.4},
    "BHARTIARTL": {"name": "Bharti Airtel", "trail_percent": 0.4},
    "AXISBANK": {"name": "Axis Bank", "trail_percent": 0.4},
    "KOTAKBANK": {"name": "Kotak Bank", "trail_percent": 0.3},
    "MARUTI": {"name": "Maruti Suzuki", "trail_percent": 0.3},
    "BAJFINANCE": {"name": "Bajaj Finance", "trail_percent": 0.4},
    "ADANIENT": {"name": "Adani Enterprises", "trail_percent": 0.6},
    "ADANIPORTS": {"name": "Adani Ports", "trail_percent": 0.5},
    "ONGC": {"name": "ONGC", "trail_percent": 0.5},
    "NTPC": {"name": "NTPC", "trail_percent": 0.4},
    "POWERGRID": {"name": "Power Grid", "trail_percent": 0.4},
    "COALINDIA": {"name": "Coal India", "trail_percent": 0.5},
    "JSWSTEEL": {"name": "JSW Steel", "trail_percent": 0.5},
    "HINDALCO": {"name": "Hindalco", "trail_percent": 0.5},
    "VEDL": {"name": "Vedanta", "trail_percent": 0.6},
    "ZOMATO": {"name": "Zomato", "trail_percent": 0.6},
    "PAYTM": {"name": "Paytm", "trail_percent": 0.8},
    "DELHIVERY": {"name": "Delhivery", "trail_percent": 0.6},
}


def load_watchlist():
    """Load watchlist from JSON file"""
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, 'r') as f:
            return json.load(f)
    return {"active_stocks": [], "capital": 10000, "leverage": 5}


def save_watchlist(data):
    """Save watchlist to JSON file"""
    data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.dirname(WATCHLIST_FILE), exist_ok=True)
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Watchlist saved to {WATCHLIST_FILE}")


def show_watchlist():
    """Display current watchlist"""
    data = load_watchlist()
    stocks = data.get('active_stocks', [])
    
    print("\n" + "="*70)
    print("📈 STOCK WATCHLIST")
    print("="*70)
    print(f"💰 Capital: Rs {data.get('capital', 10000):,}")
    print(f"💰 Leverage: {data.get('leverage', 5)}x")
    print(f"📅 Last Updated: {data.get('last_updated', 'N/A')}")
    print("="*70)
    print()
    
    enabled = [s for s in stocks if s.get('enabled', True)]
    disabled = [s for s in stocks if not s.get('enabled', True)]
    
    print("✅ ENABLED STOCKS:")
    print("-"*50)
    if enabled:
        for s in enabled:
            print(f"   {s['symbol']:<15} | {s.get('name', ''):<25} | Trail: {s.get('trail_percent', 0.5)}%")
    else:
        print("   No stocks enabled")
    
    print()
    print("❌ DISABLED STOCKS:")
    print("-"*50)
    if disabled:
        for s in disabled:
            print(f"   {s['symbol']:<15} | {s.get('name', ''):<25} | Trail: {s.get('trail_percent', 0.5)}%")
    else:
        print("   No stocks disabled")
    
    print()
    print("="*70)
    print("📌 Commands: add <STOCK> | remove <STOCK> | enable <STOCK> | disable <STOCK>")
    print("="*70)


def add_stock(symbol):
    """Add a new stock to watchlist"""
    symbol = symbol.upper()
    data = load_watchlist()
    stocks = data.get('active_stocks', [])
    
    # Check if already exists
    for s in stocks:
        if s['symbol'] == symbol:
            print(f"⚠️ {symbol} already exists in watchlist")
            return
    
    # Get preset or create new
    if symbol in STOCK_PRESETS:
        preset = STOCK_PRESETS[symbol]
        new_stock = {
            "symbol": symbol,
            "nse_symbol": f"{symbol}.NS",
            "name": preset['name'],
            "trail_percent": preset['trail_percent'],
            "enabled": True
        }
    else:
        new_stock = {
            "symbol": symbol,
            "nse_symbol": f"{symbol}.NS",
            "name": symbol,
            "trail_percent": 0.5,
            "enabled": True
        }
    
    stocks.append(new_stock)
    data['active_stocks'] = stocks
    save_watchlist(data)
    print(f"✅ Added {symbol} to watchlist")


def remove_stock(symbol):
    """Remove a stock from watchlist"""
    symbol = symbol.upper()
    data = load_watchlist()
    stocks = data.get('active_stocks', [])
    
    new_stocks = [s for s in stocks if s['symbol'] != symbol]
    if len(new_stocks) == len(stocks):
        print(f"⚠️ {symbol} not found in watchlist")
        return
    
    data['active_stocks'] = new_stocks
    save_watchlist(data)
    print(f"✅ Removed {symbol} from watchlist")


def toggle_stock(symbol, enable=True):
    """Enable or disable a stock"""
    symbol = symbol.upper()
    data = load_watchlist()
    stocks = data.get('active_stocks', [])
    
    found = False
    for s in stocks:
        if s['symbol'] == symbol:
            s['enabled'] = enable
            found = True
            break
    
    if not found:
        print(f"⚠️ {symbol} not found in watchlist")
        return
    
    data['active_stocks'] = stocks
    save_watchlist(data)
    status = "enabled" if enable else "disabled"
    print(f"✅ {symbol} {status}")


def list_available():
    """List all available preset stocks"""
    print("\n" + "="*50)
    print("📋 AVAILABLE STOCKS (Presets)")
    print("="*50)
    
    for symbol, info in sorted(STOCK_PRESETS.items()):
        print(f"   {symbol:<15} | {info['name']:<25}")
    
    print()
    print("💡 To add: python manage_watchlist.py add <SYMBOL>")
    print("="*50)


def get_enabled_stocks():
    """Get list of enabled stocks (for use by trading bot)"""
    data = load_watchlist()
    stocks = data.get('active_stocks', [])
    return [s for s in stocks if s.get('enabled', True)]


def get_watchlist_config():
    """Get full watchlist config (for use by trading bot)"""
    return load_watchlist()


# Main CLI
if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_watchlist()
    else:
        command = sys.argv[1].lower()
        
        if command == "list":
            list_available()
        elif command == "show":
            show_watchlist()
        elif command == "add" and len(sys.argv) > 2:
            add_stock(sys.argv[2])
        elif command == "remove" and len(sys.argv) > 2:
            remove_stock(sys.argv[2])
        elif command == "enable" and len(sys.argv) > 2:
            toggle_stock(sys.argv[2], enable=True)
        elif command == "disable" and len(sys.argv) > 2:
            toggle_stock(sys.argv[2], enable=False)
        else:
            print("Usage:")
            print("  python manage_watchlist.py           # Show watchlist")
            print("  python manage_watchlist.py list      # List available stocks")
            print("  python manage_watchlist.py add RELIANCE")
            print("  python manage_watchlist.py remove RELIANCE")
            print("  python manage_watchlist.py enable IRFC")
            print("  python manage_watchlist.py disable SBIN")
