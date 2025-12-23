"""
Capital Manager - Dynamic position sizing based on account growth
Implements Capital Compounding for exponential growth
"""

import os
import json
from datetime import datetime, date
from typing import Tuple
from loguru import logger


class CapitalManager:
    """
    Manages trading capital with automatic growth compounding.
    
    Features:
    - Tracks actual capital based on P&L
    - Adjusts position sizes automatically
    - Compounds profits weekly
    - Protects against drawdown
    """
    
    def __init__(self, initial_capital: float = 10000, config_path: str = "data/capital_config.json"):
        self.config_path = config_path
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.high_water_mark = initial_capital
        self.weekly_start_capital = initial_capital
        self.total_pnl = 0.0
        
        # Settings
        self.compound_rate = 1.0  # 100% of profits reinvested
        self.max_risk_per_trade = 0.02  # 2% per trade
        self.max_drawdown_percent = 0.10  # 10% max drawdown before reducing size
        self.growth_threshold = 0.05  # 5% profit before increasing size
        
        # Load saved state
        self._load_state()
    
    def _load_state(self):
        """Load capital state from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.current_capital = data.get('current_capital', self.initial_capital)
                    self.high_water_mark = data.get('high_water_mark', self.current_capital)
                    self.total_pnl = data.get('total_pnl', 0.0)
                    self.weekly_start_capital = data.get('weekly_start_capital', self.initial_capital)
                    logger.info(f"💰 Capital loaded: ₹{self.current_capital:,.2f} (Total P&L: ₹{self.total_pnl:+,.2f})")
        except Exception as e:
            logger.warning(f"Could not load capital state: {e}")
    
    def _save_state(self):
        """Save capital state to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump({
                    'current_capital': self.current_capital,
                    'high_water_mark': self.high_water_mark,
                    'total_pnl': self.total_pnl,
                    'weekly_start_capital': self.weekly_start_capital,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save capital state: {e}")
    
    def get_capital(self) -> float:
        """Get current trading capital"""
        return self.current_capital
    
    def get_position_size(self, entry_price: float, stop_loss: float) -> Tuple[int, float]:
        """
        Calculate position size based on current capital and risk.
        
        Returns:
            (quantity, risk_amount)
        """
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss)
        
        if risk_per_share <= 0:
            risk_per_share = entry_price * 0.01  # Default 1% risk
        
        # Calculate max risk amount
        risk_amount = self.current_capital * self.max_risk_per_trade
        
        # Check for drawdown - reduce size if in drawdown
        drawdown = (self.high_water_mark - self.current_capital) / self.high_water_mark
        if drawdown > 0.05:  # More than 5% drawdown
            risk_amount *= 0.75  # Reduce risk by 25%
            logger.warning(f"⚠️ In drawdown ({drawdown:.1%}), reducing position size")
        
        # Calculate quantity
        quantity = int(risk_amount / risk_per_share)
        
        # Ensure quantity is at least 1
        quantity = max(1, quantity)
        
        # Cap at max affordable quantity
        max_qty = int(self.current_capital * 0.3 / entry_price)  # Max 30% of capital per trade
        quantity = min(quantity, max_qty)
        
        return quantity, risk_amount
    
    def record_trade_pnl(self, pnl: float, charges: float = 0):
        """
        Record P&L from a trade and update capital.
        
        Args:
            pnl: Gross P&L from trade
            charges: Brokerage and other charges
        """
        net_pnl = pnl - charges
        self.current_capital += net_pnl
        self.total_pnl += net_pnl
        
        # Update high water mark
        if self.current_capital > self.high_water_mark:
            self.high_water_mark = self.current_capital
            logger.info(f"🏆 New high water mark: ₹{self.high_water_mark:,.2f}")
        
        # Log the update
        emoji = "💚" if net_pnl > 0 else "💔"
        logger.info(f"{emoji} Capital update: ₹{net_pnl:+,.2f} → New capital: ₹{self.current_capital:,.2f}")
        
        # Save state
        self._save_state()
    
    def weekly_compound(self):
        """
        Perform weekly capital compounding.
        Call this every Sunday.
        """
        week_profit = self.current_capital - self.weekly_start_capital
        
        if week_profit > 0:
            compound_amount = week_profit * self.compound_rate
            logger.info("="*50)
            logger.info("📈 WEEKLY CAPITAL COMPOUNDING")
            logger.info("="*50)
            logger.info(f"  Start of week: ₹{self.weekly_start_capital:,.2f}")
            logger.info(f"  End of week: ₹{self.current_capital:,.2f}")
            logger.info(f"  Week profit: ₹{week_profit:+,.2f}")
            logger.info(f"  Compounded: ₹{compound_amount:,.2f} added to trading capital")
            logger.info("="*50)
            
            # Notify via Telegram
            try:
                from utils.notifications import send_telegram_message
                msg = f"📈 WEEKLY COMPOUNDING\n\n"
                msg += f"Week Profit: ₹{week_profit:+,.2f}\n"
                msg += f"New Capital: ₹{self.current_capital:,.2f}\n"
                msg += f"Total P&L: ₹{self.total_pnl:+,.2f}"
                send_telegram_message(msg)
            except:
                pass
        else:
            logger.info(f"📊 Week P&L: ₹{week_profit:+,.2f} (No compounding needed)")
        
        # Reset weekly start
        self.weekly_start_capital = self.current_capital
        self._save_state()
    
    def get_stats(self) -> dict:
        """Get capital statistics"""
        drawdown = ((self.high_water_mark - self.current_capital) / self.high_water_mark) * 100
        growth = ((self.current_capital - self.initial_capital) / self.initial_capital) * 100
        
        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'high_water_mark': self.high_water_mark,
            'total_pnl': self.total_pnl,
            'growth_percent': growth,
            'current_drawdown': drawdown,
            'risk_per_trade': self.max_risk_per_trade * 100
        }
    
    def log_status(self):
        """Log current capital status"""
        stats = self.get_stats()
        logger.info(f"💰 Capital: ₹{stats['current_capital']:,.2f} | Growth: {stats['growth_percent']:+.1f}% | Drawdown: {stats['current_drawdown']:.1f}%")


# Global instance
capital_manager = CapitalManager()
