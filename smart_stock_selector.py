#!/usr/bin/env python3
"""
🎯 SMART STOCK SELECTOR & OPTIMIZER
====================================

This script:
1. Takes a smart pre-selected list (Nifty stocks, F&O stocks)
2. Backtests each with our strategy
3. Filters only 80%+ win rate stocks
4. Ranks by profitability
5. Auto-adjusts to your capital

Usage:
    python smart_stock_selector.py              # Run with default capital
    python smart_stock_selector.py --capital 20000   # Custom capital
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import argparse
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

# ============================================
# SMART PRE-SELECTED STOCKS
# These are already filtered for:
# - High liquidity
# - F&O eligible
# - Price suitable for small capital
# ============================================

SMART_STOCK_LIST = {
    # PSU Banks - High volume, affordable
    "SBIN.NS": {"name": "SBI", "sector": "PSU Bank"},
    "PNB.NS": {"name": "PNB", "sector": "PSU Bank"},
    "BANKBARODA.NS": {"name": "Bank of Baroda", "sector": "PSU Bank"},
    "CANBK.NS": {"name": "Canara Bank", "sector": "PSU Bank"},
    "UNIONBANK.NS": {"name": "Union Bank", "sector": "PSU Bank"},
    
    # Private Banks - Good volatility
    "YESBANK.NS": {"name": "Yes Bank", "sector": "Private Bank"},
    "IDFCFIRSTB.NS": {"name": "IDFC First Bank", "sector": "Private Bank"},
    "FEDERALBNK.NS": {"name": "Federal Bank", "sector": "Private Bank"},
    "INDUSINDBK.NS": {"name": "IndusInd Bank", "sector": "Private Bank"},
    
    # Metal & Mining - High volatility
    "TATASTEEL.NS": {"name": "Tata Steel", "sector": "Metal"},
    "SAIL.NS": {"name": "SAIL", "sector": "Metal"},
    "HINDALCO.NS": {"name": "Hindalco", "sector": "Metal"},
    "JSWSTEEL.NS": {"name": "JSW Steel", "sector": "Metal"},
    "VEDL.NS": {"name": "Vedanta", "sector": "Metal"},
    "NMDC.NS": {"name": "NMDC", "sector": "Metal"},
    
    # Power & Energy - Good trends
    "TATAPOWER.NS": {"name": "Tata Power", "sector": "Power"},
    "NTPC.NS": {"name": "NTPC", "sector": "Power"},
    "POWERGRID.NS": {"name": "Power Grid", "sector": "Power"},
    "NHPC.NS": {"name": "NHPC", "sector": "Power"},
    "IRFC.NS": {"name": "IRFC", "sector": "Finance"},
    "PFC.NS": {"name": "PFC", "sector": "Finance"},
    "RECLTD.NS": {"name": "REC", "sector": "Finance"},
    
    # Telecom - High volume
    "IDEA.NS": {"name": "Vodafone Idea", "sector": "Telecom"},
    
    # Oil & Gas
    "ONGC.NS": {"name": "ONGC", "sector": "Oil & Gas"},
    "IOC.NS": {"name": "IOC", "sector": "Oil & Gas"},
    "BPCL.NS": {"name": "BPCL", "sector": "Oil & Gas"},
    "GAIL.NS": {"name": "GAIL", "sector": "Oil & Gas"},
    
    # IT - Mid cap
    "WIPRO.NS": {"name": "Wipro", "sector": "IT"},
    "TECHM.NS": {"name": "Tech Mahindra", "sector": "IT"},
    "MPHASIS.NS": {"name": "Mphasis", "sector": "IT"},
    
    # Auto & Others
    "ASHOKLEY.NS": {"name": "Ashok Leyland", "sector": "Auto"},
    "TATAMOTORS.NS": {"name": "Tata Motors", "sector": "Auto"},
    "M&M.NS": {"name": "M&M", "sector": "Auto"},
    "ZOMATO.NS": {"name": "Zomato", "sector": "Consumer"},
    "PAYTM.NS": {"name": "Paytm", "sector": "Fintech"},
    
    # Infra
    "ADANIPORTS.NS": {"name": "Adani Ports", "sector": "Infra"},
    "DLF.NS": {"name": "DLF", "sector": "Real Estate"},
    "GODREJPROP.NS": {"name": "Godrej Properties", "sector": "Real Estate"},
}


def backtest_stock(symbol, name, capital=10000, leverage=5, period="14d"):
    """Backtest a single stock with our strategy"""
    
    buying_power = capital * leverage
    brokerage = 40
    
    try:
        data = yf.download(symbol, period=period, interval="15m", progress=False)
        if hasattr(data.columns, "levels") and data.columns.nlevels > 1:
            data.columns = data.columns.droplevel(1)
        
        if len(data) < 50:
            return None
        
        data['close'] = data['Close']
        data['high'] = data['High']
        data['low'] = data['Low']
        data['open'] = data['Open']
        
        current_price = data['close'].iloc[-1]
        
        # Skip if price too high for capital
        if current_price > buying_power * 0.5:
            return None
        
        qty = int(buying_power / current_price)
        if qty < 1:
            return None
            
        # Trail offset based on price volatility
        volatility = (data['high'] - data['low']).mean() / current_price * 100
        trail_pct = max(0.3, min(1.5, volatility * 0.5))
        TRAIL_OFFSET = current_price * trail_pct / 100
        
        # Calculate indicators
        high = data['high']
        low = data['low']
        close = data['close']
        opn = data['open']
        
        delta_ind = close.diff()
        gain = delta_ind.where(delta_ind > 0, 0).rolling(2).mean()
        loss_ind = (-delta_ind.where(delta_ind < 0, 0)).rolling(2).mean()
        rs = gain / loss_ind
        data['rsi'] = 100 - (100 / (1 + rs))
        
        lowest_low = low.rolling(10).min()
        highest_high = high.rolling(10).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        data['stoch_k'] = k.rolling(3).mean()
        data['stoch_d'] = data['stoch_k'].rolling(3).mean()
        
        tp = (high + low + close) / 3
        sma_tp = tp.rolling(20).mean()
        mean_dev = tp.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())))
        data['cci'] = (tp - sma_tp) / (0.015 * mean_dev)
        
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        data['macd'] = ema12 - ema26
        data['macd_signal'] = data['macd'].ewm(span=9).mean()
        
        data['is_red'] = close < opn
        
        MIN_INDICATORS = 3
        HIGHER_TF_CANDLES = 8
        LOWER_TF_CANDLES = 4
        
        trades = []
        in_trade = False
        entry_price = 0
        trail_active = False
        trail_sl = 0
        trade_type = None
        
        for i in range(50, len(data)):
            curr = data.iloc[i]
            
            if pd.isna(curr['rsi']) or pd.isna(curr['stoch_k']) or pd.isna(curr['cci']) or pd.isna(curr['macd']):
                continue
            
            # SELL signal
            bear_count = sum([data.iloc[i-j]['is_red'] for j in range(min(HIGHER_TF_CANDLES, i)) if i-j >= 0])
            higher_bear = bear_count >= HIGHER_TF_CANDLES * 0.6
            red_lower = sum([data.iloc[i-j]['is_red'] for j in range(min(LOWER_TF_CANDLES, i)) if i-j >= 0])
            all_red = red_lower >= LOWER_TF_CANDLES - 1
            
            sell_ind = 0
            if curr['stoch_k'] < curr['stoch_d']: sell_ind += 1
            if curr['rsi'] < 50: sell_ind += 1
            if curr['cci'] < 0: sell_ind += 1
            if curr['macd'] < curr['macd_signal']: sell_ind += 1
            
            sell_signal = higher_bear and all_red and sell_ind >= MIN_INDICATORS
            
            # BUY signal
            bull_count = sum([not data.iloc[i-j]['is_red'] for j in range(min(HIGHER_TF_CANDLES, i)) if i-j >= 0])
            higher_bull = bull_count >= HIGHER_TF_CANDLES * 0.6
            green_lower = sum([not data.iloc[i-j]['is_red'] for j in range(min(LOWER_TF_CANDLES, i)) if i-j >= 0])
            all_green = green_lower >= LOWER_TF_CANDLES - 1
            
            buy_ind = 0
            if curr['stoch_k'] > curr['stoch_d']: buy_ind += 1
            if curr['rsi'] > 50: buy_ind += 1
            if curr['cci'] > 0: buy_ind += 1
            if curr['macd'] > curr['macd_signal']: buy_ind += 1
            
            buy_signal = higher_bull and all_green and buy_ind >= MIN_INDICATORS
            
            curr_high = curr['high']
            curr_low = curr['low']
            curr_close = curr['close']
            
            if in_trade:
                if trade_type == 'SELL':
                    if not trail_active and curr_low <= entry_price - TRAIL_OFFSET:
                        trail_active = True
                        trail_sl = curr_low + TRAIL_OFFSET
                    
                    if trail_active:
                        trail_sl = min(trail_sl, curr_low + TRAIL_OFFSET)
                        if curr_high >= trail_sl:
                            move = entry_price - trail_sl
                            pnl = move * qty - brokerage
                            trades.append({"pnl": pnl, "result": "WIN" if pnl > 0 else "LOSS"})
                            in_trade = False
                            trail_active = False
                
                elif trade_type == 'BUY':
                    if not trail_active and curr_high >= entry_price + TRAIL_OFFSET:
                        trail_active = True
                        trail_sl = curr_high - TRAIL_OFFSET
                    
                    if trail_active:
                        trail_sl = max(trail_sl, curr_high - TRAIL_OFFSET)
                        if curr_low <= trail_sl:
                            move = trail_sl - entry_price
                            pnl = move * qty - brokerage
                            trades.append({"pnl": pnl, "result": "WIN" if pnl > 0 else "LOSS"})
                            in_trade = False
                            trail_active = False
            
            if not in_trade:
                if sell_signal:
                    in_trade = True
                    trade_type = 'SELL'
                    entry_price = curr_close
                    trail_active = False
                elif buy_signal:
                    in_trade = True
                    trade_type = 'BUY'
                    entry_price = curr_close
                    trail_active = False
        
        if not trades:
            return None
        
        wins = len([t for t in trades if t['result'] == 'WIN'])
        total_pnl = sum([t['pnl'] for t in trades])
        win_rate = wins / len(trades) * 100
        
        return {
            "symbol": symbol,
            "name": name,
            "price": round(current_price, 2),
            "qty": qty,
            "trades": len(trades),
            "wins": wins,
            "losses": len(trades) - wins,
            "win_rate": round(win_rate, 1),
            "pnl": round(total_pnl, 2),
            "trail_pct": round(trail_pct, 2),
        }
        
    except Exception as e:
        return None


def run_smart_selector(capital=10000, min_win_rate=80, leverage=5):
    """Run the smart stock selector"""
    
    print("="*80)
    print("🎯 SMART STOCK SELECTOR & OPTIMIZER")
    print("="*80)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"💰 Capital: Rs {capital:,}")
    print(f"💰 Leverage: {leverage}x")
    print(f"💰 Buying Power: Rs {capital * leverage:,}")
    print(f"🎯 Min Win Rate: {min_win_rate}%")
    print(f"📊 Stocks to Scan: {len(SMART_STOCK_LIST)}")
    print("="*80)
    print()
    print("🔍 Scanning stocks...")
    print()
    
    results = []
    
    for symbol, info in SMART_STOCK_LIST.items():
        result = backtest_stock(symbol, info['name'], capital, leverage)
        if result:
            results.append(result)
            emoji = "✅" if result['win_rate'] >= min_win_rate else "⚠️"
            print(f"   {emoji} {result['name']:<15} | WR: {result['win_rate']:>5.1f}% | P&L: Rs {result['pnl']:>+8,.0f} | Trades: {result['trades']}")
        else:
            print(f"   ❌ {info['name']:<15} | Skipped (no data/trades)")
    
    # Filter by win rate
    qualified = [r for r in results if r['win_rate'] >= min_win_rate]
    qualified = sorted(qualified, key=lambda x: x['pnl'], reverse=True)
    
    print()
    print("="*80)
    print(f"🏆 QUALIFIED STOCKS (Win Rate >= {min_win_rate}%)")
    print("="*80)
    print()
    
    if qualified:
        print(f"{'#':<3} {'STOCK':<15} {'PRICE':>10} {'QTY':>6} {'TRADES':>7} {'WINS':>5} {'WIN %':>7} {'P&L':>12}")
        print("-"*80)
        
        for i, r in enumerate(qualified, 1):
            print(f"{i:<3} {r['name']:<15} Rs {r['price']:>7,.0f} {r['qty']:>6} {r['trades']:>7} {r['wins']:>5} {r['win_rate']:>6.1f}% Rs {r['pnl']:>+10,.0f}")
        
        # Summary
        total_pnl = sum([r['pnl'] for r in qualified])
        avg_win_rate = np.mean([r['win_rate'] for r in qualified])
        
        print("-"*80)
        print()
        print("📊 SUMMARY:")
        print(f"   Qualified Stocks:   {len(qualified)}")
        print(f"   Average Win Rate:   {avg_win_rate:.1f}%")
        print(f"   Total 2-Week P&L:   Rs {total_pnl:+,.0f}")
        print(f"   Monthly Projection: Rs {total_pnl * 2:+,.0f}")
        print()
        
        # Save to watchlist
        watchlist = {
            "description": "Auto-generated by Smart Stock Selector",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "capital": capital,
            "leverage": leverage,
            "min_win_rate": min_win_rate,
            "active_stocks": []
        }
        
        for r in qualified:
            watchlist["active_stocks"].append({
                "symbol": r['name'],
                "nse_symbol": r['symbol'],
                "name": r['name'],
                "trail_percent": r['trail_pct'],
                "enabled": True,
                "win_rate": r['win_rate'],
                "expected_pnl": r['pnl']
            })
        
        # Save
        os.makedirs("config", exist_ok=True)
        with open("config/smart_watchlist.json", 'w') as f:
            json.dump(watchlist, f, indent=2)
        
        print(f"✅ Saved {len(qualified)} stocks to config/smart_watchlist.json")
        
    else:
        print("⚠️ No stocks qualified with the given criteria")
        print("   Try lowering min_win_rate to 70%")
    
    print()
    print("="*80)
    
    return qualified


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Smart Stock Selector')
    parser.add_argument('--capital', type=int, default=10000, help='Trading capital')
    parser.add_argument('--min-wr', type=int, default=80, help='Minimum win rate %')
    parser.add_argument('--leverage', type=int, default=5, help='Leverage multiplier')
    
    args = parser.parse_args()
    run_smart_selector(args.capital, args.min_wr, args.leverage)
