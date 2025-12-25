"""
Signal Aggregator - Central hub for collecting signals from multiple strategies

This module:
1. Collects signals from all running strategies
2. Deduplicates signals (same stock, same direction)
3. Prioritizes signals by confidence and strategy rank
4. Passes validated signals to the Risk Engine
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List, Dict, Optional, Set
import threading
import logging

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    
    
class SignalStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"


@dataclass
class TradingSignal:
    """Standardized trading signal from any strategy"""
    strategy_name: str
    symbol: str
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    target: float
    quantity: int
    confidence: float  # 0-100 score
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(IST))
    status: SignalStatus = SignalStatus.PENDING
    signal_id: str = ""
    
    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = f"{self.strategy_name}_{self.symbol}_{self.timestamp.strftime('%H%M%S')}"
    
    @property
    def risk_reward_ratio(self) -> float:
        """Calculate R:R ratio"""
        if self.signal_type == SignalType.BUY:
            risk = self.entry_price - self.stop_loss
            reward = self.target - self.entry_price
        else:
            risk = self.stop_loss - self.entry_price
            reward = self.entry_price - self.target
        
        return reward / risk if risk > 0 else 0
    
    @property
    def risk_amount(self) -> float:
        """Calculate total risk in rupees"""
        if self.signal_type == SignalType.BUY:
            return (self.entry_price - self.stop_loss) * self.quantity
        else:
            return (self.stop_loss - self.entry_price) * self.quantity
    
    @property
    def potential_profit(self) -> float:
        """Calculate potential profit in rupees"""
        if self.signal_type == SignalType.BUY:
            return (self.target - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.target) * self.quantity
    
    def to_dict(self) -> dict:
        return {
            'signal_id': self.signal_id,
            'strategy': self.strategy_name,
            'symbol': self.symbol,
            'type': self.signal_type.value,
            'entry': self.entry_price,
            'stop_loss': self.stop_loss,
            'target': self.target,
            'quantity': self.quantity,
            'confidence': self.confidence,
            'risk_reward': round(self.risk_reward_ratio, 2),
            'risk_amount': round(self.risk_amount, 2),
            'potential_profit': round(self.potential_profit, 2),
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value
        }


class SignalAggregator:
    """
    Central hub that collects signals from multiple strategies
    and manages the signal queue for the execution engine
    """
    
    # Strategy priority rankings (higher = more trusted)
    STRATEGY_PRIORITY = {
        'ORB': 90,           # Opening Range Breakout - high conviction
        'EMA_Crossover': 80,  # Trend following
        'RSI_MACD': 75,       # Momentum
        'VWAP_Bounce': 70,    # Mean reversion
        'Volume_Spike': 65,   # Breakout
        'Multi_Confirmation': 85,  # Multiple indicator confirmation
        'Gold_Strategy': 80,  # Commodity strategy
        'default': 50
    }
    
    def __init__(self, max_signals_per_stock: int = 1, signal_expiry_minutes: int = 5):
        self.pending_signals: List[TradingSignal] = []
        self.processed_signals: List[TradingSignal] = []
        self.active_stocks: Set[str] = set()  # Stocks with pending/active signals
        self.max_signals_per_stock = max_signals_per_stock
        self.signal_expiry_minutes = signal_expiry_minutes
        self._lock = threading.Lock()
        
        logger.info("📡 Signal Aggregator initialized")
    
    def add_signal(self, signal: TradingSignal) -> bool:
        """
        Add a new signal to the queue
        Returns True if signal was accepted, False if rejected
        """
        with self._lock:
            # Check if signal is duplicate (same stock, same direction within last 5 min)
            if self._is_duplicate(signal):
                logger.debug(f"⚠️ Duplicate signal rejected: {signal.symbol} {signal.signal_type.value}")
                return False
            
            # Check if too many signals for this stock
            stock_signals = [s for s in self.pending_signals if s.symbol == signal.symbol]
            if len(stock_signals) >= self.max_signals_per_stock:
                logger.debug(f"⚠️ Max signals reached for {signal.symbol}")
                return False
            
            # Calculate priority score
            signal.confidence = self._calculate_priority_score(signal)
            
            # Add to queue
            self.pending_signals.append(signal)
            self.active_stocks.add(signal.symbol)
            
            logger.info(f"📡 Signal added: {signal.strategy_name} → {signal.symbol} {signal.signal_type.value} @ ₹{signal.entry_price:.2f} (Confidence: {signal.confidence:.1f})")
            
            return True
    
    def _is_duplicate(self, new_signal: TradingSignal) -> bool:
        """Check if a similar signal already exists"""
        cutoff_time = datetime.now(IST) - timedelta(minutes=self.signal_expiry_minutes)
        
        for signal in self.pending_signals:
            if (signal.symbol == new_signal.symbol and 
                signal.signal_type == new_signal.signal_type and
                signal.timestamp > cutoff_time):
                return True
        
        return False
    
    def _calculate_priority_score(self, signal: TradingSignal) -> float:
        """
        Calculate overall priority score for a signal
        Combines: strategy priority + confidence + R:R ratio
        """
        # Base score from strategy priority
        strategy_priority = self.STRATEGY_PRIORITY.get(
            signal.strategy_name, 
            self.STRATEGY_PRIORITY['default']
        )
        
        # Original confidence (0-100)
        confidence = signal.confidence
        
        # R:R bonus (max 10 points for R:R >= 2)
        rr_bonus = min(signal.risk_reward_ratio * 5, 10)
        
        # Weighted final score
        final_score = (strategy_priority * 0.3) + (confidence * 0.5) + (rr_bonus * 0.2) * 10
        
        return min(100, final_score)
    
    def get_next_signal(self) -> Optional[TradingSignal]:
        """
        Get the highest priority signal from the queue
        Removes expired signals automatically
        """
        with self._lock:
            self._cleanup_expired()
            
            if not self.pending_signals:
                return None
            
            # Sort by confidence (priority score) descending
            self.pending_signals.sort(key=lambda s: s.confidence, reverse=True)
            
            return self.pending_signals[0]
    
    def get_all_pending(self) -> List[TradingSignal]:
        """Get all pending signals sorted by priority"""
        with self._lock:
            self._cleanup_expired()
            return sorted(self.pending_signals, key=lambda s: s.confidence, reverse=True)
    
    def mark_signal_status(self, signal_id: str, status: SignalStatus):
        """Update the status of a signal"""
        with self._lock:
            for signal in self.pending_signals:
                if signal.signal_id == signal_id:
                    signal.status = status
                    
                    if status in [SignalStatus.EXECUTED, SignalStatus.REJECTED, SignalStatus.EXPIRED]:
                        self.pending_signals.remove(signal)
                        self.processed_signals.append(signal)
                        
                        if signal.symbol in self.active_stocks:
                            # Check if any other pending signals for this stock
                            if not any(s.symbol == signal.symbol for s in self.pending_signals):
                                self.active_stocks.discard(signal.symbol)
                    
                    logger.info(f"📡 Signal {signal_id} status: {status.value}")
                    return
    
    def _cleanup_expired(self):
        """Remove expired signals"""
        cutoff_time = datetime.now(IST) - timedelta(minutes=self.signal_expiry_minutes)
        
        expired = [s for s in self.pending_signals if s.timestamp < cutoff_time]
        for signal in expired:
            signal.status = SignalStatus.EXPIRED
            self.pending_signals.remove(signal)
            self.processed_signals.append(signal)
            
            if not any(s.symbol == signal.symbol for s in self.pending_signals):
                self.active_stocks.discard(signal.symbol)
            
            logger.debug(f"⏰ Signal expired: {signal.signal_id}")
    
    def has_active_signal(self, symbol: str) -> bool:
        """Check if there's an active signal for a stock"""
        return symbol in self.active_stocks
    
    def get_stats(self) -> dict:
        """Get aggregator statistics"""
        with self._lock:
            return {
                'pending_count': len(self.pending_signals),
                'processed_count': len(self.processed_signals),
                'active_stocks': list(self.active_stocks),
                'pending_signals': [s.to_dict() for s in self.pending_signals]
            }
    
    def clear_all(self):
        """Clear all signals (for testing/reset)"""
        with self._lock:
            self.pending_signals.clear()
            self.processed_signals.clear()
            self.active_stocks.clear()
            logger.info("📡 Signal Aggregator cleared")


# Global signal aggregator instance
signal_aggregator = SignalAggregator()
