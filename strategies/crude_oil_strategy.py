"""
Crude Oil Trading Strategy for MCX
Uses Camarilla Pivots + EMA + Supertrend
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta, timezone
from loguru import logger
import yfinance as yf

IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class CrudeSignal:
    symbol: str
    signal: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    quantity: int
    timestamp: datetime
    confidence: float
    reason: str
    strategy_type: str
    indicators: dict


class CrudeOilStrategy:
    """
    Crude Oil Strategy - TUNED VERSION
    
    Improvements:
    - Added mean reversion at H3/L3 levels (not just breakout at H4/L4)
    - Relaxed volume requirement
    - Better risk:reward (1:2)
    - Trading with trend OR reversals at extremes
    """
    
    def __init__(self, capital: float = 20000):
        self.capital = capital
        self.current_position = None
        self.paper_trades = []
        self.paper_pnl = 0
        self.ema_fast, self.ema_slow = 12, 26  # MACD-like
        self.st_period, self.st_mult = 7, 2    # Faster supertrend
        self.rsi_period = 14
        self.sl_pct, self.t1_pct, self.t2_pct = 0.6, 0.5, 1.2  # Better R:R
        self.vol_spike = 1.0  # Relaxed volume
        
    def fetch_data(self, period="5d", interval="5m"):
        try:
            data = yf.download("CL=F", period=period, interval=interval, progress=False)
            if len(data) < 50:
                return None
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return data
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return None
    
    def calc_pivots(self, h, l, c):
        r = h - l
        return {
            'H4': c + r*1.1/2, 'H3': c + r*1.1/4,
            'L3': c - r*1.1/4, 'L4': c - r*1.1/2,
            'Pivot': (h + l + c) / 3
        }
    
    def calc_supertrend(self, df):
        h, l, c = df['High'].squeeze(), df['Low'].squeeze(), df['Close'].squeeze()
        tr = pd.concat([h-l, abs(h-c.shift()), abs(l-c.shift())], axis=1).max(axis=1)
        atr = tr.rolling(self.st_period).mean()
        hl2 = (h + l) / 2
        ub, lb = hl2 + self.st_mult * atr, hl2 - self.st_mult * atr
        
        st = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        for i in range(1, len(df)):
            if c.iloc[i] > ub.iloc[i-1]:
                st.iloc[i], direction.iloc[i] = lb.iloc[i], 1
            elif c.iloc[i] < lb.iloc[i-1]:
                st.iloc[i], direction.iloc[i] = ub.iloc[i], -1
            else:
                st.iloc[i] = st.iloc[i-1] if pd.notna(st.iloc[i-1]) else lb.iloc[i]
                direction.iloc[i] = direction.iloc[i-1] if pd.notna(direction.iloc[i-1]) else 1
        
        df['ST'], df['ST_Dir'], df['ATR'] = st, direction, atr
        return df
    
    def calc_indicators(self, data):
        df = data.copy()
        c, v = df['Close'].squeeze(), df['Volume'].squeeze()
        df['EMA20'] = c.ewm(span=20).mean()
        df['EMA50'] = c.ewm(span=50).mean()
        
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + gain/loss))
        
        df = self.calc_supertrend(df)
        df['Vol_MA'] = v.rolling(20).mean()
        df['Vol_Ratio'] = v / df['Vol_MA']
        df['D_High'] = df['High'].squeeze().rolling(78).max()
        df['D_Low'] = df['Low'].squeeze().rolling(78).min()
        return df
    
    def generate_signal(self):
        try:
            data = self.fetch_data()
            if data is None:
                return None
            
            df = self.calc_indicators(data)
            cur, prev = df.iloc[-1], df.iloc[-2]
            
            close = float(cur['Close'])
            ema20, ema50 = float(cur['EMA20']), float(cur['EMA50'])
            rsi = float(cur['RSI'])
            st_dir = int(cur['ST_Dir']) if pd.notna(cur['ST_Dir']) else 0
            vol_ratio = float(cur['Vol_Ratio'])
            vol_spike = vol_ratio > self.vol_spike
            
            pivots = self.calc_pivots(float(cur['D_High']), float(cur['D_Low']), close)
            
            indicators = {
                'close': close, 'ema20': round(ema20,2), 'ema50': round(ema50,2),
                'rsi': round(rsi,2), 'st_dir': 'BULL' if st_dir==1 else 'BEAR',
                'vol': round(vol_ratio,2), 'h4': round(pivots['H4'],2), 'l4': round(pivots['L4'],2)
            }
            
            signal, reason, conf, stype = None, "", 0.5, ""
            
            # Strategy 1: Breakout at H4/L4
            if close > pivots['H4'] and st_dir == 1:
                signal, stype = "BUY", "BREAKOUT"
                reason = f"Above H4 ({pivots['H4']:.2f}) | ST bullish"
                conf = 0.7
            elif close < pivots['L4'] and st_dir == -1:
                signal, stype = "SELL", "BREAKOUT"
                reason = f"Below L4 ({pivots['L4']:.2f}) | ST bearish"
                conf = 0.7
            
            # Strategy 2: Mean Reversion at H3/L3 (NEW!)
            if not signal:
                # Buy at L3 support with RSI oversold
                if close <= pivots['L3'] and rsi < 40:
                    signal, stype = "BUY", "MEAN_REVERT"
                    reason = f"At L3 support | RSI={rsi:.0f} oversold"
                    conf = 0.6
                # Sell at H3 resistance with RSI overbought
                elif close >= pivots['H3'] and rsi > 60:
                    signal, stype = "SELL", "MEAN_REVERT"
                    reason = f"At H3 resistance | RSI={rsi:.0f} overbought"
                    conf = 0.6
            
            # Strategy 3: Trend Following (EMA + Supertrend)
            if not signal:
                p_ema20, p_ema50 = float(prev['EMA20']), float(prev['EMA50'])
                p_st = int(prev['ST_Dir']) if pd.notna(prev['ST_Dir']) else 0
                
                # Bullish: EMA cross OR Supertrend flip
                ema_cross_up = p_ema20 <= p_ema50 and ema20 > ema50
                st_flip_up = p_st == -1 and st_dir == 1
                
                if (ema_cross_up or st_flip_up) and close > ema50:
                    if 35 < rsi < 75:  # Wider RSI range
                        signal, stype = "BUY", "TREND"
                        reason = f"EMA/ST bullish | RSI={rsi:.0f}"
                        conf = 0.65
                
                # Bearish: EMA cross OR Supertrend flip
                ema_cross_dn = p_ema20 >= p_ema50 and ema20 < ema50
                st_flip_dn = p_st == 1 and st_dir == -1
                
                if (ema_cross_dn or st_flip_dn) and close < ema50:
                    if 25 < rsi < 65:  # Wider RSI range
                        signal, stype = "SELL", "TREND"
                        reason = f"EMA/ST bearish | RSI={rsi:.0f}"
                        conf = 0.65
            
            if signal:
                if signal == "BUY":
                    sl = close * (1 - self.sl_pct/100)
                    t1, t2 = close * (1 + self.t1_pct/100), close * (1 + self.t2_pct/100)
                else:
                    sl = close * (1 + self.sl_pct/100)
                    t1, t2 = close * (1 - self.t1_pct/100), close * (1 - self.t2_pct/100)
                
                return CrudeSignal(
                    symbol="CRUDEOIL", signal=signal, entry_price=close,
                    stop_loss=round(sl,2), target_1=round(t1,2), target_2=round(t2,2),
                    quantity=1, timestamp=datetime.now(IST), confidence=min(conf,0.85),
                    reason=reason, strategy_type=stype, indicators=indicators
                )
            return None
        except Exception as e:
            logger.error(f"Signal error: {e}")
            return None
    
    def record_paper_trade(self, sig):
        trade = {
            'timestamp': sig.timestamp, 'symbol': sig.symbol, 'action': sig.signal,
            'entry': sig.entry_price, 'sl': sig.stop_loss, 't1': sig.target_1,
            't2': sig.target_2, 'qty': sig.quantity, 'status': 'OPEN',
            'exit': None, 'pnl': None, 'type': sig.strategy_type
        }
        self.paper_trades.append(trade)
        self.current_position = trade
        logger.info(f"🛢️ CRUDE: {sig.signal} @ ${sig.entry_price:.2f} | {sig.reason}")
    
    def check_paper_exits(self, price):
        if not self.current_position:
            return None
        pos = self.current_position
        if pos['action'] == 'BUY':
            if price <= pos['sl']:
                pnl = (pos['sl'] - pos['entry']) * pos['qty']
                self._close(pos['sl'], pnl, 'SL')
                return 'SL'
            if price >= pos['t2']:
                pnl = (pos['t2'] - pos['entry']) * pos['qty']
                self._close(pos['t2'], pnl, 'T2')
                return 'T2'
        else:
            if price >= pos['sl']:
                pnl = (pos['entry'] - pos['sl']) * pos['qty']
                self._close(pos['sl'], pnl, 'SL')
                return 'SL'
            if price <= pos['t2']:
                pnl = (pos['entry'] - pos['t2']) * pos['qty']
                self._close(pos['t2'], pnl, 'T2')
                return 'T2'
        return None
    
    def _close(self, exit_price, pnl, reason):
        if self.current_position:
            self.current_position['exit'] = exit_price
            self.current_position['pnl'] = pnl
            self.current_position['status'] = reason
            self.paper_pnl += pnl
            logger.info(f"🛢️ CRUDE CLOSE: {reason} @ ${exit_price:.2f} | P&L: ${pnl:+.2f}")
            self.current_position = None
    
    def get_stats(self):
        if not self.paper_trades:
            return {'total': 0, 'pnl': 0, 'win_rate': 0}
        closed = [t for t in self.paper_trades if t['status'] != 'OPEN']
        wins = [t for t in closed if t['pnl'] and t['pnl'] > 0]
        return {
            'total': len(self.paper_trades), 'closed': len(closed),
            'wins': len(wins), 'losses': len(closed)-len(wins),
            'win_rate': len(wins)/len(closed)*100 if closed else 0,
            'pnl': self.paper_pnl
        }
    
    def get_analysis(self):
        try:
            data = self.fetch_data()
            if data is None:
                return {'status': 'error'}
            df = self.calc_indicators(data)
            cur = df.iloc[-1]
            st_dir = int(cur['ST_Dir']) if pd.notna(cur['ST_Dir']) else 0
            trend = "BULLISH" if st_dir == 1 else "BEARISH"
            return {
                'status': 'ok', 'symbol': 'CRUDEOIL',
                'price': round(float(cur['Close']),2), 'trend': trend,
                'rsi': round(float(cur['RSI']),2),
                'timestamp': datetime.now(IST).isoformat()
            }
        except:
            return {'status': 'error'}


crude_strategy = CrudeOilStrategy()
