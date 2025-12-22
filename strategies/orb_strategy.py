"""
Opening Range Breakout (ORB) Strategy
Trade breakouts of first 15-minute candle range
"""

import pandas as pd
from datetime import time
from typing import Optional, List
from loguru import logger

from .base_strategy import BaseStrategy, TradeSignal, Signal
from utils.indicators import calculate_supertrend


class ORBStrategy(BaseStrategy):
    """
    Opening Range Breakout Strategy
    
    Logic:
    - Mark high/low of first 15-min candle (9:15-9:30)
    - Buy on breakout above high with volume
    - Sell on breakdown below low with volume
    - Target: 1x-1.5x the range
    """
    
    name = "Opening Range Breakout"
    description = "Trade breakouts of first 15-min range"
    timeframe = "5minute"
    min_capital = 5000
    
    # Strategy parameters
    orb_start = time(9, 15)
    orb_end = time(9, 30)
    max_range_percent = 2.5  # Skip if range > 2.5%
    min_range_percent = 0.5  # Skip if range < 0.5%
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orb_high = None
        self.orb_low = None
        self.orb_calculated = False
    
    def calculate_opening_range(self, data: pd.DataFrame) -> tuple:
        """Calculate opening range from first 15-min candle"""
        # Filter data for 9:15-9:30 timeframe
        morning_data = data.between_time('09:15', '09:30')
        if morning_data.empty:
            return None, None
        
        orb_high = morning_data['high'].max()
        orb_low = morning_data['low'].min()
        return orb_high, orb_low
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add Supertrend indicator"""
        data = data.copy()
        st_data = calculate_supertrend(data, period=10, multiplier=3)
        data['supertrend'] = st_data['supertrend']
        data['st_direction'] = st_data['direction']  # 1 = bullish, -1 = bearish
        
        # Volume analysis
        data['vol_sma'] = data['volume'].rolling(20).mean()
        data['vol_ratio'] = data['volume'] / data['vol_sma']
        
        return data
    
    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Analyze for ORB setup"""
        if len(data) < 10:
            return None
        
        # Calculate opening range
        orb_high, orb_low = self.calculate_opening_range(data)
        if orb_high is None or orb_low is None:
            return None
        
        # Calculate range percentage
        orb_range = orb_high - orb_low
        range_percent = (orb_range / orb_low) * 100
        
        # Skip if range is too wide or too narrow
        if range_percent > self.max_range_percent:
            logger.debug(f"{symbol}: ORB range too wide ({range_percent:.1f}%)")
            return None
        if range_percent < self.min_range_percent:
            logger.debug(f"{symbol}: ORB range too narrow ({range_percent:.1f}%)")
            return None
        
        current = data.iloc[-1]
        prev = data.iloc[-2]
        close = current['close']
        
        signal = None
        
        # BULLISH BREAKOUT
        if (prev['close'] <= orb_high and  # Previous candle was inside range
            close > orb_high and  # Current candle broke out
            current['st_direction'] == 1 and  # Supertrend bullish
            current['vol_ratio'] > 1.2):  # Above average volume
            
            entry = close
            stop_loss = orb_low if orb_range < entry * 0.02 else (orb_high + orb_low) / 2
            target = entry + orb_range  # 1x range target
            
            if self.risk_manager:
                qty = self.risk_manager.calculate_position_size(entry, stop_loss)
            else:
                qty = 10
            
            signal = TradeSignal(
                signal=Signal.BUY,
                symbol=symbol,
                entry_price=round(entry, 2),
                stop_loss=round(stop_loss, 2),
                target=round(target, 2),
                quantity=qty,
                reason=f"ORB Bullish Breakout, Range: {range_percent:.1f}%",
                confidence=70.0
            )
        
        # BEARISH BREAKDOWN
        elif (prev['close'] >= orb_low and
              close < orb_low and
              current['st_direction'] == -1 and
              current['vol_ratio'] > 1.2):
            
            entry = close
            stop_loss = orb_high if orb_range < entry * 0.02 else (orb_high + orb_low) / 2
            target = entry - orb_range
            
            if self.risk_manager:
                qty = self.risk_manager.calculate_position_size(entry, stop_loss)
            else:
                qty = 10
            
            signal = TradeSignal(
                signal=Signal.SELL,
                symbol=symbol,
                entry_price=round(entry, 2),
                stop_loss=round(stop_loss, 2),
                target=round(target, 2),
                quantity=qty,
                reason=f"ORB Bearish Breakdown, Range: {range_percent:.1f}%",
                confidence=70.0
            )
        
        if signal:
            logger.info(f"📊 {self.name} Signal: {signal.signal.value} {symbol}")
            logger.info(f"   ORB Range: ₹{orb_low:.2f} - ₹{orb_high:.2f}")
            logger.info(f"   Entry: ₹{signal.entry_price} | SL: ₹{signal.stop_loss} | Target: ₹{signal.target}")
        
        return signal
    
    def get_entry_conditions(self) -> List[str]:
        return [
            "Calculate high/low of 9:15-9:30 candle",
            "Range should be 0.5% - 2.5% of price",
            "For LONG: Price closes above ORB high",
            "For SHORT: Price closes below ORB low",
            "Supertrend confirms direction",
            "Volume > 1.2x average on breakout"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            "Target: 1x the ORB range",
            "Stop-loss: Opposite side of range (or middle for tight SL)",
            "Time exit: 11:30 AM if not working",
            "Exit if price re-enters range"
        ]
