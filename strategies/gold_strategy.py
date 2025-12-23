"""
Gold Trading Strategy for MCX
Paper trading mode - tracks signals without real orders
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
class GoldSignal:
    """Gold trading signal"""
    symbol: str
    signal: str  # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    target: float
    quantity: int
    timestamp: datetime
    confidence: float
    reason: str


class GoldStrategy:
    """
    Gold EMA Crossover Strategy
    - Uses EMA(9) and EMA(21) crossover
    - RSI filter to avoid overbought/oversold
    - Designed for MCX Gold Mini
    """
    
    def __init__(self, capital: float = 20000):
        self.capital = capital
        self.current_position = None
        self.paper_trades = []
        self.paper_pnl = 0
        
        # Strategy parameters
        self.ema_fast = 9
        self.ema_slow = 21
        self.rsi_period = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        
        # Risk management
        self.sl_percent = 0.5  # 0.5% stop loss (commodities are volatile)
        self.target_percent = 1.0  # 1% target
        self.risk_per_trade = 0.02  # 2% of capital
        
    def fetch_gold_data(self, period: str = "5d", interval: str = "5m") -> Optional[pd.DataFrame]:
        """Fetch Gold futures data from Yahoo Finance"""
        try:
            # Gold futures symbol
            data = yf.download("GC=F", period=period, interval=interval, progress=False)
            
            if len(data) < 30:
                logger.warning("Insufficient gold data")
                return None
            
            # Flatten columns if multi-index
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch gold data: {e}")
            return None
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators"""
        df = data.copy()
        
        close = df['Close'].squeeze()
        
        # EMAs
        df['EMA9'] = close.ewm(span=self.ema_fast).mean()
        df['EMA21'] = close.ewm(span=self.ema_slow).mean()
        
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(self.rsi_period).mean()
        loss = (-delta.clip(upper=0)).rolling(self.rsi_period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Trend
        df['Trend'] = np.where(df['EMA9'] > df['EMA21'], 'UP', 'DOWN')
        
        # EMA crossover signal
        df['EMA_Cross'] = df['EMA9'] - df['EMA21']
        df['EMA_Cross_Prev'] = df['EMA_Cross'].shift(1)
        
        return df
    
    def generate_signal(self) -> Optional[GoldSignal]:
        """Generate trading signal for Gold"""
        try:
            # Fetch data
            data = self.fetch_gold_data()
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
            rsi = float(latest['RSI'])
            
            prev_ema9 = float(prev['EMA9'])
            prev_ema21 = float(prev['EMA21'])
            
            signal = None
            reason = ""
            confidence = 0
            
            # BUY signal: EMA9 crosses above EMA21, RSI not overbought
            if prev_ema9 <= prev_ema21 and ema9 > ema21:
                if rsi < self.rsi_overbought:
                    signal = "BUY"
                    reason = f"EMA9 crossed above EMA21, RSI={rsi:.1f}"
                    confidence = min(0.8, 0.5 + (70 - rsi) / 100)
                    
            # SELL signal: EMA9 crosses below EMA21, RSI not oversold
            elif prev_ema9 >= prev_ema21 and ema9 < ema21:
                if rsi > self.rsi_oversold:
                    signal = "SELL"
                    reason = f"EMA9 crossed below EMA21, RSI={rsi:.1f}"
                    confidence = min(0.8, 0.5 + (rsi - 30) / 100)
            
            if signal:
                # Calculate SL and Target
                if signal == "BUY":
                    sl = close * (1 - self.sl_percent / 100)
                    target = close * (1 + self.target_percent / 100)
                else:
                    sl = close * (1 + self.sl_percent / 100)
                    target = close * (1 - self.target_percent / 100)
                
                return GoldSignal(
                    symbol="GOLDM",  # Gold Mini on MCX
                    signal=signal,
                    entry_price=close,
                    stop_loss=round(sl, 2),
                    target=round(target, 2),
                    quantity=1,  # 1 lot for paper trading
                    timestamp=datetime.now(IST),
                    confidence=confidence,
                    reason=reason
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating gold signal: {e}")
            return None
    
    def record_paper_trade(self, signal: GoldSignal):
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
            'pnl': None
        }
        self.paper_trades.append(trade)
        self.current_position = trade
        logger.info(f"📝 GOLD PAPER TRADE: {signal.signal} @ ${signal.entry_price}")
    
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
            logger.info(f"📝 GOLD PAPER CLOSE: {reason} @ ${exit_price} | P&L: ${pnl:+.2f}")
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


# Global instance
gold_strategy = GoldStrategy()
