"""
Risk Engine - Central risk management before order execution

This module:
1. Validates signals against risk parameters
2. Checks available funds
3. Checks open positions limit
4. Checks daily loss limit
5. Ensures no duplicate trades
6. Calculates proper position sizing
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date
from typing import Tuple, Optional, List, Dict
import os
import logging

from core.signal_aggregator import TradingSignal, SignalType, SignalStatus

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class RiskCheck:
    """Result of a risk check"""
    passed: bool
    reason: str
    adjusted_quantity: int = 0
    

@dataclass
class DailyStats:
    """Daily trading statistics for risk tracking"""
    date: date
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    gross_pnl: float = 0.0
    realized_pnl: float = 0.0
    open_positions: int = 0
    max_drawdown: float = 0.0
    

class RiskEngine:
    """
    Central risk management engine that validates all trades
    before execution
    """
    
    def __init__(
        self,
        capital: float = 10000.0,
        max_risk_per_trade_percent: float = 2.0,  # Max 2% risk per trade
        max_daily_loss_percent: float = 3.0,       # Max 3% daily loss
        max_open_positions: int = 3,               # Max simultaneous positions
        max_trades_per_day: int = 10,              # Max trades per day
        min_rr_ratio: float = 1.5,                 # Minimum risk-reward ratio
        min_profit_after_charges: float = 20.0     # Min profit after brokerage
    ):
        self.capital = capital
        self.max_risk_per_trade = capital * (max_risk_per_trade_percent / 100)
        self.max_daily_loss = capital * (max_daily_loss_percent / 100)
        self.max_open_positions = max_open_positions
        self.max_trades_per_day = max_trades_per_day
        self.min_rr_ratio = min_rr_ratio
        self.min_profit_after_charges = min_profit_after_charges
        
        # Load from environment if available
        self.capital = float(os.getenv('TRADING_CAPITAL', capital))
        self.max_risk_per_trade = self.capital * (
            float(os.getenv('MAX_RISK_PER_TRADE_PERCENT', max_risk_per_trade_percent)) / 100
        )
        self.max_daily_loss = self.capital * (
            float(os.getenv('MAX_DAILY_LOSS_PERCENT', max_daily_loss_percent)) / 100
        )
        self.max_trades_per_day = int(os.getenv('MAX_TRADES_PER_DAY', max_trades_per_day))
        
        # Daily tracking
        self.daily_stats = DailyStats(date=date.today())
        self.open_positions: Dict[str, dict] = {}  # symbol -> position info
        self.available_funds: float = capital
        
        logger.info(f"🛡️ Risk Engine initialized")
        logger.info(f"   Capital: ₹{self.capital:,.2f}")
        logger.info(f"   Max risk/trade: ₹{self.max_risk_per_trade:.2f}")
        logger.info(f"   Max daily loss: ₹{self.max_daily_loss:.2f}")
        logger.info(f"   Max positions: {self.max_open_positions}")
    
    def validate_signal(self, signal: TradingSignal) -> RiskCheck:
        """
        Run all risk checks on a signal
        Returns RiskCheck with pass/fail and reason
        """
        # Reset daily stats if new day
        self._check_new_day()
        
        checks = [
            self._check_daily_loss_limit(signal),
            self._check_trades_per_day(signal),
            self._check_open_positions(signal),
            self._check_duplicate_position(signal),
            self._check_available_funds(signal),
            self._check_risk_reward_ratio(signal),
            self._check_position_size(signal),
            self._check_profitability(signal)
        ]
        
        for check in checks:
            if not check.passed:
                logger.warning(f"🛡️ Risk check failed for {signal.symbol}: {check.reason}")
                return check
        
        # All checks passed - calculate optimal quantity
        optimal_qty = self._calculate_position_size(signal)
        
        logger.info(f"✅ Risk checks passed: {signal.symbol} {signal.signal_type.value} x{optimal_qty}")
        return RiskCheck(passed=True, reason="All checks passed", adjusted_quantity=optimal_qty)
    
    def _check_new_day(self):
        """Reset daily stats if it's a new trading day"""
        today = date.today()
        if self.daily_stats.date != today:
            logger.info(f"📅 New trading day: {today}")
            self.daily_stats = DailyStats(date=today)
    
    def _check_daily_loss_limit(self, signal: TradingSignal) -> RiskCheck:
        """Check if daily loss limit is breached"""
        if self.daily_stats.realized_pnl < -self.max_daily_loss:
            return RiskCheck(
                passed=False,
                reason=f"Daily loss limit breached: ₹{abs(self.daily_stats.realized_pnl):.2f} > ₹{self.max_daily_loss:.2f}"
            )
        return RiskCheck(passed=True, reason="Daily loss limit OK")
    
    def _check_trades_per_day(self, signal: TradingSignal) -> RiskCheck:
        """Check if max trades per day reached"""
        if self.daily_stats.trades_count >= self.max_trades_per_day:
            return RiskCheck(
                passed=False,
                reason=f"Max trades per day reached: {self.daily_stats.trades_count}/{self.max_trades_per_day}"
            )
        return RiskCheck(passed=True, reason="Trades per day OK")
    
    def _check_open_positions(self, signal: TradingSignal) -> RiskCheck:
        """Check if max open positions reached"""
        if len(self.open_positions) >= self.max_open_positions:
            return RiskCheck(
                passed=False,
                reason=f"Max open positions reached: {len(self.open_positions)}/{self.max_open_positions}"
            )
        return RiskCheck(passed=True, reason="Open positions OK")
    
    def _check_duplicate_position(self, signal: TradingSignal) -> RiskCheck:
        """Check if already have a position in this stock"""
        if signal.symbol in self.open_positions:
            return RiskCheck(
                passed=False,
                reason=f"Already have open position in {signal.symbol}"
            )
        return RiskCheck(passed=True, reason="No duplicate position")
    
    def _check_available_funds(self, signal: TradingSignal) -> RiskCheck:
        """Check if enough funds available for the trade"""
        required_margin = signal.entry_price * signal.quantity
        
        if required_margin > self.available_funds:
            return RiskCheck(
                passed=False,
                reason=f"Insufficient funds: Need ₹{required_margin:.2f}, Available ₹{self.available_funds:.2f}"
            )
        return RiskCheck(passed=True, reason="Funds available")
    
    def _check_risk_reward_ratio(self, signal: TradingSignal) -> RiskCheck:
        """Check if R:R ratio meets minimum requirement"""
        if signal.risk_reward_ratio < self.min_rr_ratio:
            return RiskCheck(
                passed=False,
                reason=f"R:R ratio too low: {signal.risk_reward_ratio:.2f} < {self.min_rr_ratio}"
            )
        return RiskCheck(passed=True, reason="R:R ratio OK")
    
    def _check_position_size(self, signal: TradingSignal) -> RiskCheck:
        """Check if position size risk is within limits"""
        risk_amount = signal.risk_amount
        
        if risk_amount > self.max_risk_per_trade:
            # Don't fail - we'll adjust quantity
            return RiskCheck(
                passed=True, 
                reason=f"Position size will be adjusted (risk ₹{risk_amount:.2f} > max ₹{self.max_risk_per_trade:.2f})"
            )
        return RiskCheck(passed=True, reason="Position size OK")
    
    def _check_profitability(self, signal: TradingSignal) -> RiskCheck:
        """Check if trade is profitable after brokerage charges"""
        # Estimate brokerage (₹20 per order for delivery, ₹20 for intraday)
        brokerage = 40  # Entry + Exit
        
        # Other charges (STT, GST, etc.) - approximately 0.1% of turnover
        turnover = signal.entry_price * signal.quantity * 2  # Buy + Sell
        other_charges = turnover * 0.001
        
        total_charges = brokerage + other_charges
        net_profit = signal.potential_profit - total_charges
        
        if net_profit < self.min_profit_after_charges:
            return RiskCheck(
                passed=False,
                reason=f"Not profitable after charges: Net ₹{net_profit:.2f} < Min ₹{self.min_profit_after_charges:.2f}"
            )
        return RiskCheck(passed=True, reason=f"Profitable: ₹{net_profit:.2f} after charges")
    
    def _calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate optimal position size based on risk"""
        # Risk per share
        if signal.signal_type == SignalType.BUY:
            risk_per_share = signal.entry_price - signal.stop_loss
        else:
            risk_per_share = signal.stop_loss - signal.entry_price
        
        if risk_per_share <= 0:
            return 0
        
        # Calculate quantity based on max risk
        max_quantity = int(self.max_risk_per_trade / risk_per_share)
        
        # Also check against available funds
        max_by_funds = int(self.available_funds / signal.entry_price)
        
        # Take minimum
        optimal_quantity = min(max_quantity, max_by_funds, signal.quantity)
        
        return max(1, optimal_quantity)  # At least 1 share
    
    def update_funds(self, available: float):
        """Update available funds (called after broker sync)"""
        self.available_funds = available
        logger.debug(f"🛡️ Funds updated: ₹{available:,.2f}")
    
    def add_position(self, symbol: str, position_info: dict):
        """Track new open position"""
        self.open_positions[symbol] = position_info
        self.daily_stats.trades_count += 1
        self.daily_stats.open_positions = len(self.open_positions)
        logger.info(f"🛡️ Position added: {symbol} (Total: {len(self.open_positions)})")
    
    def close_position(self, symbol: str, pnl: float):
        """Track closed position"""
        if symbol in self.open_positions:
            del self.open_positions[symbol]
        
        self.daily_stats.realized_pnl += pnl
        self.daily_stats.gross_pnl += pnl
        
        if pnl > 0:
            self.daily_stats.wins += 1
        else:
            self.daily_stats.losses += 1
        
        self.daily_stats.open_positions = len(self.open_positions)
        
        # Track max drawdown
        if self.daily_stats.realized_pnl < self.daily_stats.max_drawdown:
            self.daily_stats.max_drawdown = self.daily_stats.realized_pnl
        
        logger.info(f"🛡️ Position closed: {symbol} P&L: ₹{pnl:.2f} (Daily: ₹{self.daily_stats.realized_pnl:.2f})")
    
    def get_stats(self) -> dict:
        """Get current risk engine statistics"""
        return {
            'capital': self.capital,
            'available_funds': self.available_funds,
            'max_risk_per_trade': self.max_risk_per_trade,
            'max_daily_loss': self.max_daily_loss,
            'open_positions': len(self.open_positions),
            'max_open_positions': self.max_open_positions,
            'trades_today': self.daily_stats.trades_count,
            'max_trades_per_day': self.max_trades_per_day,
            'daily_pnl': self.daily_stats.realized_pnl,
            'wins': self.daily_stats.wins,
            'losses': self.daily_stats.losses,
            'positions': list(self.open_positions.keys())
        }
    
    def get_daily_summary(self) -> str:
        """Get formatted daily summary"""
        win_rate = (self.daily_stats.wins / self.daily_stats.trades_count * 100 
                    if self.daily_stats.trades_count > 0 else 0)
        
        return f"""
═══════════════════════════════════════
🛡️ RISK ENGINE DAILY SUMMARY
═══════════════════════════════════════
Date: {self.daily_stats.date}
Trades: {self.daily_stats.trades_count}/{self.max_trades_per_day}
Wins: {self.daily_stats.wins} | Losses: {self.daily_stats.losses}
Win Rate: {win_rate:.1f}%
Daily P&L: ₹{self.daily_stats.realized_pnl:+.2f}
Max Drawdown: ₹{self.daily_stats.max_drawdown:.2f}
Open Positions: {len(self.open_positions)}/{self.max_open_positions}
═══════════════════════════════════════
"""


# Global risk engine instance
risk_engine = RiskEngine()
