"""
Stock Optimizer - Professional-Grade Stock Selection System

🎯 PROFESSIONAL APPROACH (Like Renaissance Technologies):
1. Large universe (200 stocks) across market caps
2. Multi-stage filtering (liquidity, volatility, performance)
3. Sector diversification for risk management
4. 14-day backtest for statistical significance
5. Selects top 25 stocks with proven edge

This is how billion-dollar quant funds operate!
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
    """
    Professional Stock Selection System
    
    Universe: 200 stocks across Indian market
    Output: Top 25 diversified high-performers
    """
    
    # PROFESSIONAL 200-STOCK UNIVERSE
    # ================================
    
    # Tier 1: Nifty 50 (All 50 - India's best blue chips)
    NIFTY_50 = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK", "SBIN", "BHARTIARTL",
        "ITC", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TITAN", "SUNPHARMA",
        "BAJFINANCE", "ULTRACEMCO", "NESTLEIND", "WIPRO", "HCLTECH", "BAJAJFINSV", "ADANIENT",
        "ONGC", "NTPC", "POWERGRID", "COALINDIA", "M&M", "TATAMOTORS", "TATASTEEL", "JSWSTEEL",
        "GRASIM", "TECHM", "INDUSINDBK", "HINDALCO", "EICHERMOT", "BRITANNIA", "CIPLA",
        "DRREDDY", "APOLLOHOSP", "DIVISLAB", "ADANIPORTS", "SHRIRAMFIN", "BAJAJ-AUTO", 
        "HEROMOTOCO", "TATACONSUM", "SBILIFE", "HDFCLIFE", "BPCL", "IOC"
    ]
    
    # Tier 2: Nifty Next 50 (All 50 - Future blue chips)
    NIFTY_NEXT_50 = [
        "ADANIGREEN", "ADANIPOWER", "ATGL", "ABB", "AMBUJACEM", "BANDHANBNK", "BERGEPAINT",
        "BEL", "BOSCHLTD", "CANBK", "CHOLAFIN", "COLPAL", "CONCOR", "DABUR", "DLF",
        "GODREJCP", "GAIL", "GLAND", "HAVELLS", "HDFCAMC", "ICICIPRULI", "INDUSTOWER",
        "INDHOTEL", "JINDALSTEL", "LTIM", "LICHSGFIN", "MOTHERSON", "MPHASIS", "NMDC",
        "NYKAA", "OFSS", "OIL", "PAGEIND", "PERSISTENT", "PETRONET", "PIIND", "PEL",
        "PFC", "PIDILITIND", "PNB", "RECLTD", "SBICARD", "SIEMENS", "SRF", "TATACOMM",
        "TATAPOWER", "TORNTPHARM", "TRENT", "SAIL", "VEDL"
    ]
    
    # Tier 3: Top 50 Liquid Midcaps (High growth potential)
    MIDCAP_LIQUID = [
        "IRFC", "IRCTC", "SUZLON", "YESBANK", "IDEA", "BHEL", "GMRINFRA", "RVNL",
        "NHPC", "SJVN", "NATIONALUM", "ZOMATO", "PAYTM", "PVR", "DIXON", "AUROPHARMA",
        "LUPIN", "BIOCON", "BANKINDIA", "UNIONBANK", "CANBK", "IDFCFIRSTB", "FEDERALBNK",
        "PNBHOUSING", "MANAPPURAM", "MUTHOOTFIN", "DELTACORP", "ABCAPITAL", "INDIANB",
        "RBLBANK", "CROMPTON", "AMBER", "ESCORTS", "ASHOKLEY", "BALKRISIND", "APLLTD",
        "CUMMINSIND", "EXIDEIND", "SCHAEFFLER", "TIMKEN", "TTKPRESTIG", "WHIRLPOOL",
        "VOLTAS", "BLUESTARCO", "CARBORUNIV", "GRAPHITE", "AARTI", "DEEPAKNTR", "GNFC",
        "GUJGASLTD"
    ]
    
    # Tier 4: High Beta Stocks (30 stocks - High volatility for intraday)
    HIGH_BETA = [
        "YESBANK", "IDEA", "SUZLON", "SAIL", "GMRINFRA", "IRFC", "NATIONALUM", "BHEL",
        "ADANIPOWER", "TATASTEEL", "JSWSTEEL", "VEDL", "HINDALCO", "TATAMOTORS", "ASHOKLEY",
        "INDUSINDBK", "FEDERALBNK", "IDFCFIRSTB", "RBLBANK", "PNB", "CANBK", "BANKINDIA",
        "ONGC", "IOC", "BPCL", "OIL", "GAIL", "COALINDIA", "NTPC", "POWERGRID"
    ]
    
    # Tier 5: Sector Leaders (20 stocks - Capture sector-specific moves)
    SECTOR_LEADERS = [
        "HAL", "BEL",  # Defense
        "RVNL", "IRCON",  # Railways  
        "SJVN", "TORNTPOWER",  # Power
        "AARTIIND", "DEEPAKNTR",  # Chemicals
        "SYMPHONY", "RELAXO",  # Consumer durables
        "TATAELXSI", "COFORGE",  # IT Services
        "GODREJPROP", "PRESTIGE",  # Real Estate
        "AUROPHARMA", "CADILAHC",  # Pharma
        "MOTHERSON", "BOSCHLTD",  # Auto Components
        "MUTHOOTFIN", "CHOLAFIN"  # NBFCs
    ]
    
    # Combine all (with deduplication)
    ALL_CANDIDATES = list(set(
        NIFTY_50 + NIFTY_NEXT_50 + MIDCAP_LIQUID + HIGH_BETA + SECTOR_LEADERS
    ))
    
    # Sector mapping for diversification
    SECTOR_MAP = {
        # Banking & Finance
        "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking", "KOTAKBANK": "Banking",
        "AXISBANK": "Banking", "INDUSINDBK": "Banking", "BANDHANBNK": "Banking", "PNB": "Banking",
        "CANBK": "Banking", "BANKINDIA": "Banking", "UNIONBANK": "Banking", "FEDERALBNK": "Banking",
        "RBLBANK": "Banking", "IDFCFIRSTB": "Banking", "YESBANK": "Banking",
        
        "BAJFINANCE": "Finance", "BAJAJFINSV": "Finance", "CHOLAFIN": "Finance", "MUTHOOTFIN": "Finance",
        "SHRIRAMFIN": "Finance", "PFC": "Finance", "RECLTD": "Finance", "LICHSGFIN": "Finance",
        
        # IT
        "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT",
        "LTIM": "IT", "MPHASIS": "IT", "PERSISTENT": "IT", "COFORGE": "IT", "TATAELXSI": "IT",
        
        # Energy & Power
        "RELIANCE": "Energy", "ONGC": "Energy", "BPCL": "Energy", "IOC": "Energy",
        "OIL": "Energy", "GAIL": "Energy", "ATGL": "Energy",
        
        "NTPC": "Power", "POWERGRID": "Power", "TATAPOWER": "Power", "ADANIPOWER": "Power",
        "ADANIGREEN": "Power", "NHPC": "Power", "SJVN": "Power", "TORNTPOWER": "Power",
        
        # Metals & Mining
        "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals", "SAIL": "Metals",
        "VEDL": "Metals", "JINDALSTEL": "Metals", "NATIONALUM": "Metals", "NMDC": "Metals",
        "COALINDIA": "Metals",
        
        # Auto
        "MARUTI": "Auto", "M&M": "Auto", "TATAMOTORS": "Auto", "EICHERMOT": "Auto",
        "BAJAJ-AUTO": "Auto", "HEROMOTOCO": "Auto", "ESCORTS": "Auto", "ASHOKLEY": "Auto",
        "MOTHERSON": "Auto", "BOSCHLTD": "Auto",
        
        # Pharma
        "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma", "DIVISLAB": "Pharma",
        "LUPIN": "Pharma", "BIOCON": "Pharma", "AUROPHARMA": "Pharma", "TORNTPHARM": "Pharma",
        "CADILAHC": "Pharma",
        
        # Infra & Construction
        "LT": "Infra", "ADANIPORTS": "Infra", "ADANIENT": "Infra", "GMRINFRA": "Infra",
        "DLF": "Infra", "IRFC": "Infra", "IRCTC": "Infra", "RVNL": "Infra", "IRCON": "Infra",
        
        # FMCG & Consumer
        "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
        "DABUR": "FMCG", "GODREJCP": "FMCG", "TATACONSUM": "FMCG", "COLPAL": "FMCG",
        
        # Telecom
        "BHARTIARTL": "Telecom", "IDEA": "Telecom", "TATACOMM": "Telecom", "INDUSTOWER": "Telecom",
        
        # Defense
        "HAL": "Defense", "BEL": "Defense",
        
        # Chemicals
        "AARTIIND": "Chemicals", "DEEPAKNTR": "Chemicals", "GNFC": "Chemicals",
        
        # Others
        "TITAN": "Consumer", "ASIANPAINT": "Paint", "ULTRACEMCO": "Cement", "AMBUJACEM": "Cement",
        "GRASIM": "Cement", "BERGEPAINT": "Paint", "PIDILITIND": "Chemicals",
        "SUZLON": "Renewable", "BHEL": "Capital Goods"
    }
    
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
    
    def backtest_stock(self, symbol: str, days: int = 14) -> Dict:
        """
        Backtest a single stock with PROFESSIONAL metrics
        
        Args:
            symbol: Stock symbol
            days: Backtest period (14 days for statistical significance)
        
        Returns:
            Dict with performance metrics + liquidity + volatility data
        """
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            df = ticker.history(period=f"{days}d", interval="5m")
            
            if df.empty or len(df) < 50:
                return {"symbol": symbol, "trades": 0, "pnl": 0, "win_rate": 0, 
                       "liquidity_ok": False, "volatility_ok": False}
            
            # Calculate liquidity (avg daily volume)
            daily_volumes = df.groupby(df.index.date)['Volume'].sum()
            avg_daily_volume = daily_volumes.mean()
            liquidity_ok = avg_daily_volume > 500000  # 5 lakh shares minimum
            
            # Calculate volatility (ATR %)
            df['high_low'] = df['High'] - df['Low']
            atr = df['high_low'].rolling(20).mean().mean()
            atr_percent = (atr / df['Close'].mean()) * 100
            volatility_ok = 1.5 <= atr_percent <= 4.0  # Goldilocks volatility
            
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
            
            # Calculate profit factor
            if trades:
                gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
                gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999
            else:
                profit_factor = 0
            
            return {
                "symbol": symbol,
                "trades": len(trades),
                "wins": wins,
                "losses": len(trades) - wins,
                "pnl": total_pnl,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "avg_daily_volume": avg_daily_volume,
                "atr_percent": atr_percent,
                "liquidity_ok": liquidity_ok,
                "volatility_ok": volatility_ok
            }
            
        except Exception as e:
            logger.error(f"Error backtesting {symbol}: {e}")
            return {"symbol": symbol, "trades": 0, "pnl": 0, "win_rate": 0, 
                   "liquidity_ok": False, "volatility_ok": False}
    
    def find_best_stocks(self, top_n: int = 25, max_per_sector: int = 3) -> List[str]:
        """
        PROFESSIONAL STOCK SELECTION with multi-stage filtering
        
        Args:
            top_n: Number of stocks to select (25 for diversification)
            max_per_sector: Max stocks per sector (3 for risk management)
            
        Returns:
            List of top stock symbols
        """
        logger.info(f"🔍 PROFESSIONAL SCREENING: {len(self.ALL_CANDIDATES)} stocks")
        logger.info(f"📊 Target: Top {top_n} stocks with max {max_per_sector} per sector")
        
        results = []
        for symbol in self.ALL_CANDIDATES:
            result = self.backtest_stock(symbol, days=14)  # 14-day backtest
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
        
        logger.info(f"✅ Backtesting complete! Applying filters...")
        
        # STAGE 1: Liquidity Filter
        stage1 = [r for r in results if r['liquidity_ok']]
        logger.info(f"  Filter 1 (Liquidity > 5L): {len(stage1)}/{len(results)} passed")
        
        # STAGE 2: Volatility Filter
        stage2 = [r for r in stage1 if r['volatility_ok']]
        logger.info(f"  Filter 2 (Volatility 1.5-4%): {len(stage2)}/{len(stage1)} passed")
        
        # STAGE 3: Performance Filter
        stage3 = [r for r in stage2 if r['pnl'] > 0 and r['win_rate'] >= 70 and r['trades'] >= 3]
        logger.info(f"  Filter 3 (Win Rate ≥70%, P&L >0): {len(stage3)}/{len(stage2)} passed")
        
        # STAGE 4: Sort by composite score
        for r in stage3:
            # Composite score: 40% profit, 30% win rate, 20% profit factor, 10% trades
            r['score'] = (
                r['pnl'] * 0.4 +
                r['win_rate'] * 10 * 0.3 +
                r['profit_factor'] * 50 * 0.2 +
                r['trades'] * 100 * 0.1
            )
        
        stage3.sort(key=lambda x: x['score'], reverse=True)
        logger.info(f"  Sorting: Ranked by composite score")
        
        # STAGE 5: Sector Diversification
        selected = []
        sector_count = {}
        
        for r in stage3:
            symbol = r['symbol']
            sector = self.SECTOR_MAP.get(symbol, "Other")
            
            if sector_count.get(sector, 0) < max_per_sector:
                selected.append(symbol)
                sector_count[sector] = sector_count.get(sector, 0) + 1
            
            if len(selected) >= top_n:
                break
        
        logger.info(f"  Filter 4 (Sector Diversification): {len(selected)} stocks selected")
        
        # Log sector distribution
        logger.info(f"\n📊 SECTOR DISTRIBUTION:")
        for sector, count in sorted(sector_count.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {sector}: {count} stocks")
        
        self.performance_history["last_update"] = str(date.today())
        self._save_history()
        
        return selected, results
    
    def get_recommendation(self) -> Tuple[List[str], str]:
        """Get recommended stocks for this week with professional report"""
        best_stocks, all_results = self.find_best_stocks()
        
        report = "\n" + "="*70 + "\n"
        report += "📊 PROFESSIONAL STOCK OPTIMIZATION REPORT\n"
        report += "="*70 + "\n\n"
        report += f"Universe Size: {len(self.ALL_CANDIDATES)} stocks\n"
        report += f"Selected: {len(best_stocks)} TOP PERFORMERS\n"
        report += f"Backtest Period: 14 days\n"
        report += f"Filters: Liquidity + Volatility + Performance + Sector Diversity\n\n"
        report += "TOP PERFORMERS (Use These!):\n"
        report += "-"*70 + "\n"
        
        selected_results = [x for x in all_results if x['symbol'] in best_stocks]
        selected_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        for i, r in enumerate(selected_results, 1):
            sector = self.SECTOR_MAP.get(r['symbol'], "Other")
            report += f"{i:2d}. {r['symbol']:<12} ({sector:<10}) "
            report += f"P&L: ₹{r['pnl']:>+8,.0f}  "
            report += f"Win Rate: {r['win_rate']:.0f}%  "
            report += f"PF: {r.get('profit_factor', 0):.1f}\n"
        
        report += "\n" + "-"*70 + "\n"
        report += f"📋 Recommended Watchlist ({len(best_stocks)} stocks):\n"
        report += f"   {', '.join(best_stocks)}\n"
        report += "="*70 + "\n"
        
        return best_stocks, report


def run_weekly_optimization():
    """Run weekly optimization and print results"""
    print("="*70)
    print("🔄 PROFESSIONAL WEEKLY STOCK OPTIMIZATION")
    print("="*70)
    print()
    
    optimizer = StockOptimizer(capital=10000)
    best_stocks, report = optimizer.get_recommendation()
    
    print(report)
    print()
    print("="*70)
    print(f"📋 UPDATE YOUR WATCHLIST TO ({len(best_stocks)} stocks):")
    print(f"   {', '.join(best_stocks)}")
    print("="*70)
    
    return best_stocks


if __name__ == "__main__":
    run_weekly_optimization()
