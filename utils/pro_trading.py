"""
Professional Trading Features
- Brokerage Calculator
- Trailing Stop Loss
- Market Sentiment Filter
- Time-Based Filters
- Risk Management Enhancements
"""

import os
from datetime import datetime, time as dtime
from typing import Dict, Tuple, Optional
from loguru import logger
import yfinance as yf


class BrokerageCalculator:
    """Calculate Zerodha brokerage and charges"""
    
    # Zerodha charges for equity intraday
    BROKERAGE_PER_ORDER = 20  # ₹20 or 0.03% whichever is lower
    STT_RATE = 0.00025  # 0.025% on sell side
    TRANSACTION_CHARGES = 0.0000345  # NSE: 0.00345%
    GST_RATE = 0.18  # 18% on brokerage + transaction charges
    SEBI_CHARGES = 0.000001  # ₹10 per crore
    STAMP_DUTY = 0.00003  # 0.003% on buy side
    
    @classmethod
    def calculate(cls, buy_price: float, sell_price: float, quantity: int) -> Dict:
        """
        Calculate total charges for a trade
        
        Returns:
            Dict with breakdown of all charges
        """
        buy_value = buy_price * quantity
        sell_value = sell_price * quantity
        turnover = buy_value + sell_value
        
        # Brokerage (₹20 per order or 0.03%, whichever is lower)
        buy_brokerage = min(20, buy_value * 0.0003)
        sell_brokerage = min(20, sell_value * 0.0003)
        total_brokerage = buy_brokerage + sell_brokerage
        
        # STT (only on sell side for intraday)
        stt = sell_value * cls.STT_RATE
        
        # Transaction charges
        transaction_charges = turnover * cls.TRANSACTION_CHARGES
        
        # GST
        gst = (total_brokerage + transaction_charges) * cls.GST_RATE
        
        # SEBI charges
        sebi = turnover * cls.SEBI_CHARGES
        
        # Stamp duty (only on buy side)
        stamp_duty = buy_value * cls.STAMP_DUTY
        
        # Total charges
        total_charges = total_brokerage + stt + transaction_charges + gst + sebi + stamp_duty
        
        # Gross P&L and Net P&L
        gross_pnl = (sell_price - buy_price) * quantity
        net_pnl = gross_pnl - total_charges
        
        return {
            'buy_value': buy_value,
            'sell_value': sell_value,
            'turnover': turnover,
            'brokerage': round(total_brokerage, 2),
            'stt': round(stt, 2),
            'transaction_charges': round(transaction_charges, 2),
            'gst': round(gst, 2),
            'sebi': round(sebi, 2),
            'stamp_duty': round(stamp_duty, 2),
            'total_charges': round(total_charges, 2),
            'gross_pnl': round(gross_pnl, 2),
            'net_pnl': round(net_pnl, 2)
        }
    
    @classmethod
    def estimate_charges(cls, trade_value: float) -> float:
        """Quick estimate of charges for a round trip trade"""
        # Approximately ₹40-50 per trade for ₹10,000 trade value
        return min(50, trade_value * 0.005)  # ~0.5% of trade value


class TrailingStopLoss:
    """Manage trailing stop losses"""
    
    def __init__(self, entry_price: float, initial_sl: float, target: float):
        self.entry_price = entry_price
        self.initial_sl = initial_sl
        self.current_sl = initial_sl
        self.target = target
        self.highest_price = entry_price
        self.is_long = entry_price > initial_sl
    
    def update(self, current_price: float) -> Tuple[float, bool, str]:
        """
        Update trailing stop loss based on current price
        
        Returns:
            (new_sl, should_exit, exit_reason)
        """
        # Check if SL hit
        if self.is_long:
            if current_price <= self.current_sl:
                return self.current_sl, True, "STOP_LOSS"
            
            # Check if target hit
            if current_price >= self.target:
                return self.current_sl, True, "TARGET"
            
            # Update highest price
            if current_price > self.highest_price:
                self.highest_price = current_price
                
                # Move SL to breakeven after 0.3% profit
                if current_price >= self.entry_price * 1.003:
                    new_sl = max(self.current_sl, self.entry_price * 1.001)
                    if new_sl > self.current_sl:
                        self.current_sl = new_sl
                        logger.info(f"📈 Trailing SL moved to ₹{new_sl:.2f} (breakeven+)")
                
                # Move SL to 50% of profit after 0.5% profit
                if current_price >= self.entry_price * 1.005:
                    profit = current_price - self.entry_price
                    new_sl = max(self.current_sl, self.entry_price + profit * 0.5)
                    if new_sl > self.current_sl:
                        self.current_sl = new_sl
                        logger.info(f"📈 Trailing SL moved to ₹{new_sl:.2f} (lock 50% profit)")
        
        return self.current_sl, False, ""


class MarketSentimentFilter:
    """Filter trades based on market sentiment"""
    
    def __init__(self):
        self.nifty_open = None
        self.nifty_current = None
        self.sentiment = "NEUTRAL"
    
    def update(self) -> str:
        """Update market sentiment based on NIFTY"""
        try:
            ticker = yf.Ticker("^NSEI")
            data = ticker.history(period="1d", interval="5m")
            
            if data.empty:
                return "NEUTRAL"
            
            self.nifty_open = data.iloc[0]['Open']
            self.nifty_current = data.iloc[-1]['Close']
            
            change_pct = ((self.nifty_current - self.nifty_open) / self.nifty_open) * 100
            
            if change_pct > 0.5:
                self.sentiment = "BULLISH"
            elif change_pct < -0.5:
                self.sentiment = "BEARISH"
            else:
                self.sentiment = "NEUTRAL"
            
            logger.info(f"🌡️ Market Sentiment: {self.sentiment} (NIFTY: {change_pct:+.2f}%)")
            return self.sentiment
            
        except Exception as e:
            logger.error(f"Error getting market sentiment: {e}")
            return "NEUTRAL"
    
    def should_trade(self, signal_type: str) -> Tuple[bool, str]:
        """
        Check if trade should be taken based on sentiment
        
        Args:
            signal_type: "BUY" or "SELL"
        
        Returns:
            (can_trade, reason)
        """
        if self.sentiment == "BEARISH" and signal_type == "BUY":
            return False, "Market is bearish, skip BUY signals"
        
        if self.sentiment == "BULLISH" and signal_type == "SELL":
            return False, "Market is bullish, skip SELL signals"
        
        return True, "OK"


class TimeFilter:
    """Filter trades based on time of day"""
    
    # Volatile/risky times to avoid
    AVOID_TIMES = [
        (dtime(9, 15), dtime(9, 30)),   # Opening volatility
        (dtime(12, 0), dtime(13, 0)),   # Lunch hour - low volume
        (dtime(14, 30), dtime(15, 30)), # Closing volatility
    ]
    
    # Best trading times
    BEST_TIMES = [
        (dtime(9, 45), dtime(11, 30)),  # Morning session
        (dtime(13, 30), dtime(14, 15)), # Afternoon session
    ]
    
    @classmethod
    def is_safe_time(cls) -> Tuple[bool, str]:
        """Check if current time is safe for trading"""
        now = datetime.now().time()
        
        # Check if in avoid times
        for start, end in cls.AVOID_TIMES:
            if start <= now <= end:
                return False, f"Avoid time: {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
        
        return True, "OK"
    
    @classmethod
    def is_best_time(cls) -> bool:
        """Check if current time is best for trading"""
        now = datetime.now().time()
        
        for start, end in cls.BEST_TIMES:
            if start <= now <= end:
                return True
        
        return False


class PartialProfitBooking:
    """Manage partial profit booking"""
    
    def __init__(self, entry_price: float, quantity: int, target1_pct: float = 0.003, target2_pct: float = 0.005):
        self.entry_price = entry_price
        self.initial_quantity = quantity
        self.remaining_quantity = quantity
        self.target1 = entry_price * (1 + target1_pct)  # 0.3%
        self.target2 = entry_price * (1 + target2_pct)  # 0.5%
        self.target1_hit = False
        self.target2_hit = False
    
    def check_targets(self, current_price: float) -> Dict:
        """
        Check if partial targets are hit
        
        Returns:
            Dict with booking details
        """
        result = {
            'book_quantity': 0,
            'remaining_quantity': self.remaining_quantity,
            'reason': None
        }
        
        # Target 1: Book 50% at 0.3% profit
        if not self.target1_hit and current_price >= self.target1:
            book_qty = self.remaining_quantity // 2
            self.remaining_quantity -= book_qty
            self.target1_hit = True
            result['book_quantity'] = book_qty
            result['remaining_quantity'] = self.remaining_quantity
            result['reason'] = 'TARGET_1'
            logger.info(f"📊 Partial booking: {book_qty} shares at Target 1")
        
        # Target 2: Book remaining at 0.5% profit
        elif not self.target2_hit and current_price >= self.target2:
            result['book_quantity'] = self.remaining_quantity
            self.remaining_quantity = 0
            self.target2_hit = True
            result['remaining_quantity'] = 0
            result['reason'] = 'TARGET_2'
            logger.info(f"📊 Full exit: {result['book_quantity']} shares at Target 2")
        
        return result


# Utility function for quick charge estimation
def estimate_trade_profit(entry: float, exit: float, qty: int) -> Dict:
    """Quick estimate of trade profit including charges"""
    calc = BrokerageCalculator.calculate(entry, exit, qty)
    return {
        'gross_pnl': calc['gross_pnl'],
        'charges': calc['total_charges'],
        'net_pnl': calc['net_pnl']
    }


# Check if trade is worth taking (after charges)
def is_trade_profitable(entry: float, target: float, qty: int, min_profit: float = 30) -> Tuple[bool, str]:
    """Check if trade will be profitable after charges"""
    expected = estimate_trade_profit(entry, target, qty)
    
    if expected['net_pnl'] < min_profit:
        return False, f"Expected net profit ₹{expected['net_pnl']:.0f} is below minimum ₹{min_profit}"
    
    return True, f"Expected net profit: ₹{expected['net_pnl']:.0f}"
