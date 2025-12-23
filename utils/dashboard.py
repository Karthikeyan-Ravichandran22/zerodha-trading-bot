"""
Performance Dashboard - Display trading performance statistics
"""

from datetime import datetime, date
from typing import Dict
from loguru import logger


class PerformanceDashboard:
    """Display live performance metrics"""
    
    def __init__(self):
        self.trades = []
        self.start_capital = 10000
        self.current_capital = 10000
    
    def display_daily(self, stats: Dict):
        """Display daily performance dashboard"""
        logger.info("")
        logger.info("╔" + "═"*48 + "╗")
        logger.info("║" + " 📊 DAILY PERFORMANCE DASHBOARD ".center(48) + "║")
        logger.info("╠" + "═"*48 + "╣")
        logger.info(f"║  Date: {date.today().isoformat()}".ljust(49) + "║")
        logger.info("╠" + "═"*48 + "╣")
        logger.info(f"║  Total Trades: {stats.get('total_trades', 0)}".ljust(49) + "║")
        logger.info(f"║  Open Trades: {stats.get('open_trades', 0)}".ljust(49) + "║")
        logger.info(f"║  Closed Trades: {stats.get('closed_trades', 0)}".ljust(49) + "║")
        logger.info("╠" + "═"*48 + "╣")
        logger.info(f"║  Wins: {stats.get('wins', 0)} | Losses: {stats.get('losses', 0)}".ljust(49) + "║")
        logger.info(f"║  Win Rate: {stats.get('win_rate', 0):.1f}%".ljust(49) + "║")
        logger.info("╠" + "═"*48 + "╣")
        
        gross = stats.get('gross_pnl', 0)
        charges = stats.get('total_charges', 0)
        net = stats.get('net_pnl', 0)
        
        logger.info(f"║  Gross P&L: ₹{gross:+,.2f}".ljust(49) + "║")
        logger.info(f"║  Charges: ₹{charges:,.2f}".ljust(49) + "║")
        
        net_emoji = "💚" if net >= 0 else "💔"
        logger.info(f"║  {net_emoji} NET P&L: ₹{net:+,.2f}".ljust(49) + "║")
        logger.info("╠" + "═"*48 + "╣")
        logger.info(f"║  Best Trade: ₹{stats.get('best_trade', 0):+,.2f}".ljust(49) + "║")
        logger.info(f"║  Worst Trade: ₹{stats.get('worst_trade', 0):+,.2f}".ljust(49) + "║")
        logger.info("╚" + "═"*48 + "╝")
        logger.info("")
    
    def display_weekly(self, stats: Dict):
        """Display weekly performance summary"""
        logger.info("")
        logger.info("╔" + "═"*48 + "╗")
        logger.info("║" + " 📈 WEEKLY PERFORMANCE REPORT ".center(48) + "║")
        logger.info("╠" + "═"*48 + "╣")
        logger.info(f"║  Days Traded: {stats.get('days', 0)}".ljust(49) + "║")
        logger.info(f"║  Total Trades: {stats.get('total_trades', 0)}".ljust(49) + "║")
        logger.info(f"║  Total Wins: {stats.get('total_wins', 0)}".ljust(49) + "║")
        logger.info(f"║  Win Rate: {stats.get('win_rate', 0):.1f}%".ljust(49) + "║")
        logger.info("╠" + "═"*48 + "╣")
        
        total = stats.get('total_pnl', 0)
        avg = stats.get('avg_daily_pnl', 0)
        
        total_emoji = "💚" if total >= 0 else "💔"
        logger.info(f"║  {total_emoji} TOTAL P&L: ₹{total:+,.2f}".ljust(49) + "║")
        logger.info(f"║  Avg Daily P&L: ₹{avg:+,.2f}".ljust(49) + "║")
        logger.info("╠" + "═"*48 + "╣")
        logger.info(f"║  Best Day: ₹{stats.get('best_day', 0):+,.2f}".ljust(49) + "║")
        logger.info(f"║  Worst Day: ₹{stats.get('worst_day', 0):+,.2f}".ljust(49) + "║")
        logger.info("╚" + "═"*48 + "╝")
        logger.info("")
    
    def get_telegram_summary(self, stats: Dict) -> str:
        """Get summary formatted for Telegram"""
        net = stats.get('net_pnl', 0)
        emoji = "💚" if net >= 0 else "💔"
        
        msg = f"📊 <b>DAILY PERFORMANCE</b>\n\n"
        msg += f"📅 Date: {date.today().isoformat()}\n\n"
        msg += f"📈 Trades: {stats.get('total_trades', 0)}\n"
        msg += f"✅ Wins: {stats.get('wins', 0)} | ❌ Losses: {stats.get('losses', 0)}\n"
        msg += f"🎯 Win Rate: {stats.get('win_rate', 0):.1f}%\n\n"
        msg += f"💰 Gross P&L: ₹{stats.get('gross_pnl', 0):+,.2f}\n"
        msg += f"📋 Charges: ₹{stats.get('total_charges', 0):,.2f}\n"
        msg += f"{emoji} <b>NET P&L: ₹{net:+,.2f}</b>\n\n"
        msg += f"🏆 Best: ₹{stats.get('best_trade', 0):+,.2f}\n"
        msg += f"📉 Worst: ₹{stats.get('worst_trade', 0):+,.2f}"
        
        return msg


# Global instance
dashboard = PerformanceDashboard()
