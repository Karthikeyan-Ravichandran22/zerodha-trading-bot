"""
Gap and Go Strategy - Trade morning gap momentum
"""

import pandas as pd
from typing import Optional, List
from loguru import logger

from .base_strategy import BaseStrategy, TradeSignal, Signal
from utils.indicators import calculate_vwap


class GapAndGoStrategy(BaseStrategy):
    """
    Gap and Go Trading Strategy
    
    Logic:
    - Look for 1-2% gap up/down at market open
    - Wait for first 15-min candle to confirm direction
    - Enter on break of first candle high (gap up) or low (gap down)
    - VWAP and volume must confirm
    """
    
    name = "Gap and Go"
    description = "Trade morning gap momentum with confirmation"
    timeframe = "15minute"
    min_capital = 5000
    
    # Strategy parameters
    min_gap_percent = 1.0
    max_gap_percent = 3.0
    min_volume_ratio = 1.5
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add VWAP and volume analysis"""
        data = data.copy()
        data['vwap'] = calculate_vwap(data)
        data['vol_sma'] = data['volume'].rolling(20).mean()
        data['vol_ratio'] = data['volume'] / data['vol_sma']
        return data
    
    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Analyze for gap and go setup"""
        if len(data) < 5:
            return None
        
        # Get today's first candle and previous day's close
        today_data = data.tail(5)  # Last 5 candles
        if len(today_data) < 2:
            return None
        
        first_candle = today_data.iloc[0]
        current = today_data.iloc[-1]
        
        # Approximate previous close (day before)
        prev_close = data.iloc[-6]['close'] if len(data) > 5 else first_candle['open']
        open_price = first_candle['open']
        
        # Calculate gap percentage
        gap_percent = ((open_price - prev_close) / prev_close) * 100
        
        # Check if gap is in valid range
        if abs(gap_percent) < self.min_gap_percent:
            return None  # Gap too small
        if abs(gap_percent) > self.max_gap_percent:
            return None  # Gap too large (risky for reversal)
        
        signal = None
        close = current['close']
        vwap = current['vwap']
        
        # GAP UP scenario
        if gap_percent >= self.min_gap_percent:
            first_candle_bullish = first_candle['close'] > first_candle['open']
            first_high = first_candle['high']
            first_low = first_candle['low']
            
            # Check for breakout of first candle high
            if (first_candle_bullish and
                close > first_high and
                close > vwap and
                current['vol_ratio'] > self.min_volume_ratio):
                
                entry = close
                stop_loss = first_low
                risk = entry - stop_loss
                target = entry + (risk * 1.5)
                
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
                    reason=f"Gap Up +{gap_percent:.1f}%, Breakout of first candle",
                    confidence=75.0
                )
        
        # GAP DOWN scenario
        elif gap_percent <= -self.min_gap_percent:
            first_candle_bearish = first_candle['close'] < first_candle['open']
            first_high = first_candle['high']
            first_low = first_candle['low']
            
            if (first_candle_bearish and
                close < first_low and
                close < vwap and
                current['vol_ratio'] > self.min_volume_ratio):
                
                entry = close
                stop_loss = first_high
                risk = stop_loss - entry
                target = entry - (risk * 1.5)
                
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
                    reason=f"Gap Down {gap_percent:.1f}%, Breakdown of first candle",
                    confidence=75.0
                )
        
        if signal:
            logger.info(f"📊 {self.name} Signal: {signal.signal.value} {symbol}")
            logger.info(f"   Gap: {gap_percent:+.1f}%")
            logger.info(f"   Entry: ₹{signal.entry_price} | SL: ₹{signal.stop_loss} | Target: ₹{signal.target}")
        
        return signal
    
    def get_entry_conditions(self) -> List[str]:
        return [
            "Gap of 1-3% from previous close",
            "First 15-min candle confirms gap direction",
            "For GAP UP: First candle green, break of high",
            "For GAP DOWN: First candle red, break of low",
            "Price above VWAP (gap up) or below VWAP (gap down)",
            "Volume > 1.5x average"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            "Target: 1.5x risk",
            "Stop-loss: Below first candle low (gap up) or above high (gap down)",
            "Time exit: 10:30 AM",
            "Exit if VWAP crosses against position"
        ]
