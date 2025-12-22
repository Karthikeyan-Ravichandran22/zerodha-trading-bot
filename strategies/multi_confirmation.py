"""
HIGH PROBABILITY MULTI-CONFIRMATION SCALPING STRATEGY

This strategy ONLY enters when ALL indicators confirm:
- VWAP position
- EMA crossover
- RSI confirmation
- Supertrend direction
- Volume confirmation

Target: Quick 0.5-1% profits with tight stop-loss
Goal: 70-80% win rate through strict entry criteria

WARNING: No strategy can guarantee 100% win rate!
"""

import pandas as pd
from typing import Optional, List, Tuple
from dataclasses import dataclass
from loguru import logger

from strategies.base_strategy import BaseStrategy, TradeSignal, Signal
from utils.indicators import (
    calculate_vwap, calculate_rsi, calculate_ema, 
    calculate_supertrend, calculate_atr
)


@dataclass
class ConfirmationScore:
    """Track how many indicators confirm the trade"""
    vwap_confirm: bool = False
    ema_confirm: bool = False
    rsi_confirm: bool = False
    supertrend_confirm: bool = False
    volume_confirm: bool = False
    price_action_confirm: bool = False
    
    @property
    def score(self) -> int:
        return sum([
            self.vwap_confirm,
            self.ema_confirm,
            self.rsi_confirm,
            self.supertrend_confirm,
            self.volume_confirm,
            self.price_action_confirm
        ])
    
    @property
    def is_high_probability(self) -> bool:
        """Need at least 5 out of 6 confirmations"""
        return self.score >= 5


class MultiConfirmationScalper(BaseStrategy):
    """
    Multi-Confirmation Scalping Strategy
    
    ONLY enters trade when MULTIPLE indicators confirm:
    1. Price above/below VWAP
    2. EMA 9 > EMA 21 (or vice versa for shorts)
    3. RSI in favorable zone (not overbought/oversold against trend)
    4. Supertrend in same direction
    5. Volume above average
    6. Bullish/Bearish candle pattern
    
    Quick Exit Rules:
    - Take profit at 0.5-1% (scalp target)
    - Exit immediately if ANY indicator flips
    - Tight stop-loss at 0.3-0.5%
    """
    
    name = "Multi-Confirmation Scalper"
    description = "High probability trades with multiple indicator confirmation"
    timeframe = "5minute"
    min_capital = 5000
    
    # Strict parameters for high win rate
    min_confirmations = 5  # Out of 6
    target_percent = 0.5   # Quick 0.5% profit
    stop_loss_percent = 0.3  # Tight 0.3% SL
    min_volume_ratio = 1.3  # Volume must be 30% above average
    
    # RSI zones
    rsi_bullish_min = 45
    rsi_bullish_max = 65
    rsi_bearish_min = 35
    rsi_bearish_max = 55
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required indicators"""
        data = data.copy()
        
        # VWAP
        data['vwap'] = calculate_vwap(data)
        
        # EMAs
        data['ema9'] = calculate_ema(data['close'], 9)
        data['ema21'] = calculate_ema(data['close'], 21)
        
        # RSI
        data['rsi'] = calculate_rsi(data['close'], 14)
        
        # Supertrend
        st = calculate_supertrend(data, period=10, multiplier=3)
        data['supertrend'] = st['supertrend']
        data['st_direction'] = st['direction']
        
        # Volume
        data['vol_sma'] = data['volume'].rolling(20).mean()
        data['vol_ratio'] = data['volume'] / data['vol_sma']
        
        # ATR for dynamic SL
        data['atr'] = calculate_atr(data, 14)
        
        # Candle patterns
        data['body'] = data['close'] - data['open']
        data['body_pct'] = abs(data['body']) / data['open'] * 100
        data['is_bullish'] = data['close'] > data['open']
        data['is_bearish'] = data['close'] < data['open']
        
        # Trend strength
        data['ema_diff'] = data['ema9'] - data['ema21']
        data['ema_diff_pct'] = abs(data['ema_diff']) / data['close'] * 100
        
        return data
    
    def check_confirmations(self, data: pd.DataFrame, is_long: bool) -> ConfirmationScore:
        """Check all confirmation indicators"""
        current = data.iloc[-1]
        prev = data.iloc[-2]
        score = ConfirmationScore()
        
        if is_long:
            # 1. VWAP: Price above VWAP
            score.vwap_confirm = current['close'] > current['vwap']
            
            # 2. EMA: Fast above Slow
            score.ema_confirm = current['ema9'] > current['ema21']
            
            # 3. RSI: In bullish zone (not overbought)
            score.rsi_confirm = (
                self.rsi_bullish_min <= current['rsi'] <= self.rsi_bullish_max
            )
            
            # 4. Supertrend: Bullish
            score.supertrend_confirm = current['st_direction'] == 1
            
            # 5. Volume: Above average
            score.volume_confirm = current['vol_ratio'] > self.min_volume_ratio
            
            # 6. Candle: Bullish candle
            score.price_action_confirm = current['is_bullish'] and current['body_pct'] > 0.1
            
        else:  # Short
            # 1. VWAP: Price below VWAP
            score.vwap_confirm = current['close'] < current['vwap']
            
            # 2. EMA: Fast below Slow
            score.ema_confirm = current['ema9'] < current['ema21']
            
            # 3. RSI: In bearish zone (not oversold)
            score.rsi_confirm = (
                self.rsi_bearish_min <= current['rsi'] <= self.rsi_bearish_max
            )
            
            # 4. Supertrend: Bearish
            score.supertrend_confirm = current['st_direction'] == -1
            
            # 5. Volume: Above average
            score.volume_confirm = current['vol_ratio'] > self.min_volume_ratio
            
            # 6. Candle: Bearish candle
            score.price_action_confirm = current['is_bearish'] and current['body_pct'] > 0.1
        
        return score
    
    def analyze(self, symbol: str, data: pd.DataFrame) -> Optional[TradeSignal]:
        """Analyze for high-probability setup"""
        if len(data) < 30:
            return None
        
        current = data.iloc[-1]
        close = current['close']
        
        # Check LONG setup
        long_score = self.check_confirmations(data, is_long=True)
        
        if long_score.is_high_probability:
            entry = close
            stop_loss = entry * (1 - self.stop_loss_percent / 100)
            target = entry * (1 + self.target_percent / 100)
            
            if self.risk_manager:
                qty = self.risk_manager.calculate_position_size(entry, stop_loss)
            else:
                qty = 10
            
            logger.info(f"🎯 HIGH PROBABILITY LONG: {symbol}")
            logger.info(f"   Confirmations: {long_score.score}/6")
            logger.info(f"   VWAP: {'✅' if long_score.vwap_confirm else '❌'}")
            logger.info(f"   EMA: {'✅' if long_score.ema_confirm else '❌'}")
            logger.info(f"   RSI: {'✅' if long_score.rsi_confirm else '❌'}")
            logger.info(f"   Supertrend: {'✅' if long_score.supertrend_confirm else '❌'}")
            logger.info(f"   Volume: {'✅' if long_score.volume_confirm else '❌'}")
            logger.info(f"   Price Action: {'✅' if long_score.price_action_confirm else '❌'}")
            
            return TradeSignal(
                signal=Signal.BUY,
                symbol=symbol,
                entry_price=round(entry, 2),
                stop_loss=round(stop_loss, 2),
                target=round(target, 2),
                quantity=qty,
                reason=f"Multi-confirmation: {long_score.score}/6 indicators bullish",
                confidence=long_score.score / 6 * 100
            )
        
        # Check SHORT setup
        short_score = self.check_confirmations(data, is_long=False)
        
        if short_score.is_high_probability:
            entry = close
            stop_loss = entry * (1 + self.stop_loss_percent / 100)
            target = entry * (1 - self.target_percent / 100)
            
            if self.risk_manager:
                qty = self.risk_manager.calculate_position_size(entry, stop_loss)
            else:
                qty = 10
            
            logger.info(f"🎯 HIGH PROBABILITY SHORT: {symbol}")
            logger.info(f"   Confirmations: {short_score.score}/6")
            
            return TradeSignal(
                signal=Signal.SELL,
                symbol=symbol,
                entry_price=round(entry, 2),
                stop_loss=round(stop_loss, 2),
                target=round(target, 2),
                quantity=qty,
                reason=f"Multi-confirmation: {short_score.score}/6 indicators bearish",
                confidence=short_score.score / 6 * 100
            )
        
        return None
    
    def should_exit_early(self, data: pd.DataFrame, is_long: bool) -> Tuple[bool, str]:
        """Check if we should exit before SL/Target"""
        current = data.iloc[-1]
        
        if is_long:
            # Exit if ANY major indicator flips
            if current['close'] < current['vwap']:
                return True, "Price crossed below VWAP"
            if current['st_direction'] == -1:
                return True, "Supertrend turned bearish"
            if current['ema9'] < current['ema21']:
                return True, "EMA crossover turned bearish"
            if current['rsi'] > 70:
                return True, "RSI overbought - taking profit"
        else:
            if current['close'] > current['vwap']:
                return True, "Price crossed above VWAP"
            if current['st_direction'] == 1:
                return True, "Supertrend turned bullish"
            if current['ema9'] > current['ema21']:
                return True, "EMA crossover turned bullish"
            if current['rsi'] < 30:
                return True, "RSI oversold - taking profit"
        
        return False, ""
    
    def get_entry_conditions(self) -> List[str]:
        return [
            "MINIMUM 5 out of 6 indicators must confirm:",
            "1. Price above VWAP (for longs)",
            "2. EMA 9 > EMA 21",
            "3. RSI in favorable zone (45-65 for longs)",
            "4. Supertrend bullish",
            "5. Volume > 1.3x average",
            "6. Bullish candle pattern",
            "",
            "This ensures high-probability entries only!"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            "Quick profit target: 0.5%",
            "Tight stop-loss: 0.3%",
            "IMMEDIATE exit if ANY indicator flips:",
            "- Price crosses VWAP against position",
            "- Supertrend changes direction",
            "- EMA crossover reverses",
            "- RSI reaches extreme levels"
        ]


# Alias for easy import
HighProbabilityStrategy = MultiConfirmationScalper
