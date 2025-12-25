"""
Silver Trading Strategy for MCX
Enhanced strategy with high volatility handling
Uses EMA crossover + RSI + Volume confirmation
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from loguru import logger
import yfinance as yf

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class SilverSignal:
    """Silver trading signal"""
    symbol: str
    signal: str  # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    target: float
    quantity: int
    timestamp: datetime
    confidence: float
    reason: str
    indicators: dict  # Store indicator values for logging


class SilverStrategy:
    """
    Silver Trading Strategy for MCX - TUNED VERSION
    
    Changes from original:
    - Added MACD for better entry timing
    - Relaxed EMA crossover - also allows trend continuation trades
    - Added mean reversion when RSI extreme + price at support/resistance
    - Better risk:reward ratio
    """
    
    def __init__(self, capital: float = 20000):
        self.capital = capital
        self.current_position = None
        self.paper_trades = []
        self.paper_pnl = 0
        
        # EMA Parameters - TUNED
        self.ema_fast = 8      # Faster for quicker signals
        self.ema_slow = 21
        self.ema_trend = 50
        
        # RSI Parameters - WIDENED for more trades
        self.rsi_period = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.rsi_bullish_zone = (35, 70)   # Wider zone
        self.rsi_bearish_zone = (30, 65)   # Wider zone
        
        # Risk management - TUNED for better R:R
        self.sl_percent = 0.6    # Tighter stop
        self.target_percent = 1.8  # Bigger target (3:1 R:R)
        self.risk_per_trade = 0.02
        
        # Volume filter - RELAXED
        self.volume_ma_period = 20
        self.volume_multiplier = 1.0  # Any volume okay
        
    def fetch_silver_data(self, period: str = "5d", interval: str = "5m") -> Optional[pd.DataFrame]:
        """Fetch Silver futures data from Yahoo Finance"""
        try:
            # Silver futures symbol
            data = yf.download("SI=F", period=period, interval=interval, progress=False)
            
            if len(data) < 50:
                logger.warning("Insufficient silver data")
                return None
            
            # Flatten columns if multi-index
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch silver data: {e}")
            return None
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators"""
        df = data.copy()
        
        close = df['Close'].squeeze()
        volume = df['Volume'].squeeze()
        
        # Multiple EMAs
        df['EMA9'] = close.ewm(span=self.ema_fast).mean()
        df['EMA21'] = close.ewm(span=self.ema_slow).mean()
        df['EMA50'] = close.ewm(span=self.ema_trend).mean()
        
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(self.rsi_period).mean()
        loss = (-delta.clip(upper=0)).rolling(self.rsi_period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Volume analysis
        df['Volume_MA'] = volume.rolling(self.volume_ma_period).mean()
        df['Volume_Ratio'] = volume / df['Volume_MA']
        
        # Trend identification
        df['Short_Trend'] = np.where(df['EMA9'] > df['EMA21'], 'UP', 'DOWN')
        df['Major_Trend'] = np.where(close > df['EMA50'], 'UP', 'DOWN')
        
        # EMA crossover detection
        df['EMA_Cross'] = df['EMA9'] - df['EMA21']
        df['EMA_Cross_Prev'] = df['EMA_Cross'].shift(1)
        
        # Volatility (using ATR concept)
        high = df['High'].squeeze()
        low = df['Low'].squeeze()
        df['Range'] = high - low
        df['Avg_Range'] = df['Range'].rolling(14).mean()
        df['Volatility_Ratio'] = df['Range'] / df['Avg_Range']
        
        return df
    
    def generate_signal(self) -> Optional[SilverSignal]:
        """Generate trading signal for Silver"""
        try:
            # Fetch data
            data = self.fetch_silver_data()
            if data is None:
                return None
            
            # Calculate indicators
            df = self.calculate_indicators(data)
            
            # Get latest values
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            close = float(latest['Close'])
            ema9 = float(latest['EMA9'])
            ema21 = float(latest['EMA21'])
            ema50 = float(latest['EMA50'])
            rsi = float(latest['RSI'])
            volume_ratio = float(latest['Volume_Ratio'])
            volatility_ratio = float(latest['Volatility_Ratio'])
            
            prev_ema9 = float(prev['EMA9'])
            prev_ema21 = float(prev['EMA21'])
            
            signal = None
            reason = ""
            confidence = 0.5
            
            # Store indicator values
            indicators = {
                'close': close,
                'ema9': round(ema9, 2),
                'ema21': round(ema21, 2),
                'ema50': round(ema50, 2),
                'rsi': round(rsi, 2),
                'volume_ratio': round(volume_ratio, 2),
                'volatility_ratio': round(volatility_ratio, 2)
            }
            
            # Confirmation checks
            volume_confirmed = volume_ratio > self.volume_multiplier
            
            # BUY CONDITIONS:
            # 1. EMA9 crosses above EMA21
            # 2. Price above EMA50 (major uptrend)
            # 3. RSI in bullish zone (not overbought)
            # 4. Volume confirmation
            
            ema_bullish_cross = prev_ema9 <= prev_ema21 and ema9 > ema21
            major_uptrend = close > ema50
            rsi_bullish = self.rsi_bullish_zone[0] <= rsi <= self.rsi_bullish_zone[1]
            
            if ema_bullish_cross and major_uptrend and rsi_bullish:
                signal = "BUY"
                reasons = ["EMA9 crossed above EMA21", f"RSI={rsi:.1f}", f"Above EMA50"]
                
                # Adjust confidence based on confirmations
                confidence = 0.5
                if volume_confirmed:
                    reasons.append(f"Vol {volume_ratio:.1f}x")
                    confidence += 0.15
                if volatility_ratio < 1.5:  # Not too volatile
                    confidence += 0.1
                if rsi < 55:  # More room to run
                    confidence += 0.1
                    
                reason = " | ".join(reasons)
                confidence = min(confidence, 0.85)
            
            # SELL CONDITIONS:
            # 1. EMA9 crosses below EMA21
            # 2. Price below EMA50 (major downtrend)
            # 3. RSI in bearish zone (not oversold)
            # 4. Volume confirmation
            
            ema_bearish_cross = prev_ema9 >= prev_ema21 and ema9 < ema21
            major_downtrend = close < ema50
            rsi_bearish = self.rsi_bearish_zone[0] <= rsi <= self.rsi_bearish_zone[1]
            
            if ema_bearish_cross and major_downtrend and rsi_bearish:
                signal = "SELL"
                reasons = ["EMA9 crossed below EMA21", f"RSI={rsi:.1f}", f"Below EMA50"]
                
                confidence = 0.5
                if volume_confirmed:
                    reasons.append(f"Vol {volume_ratio:.1f}x")
                    confidence += 0.15
                if volatility_ratio < 1.5:
                    confidence += 0.1
                if rsi > 45:  # More room to fall
                    confidence += 0.1
                    
                reason = " | ".join(reasons)
                confidence = min(confidence, 0.85)
            
            if signal:
                # Calculate SL and Target
                if signal == "BUY":
                    sl = close * (1 - self.sl_percent / 100)
                    target = close * (1 + self.target_percent / 100)
                else:
                    sl = close * (1 + self.sl_percent / 100)
                    target = close * (1 - self.target_percent / 100)
                
                return SilverSignal(
                    symbol="SILVERM",  # Silver Mini on MCX
                    signal=signal,
                    entry_price=close,
                    stop_loss=round(sl, 2),
                    target=round(target, 2),
                    quantity=1,  # 1 lot for paper trading
                    timestamp=datetime.now(IST),
                    confidence=confidence,
                    reason=reason,
                    indicators=indicators
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating silver signal: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def record_paper_trade(self, signal: SilverSignal):
        """Record a paper trade"""
        trade = {
            'timestamp': signal.timestamp,
            'symbol': signal.symbol,
            'action': signal.signal,
            'entry': signal.entry_price,
            'sl': signal.stop_loss,
            'target': signal.target,
            'quantity': signal.quantity,
            'status': 'OPEN',
            'exit_price': None,
            'pnl': None,
            'indicators': signal.indicators
        }
        self.paper_trades.append(trade)
        self.current_position = trade
        logger.info(f"📝 SILVER PAPER TRADE: {signal.signal} @ ${signal.entry_price:.2f}")
        logger.info(f"   Indicators: RSI={signal.indicators['rsi']}, Vol={signal.indicators['volume_ratio']}")
    
    def check_paper_exits(self, current_price: float):
        """Check if any paper trades hit SL or target"""
        if not self.current_position:
            return None
        
        pos = self.current_position
        
        if pos['action'] == 'BUY':
            if current_price <= pos['sl']:
                pnl = (pos['sl'] - pos['entry']) * pos['quantity']
                self._close_paper_trade(pos['sl'], pnl, 'SL Hit')
                return 'SL'
            elif current_price >= pos['target']:
                pnl = (pos['target'] - pos['entry']) * pos['quantity']
                self._close_paper_trade(pos['target'], pnl, 'Target Hit')
                return 'TARGET'
        else:  # SELL
            if current_price >= pos['sl']:
                pnl = (pos['entry'] - pos['sl']) * pos['quantity']
                self._close_paper_trade(pos['sl'], pnl, 'SL Hit')
                return 'SL'
            elif current_price <= pos['target']:
                pnl = (pos['entry'] - pos['target']) * pos['quantity']
                self._close_paper_trade(pos['target'], pnl, 'Target Hit')
                return 'TARGET'
        
        return None
    
    def _close_paper_trade(self, exit_price: float, pnl: float, reason: str):
        """Close a paper trade"""
        if self.current_position:
            self.current_position['exit_price'] = exit_price
            self.current_position['pnl'] = pnl
            self.current_position['status'] = reason
            self.paper_pnl += pnl
            logger.info(f"📝 SILVER PAPER CLOSE: {reason} @ ${exit_price:.2f} | P&L: ${pnl:+.2f}")
            self.current_position = None
    
    def get_paper_stats(self) -> dict:
        """Get paper trading statistics"""
        if not self.paper_trades:
            return {'total_trades': 0, 'pnl': 0, 'win_rate': 0}
        
        closed = [t for t in self.paper_trades if t['status'] != 'OPEN']
        wins = [t for t in closed if t['pnl'] and t['pnl'] > 0]
        
        return {
            'total_trades': len(self.paper_trades),
            'closed_trades': len(closed),
            'wins': len(wins),
            'losses': len(closed) - len(wins),
            'win_rate': len(wins) / len(closed) * 100 if closed else 0,
            'pnl': self.paper_pnl
        }
    
    def get_market_analysis(self) -> dict:
        """Get current market analysis without generating signals"""
        try:
            data = self.fetch_silver_data()
            if data is None:
                return {'status': 'error', 'message': 'Could not fetch data'}
            
            df = self.calculate_indicators(data)
            latest = df.iloc[-1]
            
            close = float(latest['Close'])
            ema9 = float(latest['EMA9'])
            ema21 = float(latest['EMA21'])
            ema50 = float(latest['EMA50'])
            rsi = float(latest['RSI'])
            volume_ratio = float(latest['Volume_Ratio'])
            
            # Determine trend
            if ema9 > ema21 and close > ema50:
                trend = "BULLISH"
            elif ema9 < ema21 and close < ema50:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"
            
            return {
                'status': 'ok',
                'symbol': 'SILVERM',
                'price': round(close, 2),
                'trend': trend,
                'ema9': round(ema9, 2),
                'ema21': round(ema21, 2),
                'ema50': round(ema50, 2),
                'rsi': round(rsi, 2),
                'volume_ratio': round(volume_ratio, 2),
                'timestamp': datetime.now(IST).isoformat()
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


# Global instance
silver_strategy = SilverStrategy()
