"""
Parallel Stock Tracker - Trade main watchlist while paper testing others

This system:
1. Tracks performance of MAIN watchlist (real trades)
2. Paper trades ALL other candidates in parallel
3. Compares performance after 2 weeks
4. Recommends swaps only when backup outperforms main
"""

import os
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple
from loguru import logger


class ParallelStockTracker:
    """Track main and backup stocks simultaneously"""
    
    # Main watchlist (currently trading)
    MAIN_WATCHLIST = ["PNB", "SAIL", "IDEA", "IRFC", "PFC", "BPCL", "BHEL"]
    
    # All backup candidates to paper trade
    BACKUP_CANDIDATES = [
        "TATAMOTORS", "SBIN", "TATASTEEL", "ITC", "COALINDIA",
        "ONGC", "NHPC", "IOC", "GAIL", "BANKBARODA", "CANBK",
        "IDFCFIRSTB", "YESBANK", "FEDERALBNK", "HINDALCO",
        "VEDL", "NATIONALUM", "SUZLON", "POWERGRID", "NTPC",
        "ADANIPORTS", "RECLTD", "INDUSTOWER"
    ]
    
    def __init__(self, data_file: str = "stock_tracker.json"):
        self.data_file = data_file
        self.data = self._load_data()
    
    def _load_data(self) -> Dict:
        """Load tracking data from file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            "main_stocks": {s: {"trades": 0, "wins": 0, "pnl": 0, "history": []} for s in self.MAIN_WATCHLIST},
            "backup_stocks": {s: {"trades": 0, "wins": 0, "pnl": 0, "history": []} for s in self.BACKUP_CANDIDATES},
            "last_swap_date": None,
            "swap_history": []
        }
    
    def _save_data(self):
        """Save tracking data to file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2, default=str)
    
    def record_trade(self, symbol: str, pnl: float, is_win: bool, is_paper: bool = False):
        """Record a trade result"""
        today = str(date.today())
        
        # Determine which list this stock belongs to
        if symbol in self.MAIN_WATCHLIST:
            stock_data = self.data["main_stocks"].get(symbol)
        elif symbol in self.BACKUP_CANDIDATES:
            stock_data = self.data["backup_stocks"].get(symbol)
        else:
            logger.warning(f"Unknown stock: {symbol}")
            return
        
        if stock_data:
            stock_data["trades"] += 1
            stock_data["pnl"] += pnl
            if is_win:
                stock_data["wins"] += 1
            
            stock_data["history"].append({
                "date": today,
                "pnl": pnl,
                "result": "WIN" if is_win else "LOSS",
                "is_paper": is_paper
            })
        
        self._save_data()
        logger.info(f"Recorded: {symbol} {'PAPER' if is_paper else 'REAL'} - {'WIN' if is_win else 'LOSS'} Rs{pnl:+,.0f}")
    
    def get_stock_performance(self, symbol: str) -> Dict:
        """Get performance stats for a stock"""
        if symbol in self.MAIN_WATCHLIST:
            stock_data = self.data["main_stocks"].get(symbol, {})
        else:
            stock_data = self.data["backup_stocks"].get(symbol, {})
        
        if not stock_data or stock_data.get("trades", 0) == 0:
            return {"win_rate": 0, "avg_pnl": 0, "total_pnl": 0}
        
        win_rate = (stock_data["wins"] / stock_data["trades"]) * 100
        avg_pnl = stock_data["pnl"] / stock_data["trades"]
        
        return {
            "trades": stock_data["trades"],
            "wins": stock_data["wins"],
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "total_pnl": stock_data["pnl"]
        }
    
    def get_swap_recommendations(self, min_trades: int = 10) -> List[Tuple[str, str, float]]:
        """
        Get recommendations for stock swaps.
        Returns list of (main_stock_to_remove, backup_stock_to_add, improvement)
        Only recommends if backup has enough trades AND outperforms
        """
        recommendations = []
        
        # Get main stock performances
        main_perfs = []
        for symbol in self.MAIN_WATCHLIST:
            perf = self.get_stock_performance(symbol)
            if perf.get("trades", 0) >= min_trades:
                main_perfs.append((symbol, perf["avg_pnl"], perf["win_rate"]))
        
        if not main_perfs:
            return []  # Not enough data yet
        
        # Sort main by performance (worst first)
        main_perfs.sort(key=lambda x: x[1])
        
        # Get backup stock performances
        backup_perfs = []
        for symbol in self.BACKUP_CANDIDATES:
            perf = self.get_stock_performance(symbol)
            if perf.get("trades", 0) >= min_trades and perf["avg_pnl"] > 0:
                backup_perfs.append((symbol, perf["avg_pnl"], perf["win_rate"]))
        
        # Sort backup by performance (best first)
        backup_perfs.sort(key=lambda x: x[1], reverse=True)
        
        # Find swaps where backup is significantly better
        for main_sym, main_pnl, main_wr in main_perfs:
            if main_pnl < 0:  # Main stock is losing
                for backup_sym, backup_pnl, backup_wr in backup_perfs:
                    improvement = backup_pnl - main_pnl
                    if improvement > 50:  # At least Rs50 better per trade
                        recommendations.append((main_sym, backup_sym, improvement))
                        break  # Only one swap per main stock
        
        return recommendations
    
    def generate_report(self) -> str:
        """Generate performance comparison report"""
        report = "\n" + "="*70 + "\n"
        report += "📊 STOCK PERFORMANCE TRACKER - REPORT\n"
        report += "="*70 + "\n\n"
        
        # Main watchlist performance
        report += "🎯 MAIN WATCHLIST (Real Trading):\n"
        report += "-"*50 + "\n"
        
        main_total_pnl = 0
        for symbol in self.MAIN_WATCHLIST:
            perf = self.get_stock_performance(symbol)
            trades = perf.get("trades", 0)
            if trades > 0:
                report += f"  {symbol:<12} Trades: {trades:>3} | "
                report += f"Win Rate: {perf['win_rate']:>5.1f}% | "
                report += f"P&L: Rs{perf['total_pnl']:>+8,.0f}\n"
                main_total_pnl += perf['total_pnl']
        
        report += f"\n  TOTAL MAIN P&L: Rs{main_total_pnl:+,.0f}\n"
        
        # Backup watchlist performance (paper)
        report += "\n📝 BACKUP STOCKS (Paper Trading):\n"
        report += "-"*50 + "\n"
        
        backup_results = []
        for symbol in self.BACKUP_CANDIDATES:
            perf = self.get_stock_performance(symbol)
            if perf.get("trades", 0) > 0:
                backup_results.append((symbol, perf))
        
        # Sort by P&L
        backup_results.sort(key=lambda x: x[1]['total_pnl'], reverse=True)
        
        for symbol, perf in backup_results[:10]:  # Top 10
            report += f"  {symbol:<12} Trades: {perf['trades']:>3} | "
            report += f"Win Rate: {perf['win_rate']:>5.1f}% | "
            report += f"P&L: Rs{perf['total_pnl']:>+8,.0f}\n"
        
        # Swap recommendations
        recommendations = self.get_swap_recommendations()
        if recommendations:
            report += "\n💡 SWAP RECOMMENDATIONS:\n"
            report += "-"*50 + "\n"
            for main_sym, backup_sym, improvement in recommendations:
                report += f"  REMOVE: {main_sym:<10} → ADD: {backup_sym:<10} "
                report += f"(+Rs{improvement:,.0f}/trade better)\n"
        else:
            report += "\n✅ No swaps recommended yet. Need more data.\n"
        
        report += "\n" + "="*70 + "\n"
        
        return report
    
    def execute_swap(self, remove_stock: str, add_stock: str):
        """Execute a stock swap"""
        if remove_stock in self.MAIN_WATCHLIST and add_stock in self.BACKUP_CANDIDATES:
            # Record swap
            self.data["swap_history"].append({
                "date": str(date.today()),
                "removed": remove_stock,
                "added": add_stock
            })
            
            # Move stocks
            self.MAIN_WATCHLIST.remove(remove_stock)
            self.MAIN_WATCHLIST.append(add_stock)
            self.BACKUP_CANDIDATES.remove(add_stock)
            self.BACKUP_CANDIDATES.append(remove_stock)
            
            # Update data structure
            self.data["main_stocks"][add_stock] = self.data["backup_stocks"].pop(add_stock)
            self.data["backup_stocks"][remove_stock] = self.data["main_stocks"].pop(remove_stock)
            
            self.data["last_swap_date"] = str(date.today())
            self._save_data()
            
            logger.info(f"✅ Swapped: Removed {remove_stock}, Added {add_stock}")
            return True
        
        return False


def demo():
    """Demo the parallel tracker"""
    tracker = ParallelStockTracker()
    
    # Simulate some trades
    print("Simulating trades...")
    
    # Main stocks (real)
    tracker.record_trade("PNB", 50, True, is_paper=False)
    tracker.record_trade("PNB", 50, True, is_paper=False)
    tracker.record_trade("SAIL", -30, False, is_paper=False)
    tracker.record_trade("IDEA", 50, True, is_paper=False)
    
    # Backup stocks (paper)
    tracker.record_trade("IDFCFIRSTB", 60, True, is_paper=True)
    tracker.record_trade("IDFCFIRSTB", 55, True, is_paper=True)
    tracker.record_trade("YESBANK", 45, True, is_paper=True)
    
    # Generate report
    print(tracker.generate_report())


if __name__ == "__main__":
    demo()
