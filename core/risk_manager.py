"""
Risk Manager - Position sizing, daily limits, and risk calculations
"""

from datetime import datetime, date
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field
from loguru import logger

from config.settings import (
    TRADING_CAPITAL, MAX_RISK_PER_TRADE, MAX_RISK_PER_TRADE_PERCENT,
    MAX_DAILY_LOSS, MAX_DAILY_LOSS_PERCENT, MAX_TRADES_PER_DAY,
    MAX_OPEN_POSITIONS, MAX_POSITION_SIZE
)


@dataclass
class DailyStats:
    """Track daily trading statistics"""
    date: date = field(default_factory=date.today)
    trades_taken: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    open_positions: int = 0
    
    @property
    def win_rate(self) -> float:
        return (self.winning_trades / self.trades_taken * 100) if self.trades_taken else 0.0
    
    @property
    def is_loss_limit_hit(self) -> bool:
        return self.total_pnl <= -MAX_DAILY_LOSS


class RiskManager:
    """Handles all risk-related calculations and limits"""
    
    def __init__(self, capital: float = None):
        self.capital = capital or TRADING_CAPITAL
        self.daily_stats = DailyStats()
        self._last_reset_date = date.today()
        logger.info(f"💰 Risk Manager: ₹{self.capital:,.0f} capital")
    
    def _check_day_reset(self):
        if self._last_reset_date != date.today():
            self.daily_stats = DailyStats()
            self._last_reset_date = date.today()
    
    def calculate_position_size(self, entry: float, stop_loss: float, risk_amt: float = None) -> int:
        """Calculate quantity based on risk per trade"""
        risk_amt = risk_amt or MAX_RISK_PER_TRADE
        risk_per_share = abs(entry - stop_loss)
        if risk_per_share <= 0:
            return 0
        qty = int(risk_amt / risk_per_share)
        if qty * entry > MAX_POSITION_SIZE:
            qty = int(MAX_POSITION_SIZE / entry)
        return max(1, qty) if entry <= MAX_POSITION_SIZE else 0
    
    def can_take_trade(self) -> Tuple[bool, str]:
        """Check if trading is allowed"""
        self._check_day_reset()
        if self.daily_stats.is_loss_limit_hit:
            return False, "❌ Daily loss limit hit"
        if self.daily_stats.trades_taken >= MAX_TRADES_PER_DAY:
            return False, "❌ Max trades reached"
        if self.daily_stats.open_positions >= MAX_OPEN_POSITIONS:
            return False, "❌ Max positions open"
        return True, "✅ Trade allowed"
    
    def record_trade_entry(self):
        self._check_day_reset()
        self.daily_stats.trades_taken += 1
        self.daily_stats.open_positions += 1
    
    def record_trade_exit(self, pnl: float):
        self._check_day_reset()
        self.daily_stats.open_positions = max(0, self.daily_stats.open_positions - 1)
        self.daily_stats.total_pnl += pnl
        if pnl >= 0:
            self.daily_stats.winning_trades += 1
            self.daily_stats.gross_profit += pnl
        else:
            self.daily_stats.losing_trades += 1
            self.daily_stats.gross_loss += abs(pnl)
        if self.daily_stats.is_loss_limit_hit:
            logger.warning("🛑 DAILY LOSS LIMIT HIT!")


_risk_manager: Optional[RiskManager] = None

def get_risk_manager() -> RiskManager:
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager
