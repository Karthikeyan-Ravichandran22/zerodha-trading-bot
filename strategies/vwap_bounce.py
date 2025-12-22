"""
VWAP Bounce Strategy - Buy/Sell at VWAP support/resistance
"""

import pandas as pd
from typing import Optional, List
from loguru import logger

from .base_strategy import BaseStrategy, TradeSignal, Signal
from utils.indicators import calculate_vwap, calculate_rsi


class VWAPBounceStrategy(BaseStrategy):
    """
    VWAP Bounce Trading Strategy
    
    Logic:
    - In uptrend: Buy when price bounces off VWAP from above
    - In downtrend: Sell when price rejects VWAP from below
    - Use RSI for confirmation
    """
    
    name = "VWAP Bounce"
    description = "Trade bounces off VWAP support/resistance"
    timeframe = "5minute"
    min_capital = 5000
    
    # Strategy parameters
    rsi_oversold = 40
    rsi_overbought = 60
    vwap_tolerance = 0.003  # 0.3% from VWAP
    min_risk_reward = 1.5
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add VWAP and RSI to data"""
        data = data.copy()
        data['vwap'] = calculate_vwap(data)
        data['rsi'] = calculate_rsi(data['close'], period=14)
        data['above_vwap'] = data['close'] > data['vwap']
        
        # Distance from VWAP
        data['vwap_distance'] = (data['close'] - data['vwap']) / data['vwap']
        
        return data
    
    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Analyze for VWAP bounce setup"""
        if len(data) < 20:
            return None
        
        current = data.iloc[-1]
        prev = data.iloc[-2]
        vwap = current['vwap']
        close = current['close']
        rsi = current['rsi']
        
        # Check if price is near VWAP
        distance = abs(current['vwap_distance'])
        if distance > self.vwap_tolerance:
            return None  # Not close enough to VWAP
        
        signal = None
        
        # BULLISH BOUNCE (price touching VWAP from above, bouncing up)
        if (prev['close'] > prev['vwap'] and
            current['low'] <= vwap * 1.003 and  # Touched VWAP
            close > vwap and  # Closed above
            rsi > self.rsi_oversold and rsi < 70):  # Not overbought
            
            # Check for bullish candle (hammer or green)
            is_bullish = (close > current['open'] or 
                         current['low'] < current['open'] * 0.995)
            
            if is_bullish:
                entry = close
                stop_loss = vwap * 0.995  # SL below VWAP
                target = entry + (entry - stop_loss) * self.min_risk_reward
                
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
                    reason=f"Bullish VWAP bounce, RSI: {rsi:.0f}",
                    confidence=75.0
                )
        
        # BEARISH BOUNCE (price touching VWAP from below, rejecting)
        elif (prev['close'] < prev['vwap'] and
              current['high'] >= vwap * 0.997 and  # Touched VWAP
              close < vwap and  # Closed below
              rsi < self.rsi_overbought and rsi > 30):
            
            is_bearish = (close < current['open'] or 
                         current['high'] > current['open'] * 1.005)
            
            if is_bearish:
                entry = close
                stop_loss = vwap * 1.005
                target = entry - (stop_loss - entry) * self.min_risk_reward
                
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
                    reason=f"Bearish VWAP rejection, RSI: {rsi:.0f}",
                    confidence=70.0
                )
        
        if signal:
            logger.info(f"📊 {self.name} Signal: {signal.signal.value} {symbol}")
            logger.info(f"   Entry: ₹{signal.entry_price} | SL: ₹{signal.stop_loss} | Target: ₹{signal.target}")
        
        return signal
    
    def get_entry_conditions(self) -> List[str]:
        return [
            "Price is within 0.3% of VWAP",
            "For LONG: Price bounces off VWAP from above with bullish candle",
            "For SHORT: Price rejects VWAP from below with bearish candle",
            "RSI confirms direction (40-70 for longs, 30-60 for shorts)",
            "Volume should be above average"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            "Target hit (1.5x risk)",
            "Stop-loss hit (0.5% beyond VWAP)",
            "Price crosses VWAP against position",
            "Time exit: 2:45 PM"
        ]
