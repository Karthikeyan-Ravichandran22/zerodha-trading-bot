"""
EMA Crossover Strategy - Swing trading on daily charts
"""

import pandas as pd
from typing import Optional, List
from loguru import logger

from .base_strategy import BaseStrategy, TradeSignal, Signal
from utils.indicators import calculate_ema, calculate_rsi


class EMACrossoverStrategy(BaseStrategy):
    """
    EMA 9/21 Crossover Strategy (Swing Trading)
    
    Logic:
    - Buy when EMA 9 crosses above EMA 21 on daily chart
    - Sell when EMA 9 crosses below EMA 21
    - Use RSI for overbought/oversold confirmation
    - Hold for 2-5 days
    """
    
    name = "EMA Crossover"
    description = "9/21 EMA crossover for swing trades"
    timeframe = "day"
    min_capital = 5000
    
    # Strategy parameters
    ema_fast = 9
    ema_slow = 21
    rsi_period = 14
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add EMAs and RSI"""
        data = data.copy()
        data['ema_fast'] = calculate_ema(data['close'], self.ema_fast)
        data['ema_slow'] = calculate_ema(data['close'], self.ema_slow)
        data['rsi'] = calculate_rsi(data['close'], self.rsi_period)
        
        # Crossover detection
        data['ema_diff'] = data['ema_fast'] - data['ema_slow']
        data['prev_diff'] = data['ema_diff'].shift(1)
        
        # Volume analysis
        data['vol_sma'] = data['volume'].rolling(20).mean()
        data['vol_ratio'] = data['volume'] / data['vol_sma']
        
        return data
    
    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Analyze for EMA crossover"""
        if len(data) < 25:
            return None
        
        current = data.iloc[-1]
        prev = data.iloc[-2]
        close = current['close']
        rsi = current['rsi']
        
        signal = None
        
        # BULLISH CROSSOVER (EMA 9 crosses above EMA 21)
        if (prev['ema_diff'] <= 0 and  # Was below or equal
            current['ema_diff'] > 0 and  # Now above
            rsi > 45 and rsi < 70 and  # Not overbought
            current['vol_ratio'] > 1.0):  # Decent volume
            
            entry = close
            stop_loss = current['ema_slow'] * 0.97  # 3% below slow EMA
            target = entry * 1.05  # 5% target
            
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
                reason=f"Bullish EMA Crossover, RSI: {rsi:.0f}",
                confidence=70.0
            )
        
        # BEARISH CROSSOVER (EMA 9 crosses below EMA 21)
        elif (prev['ema_diff'] >= 0 and
              current['ema_diff'] < 0 and
              rsi < 55 and rsi > 30):
            
            entry = close
            stop_loss = current['ema_slow'] * 1.03
            target = entry * 0.95
            
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
                reason=f"Bearish EMA Crossover, RSI: {rsi:.0f}",
                confidence=70.0
            )
        
        if signal:
            logger.info(f"📊 {self.name} Signal: {signal.signal.value} {symbol}")
            logger.info(f"   EMA9: ₹{current['ema_fast']:.2f} | EMA21: ₹{current['ema_slow']:.2f}")
            logger.info(f"   Entry: ₹{signal.entry_price} | SL: ₹{signal.stop_loss} | Target: ₹{signal.target}")
        
        return signal
    
    def get_entry_conditions(self) -> List[str]:
        return [
            "EMA 9 crosses above EMA 21 (bullish)",
            "EMA 9 crosses below EMA 21 (bearish)",
            "RSI between 45-70 for longs, 30-55 for shorts",
            "Volume above average",
            "Preferably enter on pullback to EMA 9"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            "Target: 5% profit",
            "Stop-loss: 3% below EMA 21",
            "Trailing stop after 3% profit",
            "Exit on opposite crossover signal"
        ]
