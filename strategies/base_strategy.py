"""
Base Strategy Class - All strategies inherit from this
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum
import pandas as pd


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradeSignal:
    signal: Signal
    symbol: str
    entry_price: float
    stop_loss: float
    target: float
    quantity: int
    reason: str
    confidence: float = 0.0  # 0-100


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""
    
    name: str = "BaseStrategy"
    description: str = ""
    timeframe: str = "15minute"
    min_capital: float = 5000
    
    def __init__(self, data_fetcher=None, risk_manager=None):
        self.data_fetcher = data_fetcher
        self.risk_manager = risk_manager
        self.active_signals: List[TradeSignal] = []
    
    @abstractmethod
    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """
        Analyze market data and generate trade signal
        
        Args:
            symbol: Stock symbol
            data: OHLCV DataFrame with indicators
            
        Returns:
            TradeSignal if conditions met, None otherwise
        """
        pass
    
    @abstractmethod
    def get_entry_conditions(self) -> List[str]:
        """Return list of entry conditions for documentation"""
        pass
    
    @abstractmethod
    def get_exit_conditions(self) -> List[str]:
        """Return list of exit conditions"""
        pass
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate required indicators - override in subclass"""
        return data
    
    def validate_signal(self, signal: TradeSignal) -> bool:
        """Validate signal against risk rules"""
        if self.risk_manager:
            can_trade, _ = self.risk_manager.can_take_trade()
            return can_trade
        return True
    
    def scan_symbols(self, symbols: List[str]) -> List[TradeSignal]:
        """Scan multiple symbols for signals"""
        signals = []
        for symbol in symbols:
            if self.data_fetcher:
                data = self.data_fetcher.get_ohlc_data(symbol, self.timeframe)
                if data is not None and not data.empty:
                    data = self.calculate_indicators(data)
                    signal = self.analyze(symbol, data)
                    if signal and self.validate_signal(signal):
                        signals.append(signal)
        return signals
