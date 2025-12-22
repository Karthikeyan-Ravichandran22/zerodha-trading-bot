"""
Stock Optimizer - Automatically selects best performing stocks

This module:
1. Tracks performance of each stock
2. Runs weekly backtests on candidate stocks
3. Recommends best stocks for next week
4. Auto-updates watchlist based on performance
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple
import json
import os
from loguru import logger

# Import indicators
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.indicators import calculate_vwap, calculate_rsi, calculate_ema, calculate_supertrend


class StockOptimizer:
    """Automatically optimizes stock watchlist based on performance"""
    
    # All candidate stocks to test
    ALL_CANDIDATES = [
        # Current winners
        "PNB", "SAIL", "IDEA", "IRFC", "PFC", "BPCL", "BHEL",
        # Potential candidates
        "TATAMOTORS", "SBIN", "TATASTEEL", "ITC", "COALINDIA",
        "ONGC", "NHPC", "IOC", "GAIL", "BANKBARODA", "CANBK",
        "HINDALCO", "VEDL", "NATIONALUM", "GMRINFRA", "SUZLON",
        "YESBANK", "IDFCFIRSTB", "FEDERALBNK", "INDUSINDBK",
        "ADANIPOWER", "ADANIPORTS", "ADANIENT", "POWERGRID", "NTPC"
    ]
    
    def __init__(self, capital: float = 10000, results_file: str = "stock_performance.json"):
        self.capital = capital
        self.max_position = capital
        self.max_risk = capital * 0.02  # 2% risk
        self.results_file = results_file
        self.performance_history = self._load_history()
    
    def _load_history(self) -> Dict:
        """Load historical performance data"""
        if os.path.exists(self.results_file):
            try:
                with open(self.results_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"stocks": {}, "last_update": None}
    
    def _save_history(self):
        """Save performance data"""
        with open(self.results_file, 'w') as f:
            json.dump(self.performance_history, f, indent=2, default=str)
    
    def calculate_qty(self, entry: float, sl: float) -> int:
        """Calculate position size"""
        risk_per_share = abs(entry - sl)
        if risk_per_share <= 0:
            return 0
        qty_by_risk = int(self.max_risk / risk_per_share)
        qty_by_capital = int(self.max_position / entry)
        return min(qty_by_risk, qty_by_capital)
    
    def backtest_stock(self, symbol: str, days: int = 7) -> Dict:
        """Backtest a single stock"""
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            df = ticker.history(period=f"{days}d", interval="5m")
            
            if df.empty or len(df) < 50:
                return {"symbol": symbol, "trades": 0, "pnl": 0, "win_rate": 0}
            
            trades = []
            available_dates = sorted(set(df.index.date))
            
            for trading_day in available_dates:
                df_day = df[df.index.date == trading_day].copy()
                
                if len(df_day) < 25:
                    continue
                
                df_day.columns = [c.lower() for c in df_day.columns]
                
                # Calculate indicators
                df_day['vwap'] = calculate_vwap(df_day)
                df_day['ema9'] = calculate_ema(df_day['close'], 9)
                df_day['ema21'] = calculate_ema(df_day['close'], 21)
                df_day['rsi'] = calculate_rsi(df_day['close'], 14)
                st = calculate_supertrend(df_day, 10, 3)
                df_day['st_dir'] = st['direction']
                df_day['vol_sma'] = df_day['volume'].rolling(20).mean()
                df_day['vol_ratio'] = df_day['volume'] / df_day['vol_sma']
                
                symbol_trades = 0
                
                for i in range(25, len(df_day)):
                    if symbol_trades >= 2:
                        break
                    
                    row = df_day.iloc[i]
                    
                    # Multi-confirmation check
                    conf = 0
                    if row['close'] > row['vwap']: conf += 1
                    if row['ema9'] > row['ema21']: conf += 1
                    if 45 <= row['rsi'] <= 65: conf += 1
                    if row['st_dir'] == 1: conf += 1
                    if pd.notna(row['vol_ratio']) and row['vol_ratio'] > 1.3: conf += 1
                    if row['close'] > row['open']: conf += 1
                    
                    if conf >= 5:
                        entry = row['close']
                        sl = entry * 0.997
                        target = entry * 1.005
                        qty = self.calculate_qty(entry, sl)
                        
                        for j in range(i+1, min(i+15, len(df_day))):
                            next_row = df_day.iloc[j]
                            if next_row['high'] >= target:
                                pnl = (target - entry) * qty
                                trades.append({"result": "WIN", "pnl": pnl})
                                symbol_trades += 1
                                break
                            elif next_row['low'] <= sl:
                                pnl = (sl - entry) * qty
                                trades.append({"result": "LOSS", "pnl": pnl})
                                symbol_trades += 1
                                break
            
            total_pnl = sum(t['pnl'] for t in trades)
            wins = sum(1 for t in trades if t['result'] == 'WIN')
            win_rate = (wins / len(trades) * 100) if trades else 0
            
            return {
                "symbol": symbol,
                "trades": len(trades),
                "wins": wins,
                "losses": len(trades) - wins,
                "pnl": total_pnl,
                "win_rate": win_rate
            }
            
        except Exception as e:
            logger.error(f"Error backtesting {symbol}: {e}")
            return {"symbol": symbol, "trades": 0, "pnl": 0, "win_rate": 0}
    
    def find_best_stocks(self, top_n: int = 7) -> List[str]:
        """Find the best performing stocks from all candidates"""
        logger.info(f"🔍 Testing {len(self.ALL_CANDIDATES)} stocks...")
        
        results = []
        for symbol in self.ALL_CANDIDATES:
            result = self.backtest_stock(symbol)
            results.append(result)
            
            # Update history
            if symbol not in self.performance_history["stocks"]:
                self.performance_history["stocks"][symbol] = []
            self.performance_history["stocks"][symbol].append({
                "date": str(date.today()),
                "pnl": result["pnl"],
                "win_rate": result["win_rate"],
                "trades": result["trades"]
            })
        
        # Sort by profit
        results.sort(key=lambda x: x['pnl'], reverse=True)
        
        # Get top performers (only profitable ones)
        top_stocks = [r for r in results if r['pnl'] > 0][:top_n]
        
        self.performance_history["last_update"] = str(date.today())
        self._save_history()
        
        return [r['symbol'] for r in top_stocks], results
    
    def get_recommendation(self) -> Tuple[List[str], str]:
        """Get recommended stocks for this week"""
        best_stocks, all_results = self.find_best_stocks()
        
        report = "\n📊 WEEKLY STOCK OPTIMIZATION REPORT\n"
        report += "=" * 50 + "\n\n"
        report += "TOP PERFORMERS (Use These!):\n"
        report += "-" * 50 + "\n"
        
        for i, r in enumerate([x for x in all_results if x['symbol'] in best_stocks]):
            report += f"{i+1}. {r['symbol']:<12} P&L: ₹{r['pnl']:>+8,.0f}  "
            report += f"Win Rate: {r['win_rate']:.0f}%\n"
        
        report += "\n" + "-" * 50 + "\n"
        report += f"Recommended Watchlist: {','.join(best_stocks)}\n"
        
        return best_stocks, report


def run_weekly_optimization():
    """Run weekly optimization and print results"""
    print("=" * 70)
    print("🔄 WEEKLY STOCK OPTIMIZATION")
    print("=" * 70)
    print()
    
    optimizer = StockOptimizer(capital=10000)
    best_stocks, report = optimizer.get_recommendation()
    
    print(report)
    print()
    print("=" * 70)
    print(f"📋 UPDATE YOUR WATCHLIST TO:")
    print(f"   {','.join(best_stocks)}")
    print("=" * 70)
    
    return best_stocks


if __name__ == "__main__":
    run_weekly_optimization()
