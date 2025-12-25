"""
Commodity Backtester - Test commodity strategies on historical data
Supports Gold, Silver, and Crude Oil
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from dataclasses import dataclass
from loguru import logger

IST = timezone(timedelta(hours=5, minutes=30))


@dataclass
class CommodityBacktestResult:
    """Backtest result for a commodity strategy"""
    commodity: str
    symbol: str
    strategy: str
    period: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    gross_profit: float
    gross_loss: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    avg_win: float
    avg_loss: float
    trades: List[dict]


class CommodityBacktester:
    """
    Backtest commodity strategies on historical data
    Supports: Gold (GC=F), Silver (SI=F), Crude Oil (CL=F)
    """
    
    SYMBOLS = {
        'GOLD': 'GC=F',
        'SILVER': 'SI=F',
        'CRUDE': 'CL=F'
    }
    
    def __init__(self, capital: float = 50000):
        self.capital = capital
        self.initial_capital = capital
        
    def fetch_data(self, commodity: str, days: int = 7, interval: str = "5m") -> Optional[pd.DataFrame]:
        """Fetch historical data for a commodity"""
        symbol = self.SYMBOLS.get(commodity.upper())
        if not symbol:
            logger.error(f"Unknown commodity: {commodity}")
            return None
        
        try:
            # For 5m data, yfinance limits to 60 days
            period = f"{min(days, 60)}d"
            data = yf.download(symbol, period=period, interval=interval, progress=False)
            
            if len(data) < 50:
                logger.warning(f"Insufficient data for {commodity}")
                return None
            
            # Flatten columns if multi-index
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch {commodity} data: {e}")
            return None
    
    def calculate_gold_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicators for Gold strategy"""
        data = df.copy()
        close = data['Close'].squeeze()
        
        # EMAs
        data['EMA9'] = close.ewm(span=9).mean()
        data['EMA21'] = close.ewm(span=21).mean()
        
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        data['RSI'] = 100 - (100 / (1 + gain/loss))
        
        return data
    
    def calculate_silver_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicators for Silver strategy - TUNED"""
        data = df.copy()
        close = data['Close'].squeeze()
        volume = data['Volume'].squeeze()
        
        # EMAs - Faster EMA8 for quicker signals
        data['EMA8'] = close.ewm(span=8).mean()
        data['EMA9'] = close.ewm(span=9).mean()  # Keep for compatibility
        data['EMA21'] = close.ewm(span=21).mean()
        data['EMA50'] = close.ewm(span=50).mean()
        
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        data['RSI'] = 100 - (100 / (1 + gain/loss))
        
        # Volume
        data['Vol_MA'] = volume.rolling(20).mean()
        data['Vol_Ratio'] = volume / data['Vol_MA']
        
        return data
    
    def calculate_crude_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicators for Crude Oil strategy - TUNED"""
        data = df.copy()
        close = data['Close'].squeeze()
        high = data['High'].squeeze()
        low = data['Low'].squeeze()
        volume = data['Volume'].squeeze()
        
        # EMAs - TUNED: Faster like MACD
        data['EMA12'] = close.ewm(span=12).mean()
        data['EMA20'] = close.ewm(span=20).mean()  # Keep for compatibility
        data['EMA26'] = close.ewm(span=26).mean()
        data['EMA50'] = close.ewm(span=50).mean()
        
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        data['RSI'] = 100 - (100 / (1 + gain/loss))
        
        # Supertrend - TUNED: Faster (7,2 instead of 10,3)
        tr = pd.concat([high-low, abs(high-close.shift()), abs(low-close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(7).mean()
        hl2 = (high + low) / 2
        ub = hl2 + 2 * atr
        lb = hl2 - 2 * atr
        
        st = pd.Series(index=data.index, dtype=float)
        st_dir = pd.Series(index=data.index, dtype=int)
        for i in range(1, len(data)):
            if close.iloc[i] > ub.iloc[i-1]:
                st.iloc[i], st_dir.iloc[i] = lb.iloc[i], 1
            elif close.iloc[i] < lb.iloc[i-1]:
                st.iloc[i], st_dir.iloc[i] = ub.iloc[i], -1
            else:
                st.iloc[i] = st.iloc[i-1] if pd.notna(st.iloc[i-1]) else lb.iloc[i]
                st_dir.iloc[i] = st_dir.iloc[i-1] if pd.notna(st_dir.iloc[i-1]) else 1
        
        data['ST_Dir'] = st_dir
        
        # Camarilla Pivot levels for mean reversion
        data['D_High'] = high.rolling(78).max()
        data['D_Low'] = low.rolling(78).min()
        
        # Volume
        data['Vol_MA'] = volume.rolling(20).mean()
        data['Vol_Ratio'] = volume / data['Vol_MA']
        
        return data
    
    def backtest_gold(self, days: int = 7) -> CommodityBacktestResult:
        """Backtest Gold EMA Crossover strategy"""
        logger.info(f"🥇 Backtesting GOLD for {days} days...")
        
        data = self.fetch_data('GOLD', days)
        if data is None:
            return self._empty_result('GOLD', 'EMA Crossover', days)
        
        df = self.calculate_gold_indicators(data)
        trades = []
        position = None
        sl_pct, target_pct = 0.5, 1.0
        
        for i in range(22, len(df)):
            cur, prev = df.iloc[i], df.iloc[i-1]
            close = float(cur['Close'])
            ema9, ema21 = float(cur['EMA9']), float(cur['EMA21'])
            p_ema9, p_ema21 = float(prev['EMA9']), float(prev['EMA21'])
            rsi = float(cur['RSI'])
            
            # Check exits
            if position:
                if position['type'] == 'BUY':
                    if close <= position['sl']:
                        position['exit'] = position['sl']
                        position['pnl'] = position['sl'] - position['entry']
                        position['result'] = 'SL'
                        trades.append(position)
                        position = None
                    elif close >= position['target']:
                        position['exit'] = position['target']
                        position['pnl'] = position['target'] - position['entry']
                        position['result'] = 'TARGET'
                        trades.append(position)
                        position = None
                else:  # SELL
                    if close >= position['sl']:
                        position['exit'] = position['sl']
                        position['pnl'] = position['entry'] - position['sl']
                        position['result'] = 'SL'
                        trades.append(position)
                        position = None
                    elif close <= position['target']:
                        position['exit'] = position['target']
                        position['pnl'] = position['entry'] - position['target']
                        position['result'] = 'TARGET'
                        trades.append(position)
                        position = None
            
            # Check entries (only if no position)
            if position is None:
                # BUY: EMA9 crosses above EMA21, RSI < 70
                if p_ema9 <= p_ema21 and ema9 > ema21 and rsi < 70:
                    position = {
                        'type': 'BUY', 'entry': close,
                        'sl': close * (1 - sl_pct/100),
                        'target': close * (1 + target_pct/100),
                        'entry_time': df.index[i]
                    }
                # SELL: EMA9 crosses below EMA21, RSI > 30
                elif p_ema9 >= p_ema21 and ema9 < ema21 and rsi > 30:
                    position = {
                        'type': 'SELL', 'entry': close,
                        'sl': close * (1 + sl_pct/100),
                        'target': close * (1 - target_pct/100),
                        'entry_time': df.index[i]
                    }
        
        return self._calculate_result('GOLD', 'EMA Crossover', days, trades)
    
    def backtest_silver(self, days: int = 7) -> CommodityBacktestResult:
        """Backtest Silver Triple EMA + Volume strategy"""
        logger.info(f"🥈 Backtesting SILVER for {days} days...")
        
        data = self.fetch_data('SILVER', days)
        if data is None:
            return self._empty_result('SILVER', 'Triple EMA + Volume', days)
        
        df = self.calculate_silver_indicators(data)
        trades = []
        position = None
        sl_pct, target_pct = 0.6, 1.8  # TUNED: Better R:R (1:3)
        
        for i in range(52, len(df)):
            cur, prev = df.iloc[i], df.iloc[i-1]
            close = float(cur['Close'])
            ema8, ema21, ema50 = float(cur['EMA8']), float(cur['EMA21']), float(cur['EMA50'])
            p_ema8, p_ema21 = float(prev['EMA8']), float(prev['EMA21'])
            rsi = float(cur['RSI'])
            
            # Check exits
            if position:
                if position['type'] == 'BUY':
                    if close <= position['sl']:
                        position['exit'], position['pnl'] = position['sl'], position['sl'] - position['entry']
                        position['result'] = 'SL'
                        trades.append(position)
                        position = None
                    elif close >= position['target']:
                        position['exit'], position['pnl'] = position['target'], position['target'] - position['entry']
                        position['result'] = 'TARGET'
                        trades.append(position)
                        position = None
                else:
                    if close >= position['sl']:
                        position['exit'], position['pnl'] = position['sl'], position['entry'] - position['sl']
                        position['result'] = 'SL'
                        trades.append(position)
                        position = None
                    elif close <= position['target']:
                        position['exit'], position['pnl'] = position['target'], position['entry'] - position['target']
                        position['result'] = 'TARGET'
                        trades.append(position)
                        position = None
            
            # Check entries - TUNED: Wider RSI zones
            if position is None:
                # BUY: EMA8 crosses above EMA21, above EMA50, RSI in wide zone
                if p_ema8 <= p_ema21 and ema8 > ema21 and close > ema50 and 35 <= rsi <= 70:
                    position = {
                        'type': 'BUY', 'entry': close,
                        'sl': close * (1 - sl_pct/100),
                        'target': close * (1 + target_pct/100),
                        'entry_time': df.index[i]
                    }
                # SELL: EMA8 crosses below EMA21, below EMA50, RSI in wide zone
                elif p_ema8 >= p_ema21 and ema8 < ema21 and close < ema50 and 30 <= rsi <= 65:
                    position = {
                        'type': 'SELL', 'entry': close,
                        'sl': close * (1 + sl_pct/100),
                        'target': close * (1 - target_pct/100),
                        'entry_time': df.index[i]
                    }
        
        return self._calculate_result('SILVER', 'Triple EMA + Volume', days, trades)
    
    def backtest_crude(self, days: int = 7) -> CommodityBacktestResult:
        """Backtest Crude Oil Trend + Supertrend strategy"""
        logger.info(f"🛢️ Backtesting CRUDE OIL for {days} days...")
        
        data = self.fetch_data('CRUDE', days)
        if data is None:
            return self._empty_result('CRUDE', 'EMA + Supertrend', days)
        
        df = self.calculate_crude_indicators(data)
        trades = []
        position = None
        sl_pct, target_pct = 0.6, 1.2  # TUNED: Better R:R
        
        for i in range(52, len(df)):
            cur, prev = df.iloc[i], df.iloc[i-1]
            close = float(cur['Close'])
            ema12, ema26, ema50 = float(cur['EMA12']), float(cur['EMA26']), float(cur['EMA50'])
            p_ema12, p_ema26 = float(prev['EMA12']), float(prev['EMA26'])
            rsi = float(cur['RSI'])
            st_dir = int(cur['ST_Dir']) if pd.notna(cur['ST_Dir']) else 0
            p_st_dir = int(prev['ST_Dir']) if pd.notna(prev['ST_Dir']) else 0
            
            # Camarilla pivots for mean reversion
            d_high, d_low = float(cur['D_High']), float(cur['D_Low'])
            r = d_high - d_low
            h3, l3 = close + r*1.1/4, close - r*1.1/4
            
            # Check exits
            if position:
                if position['type'] == 'BUY':
                    if close <= position['sl']:
                        position['exit'], position['pnl'] = position['sl'], position['sl'] - position['entry']
                        position['result'] = 'SL'
                        trades.append(position)
                        position = None
                    elif close >= position['target']:
                        position['exit'], position['pnl'] = position['target'], position['target'] - position['entry']
                        position['result'] = 'TARGET'
                        trades.append(position)
                        position = None
                else:
                    if close >= position['sl']:
                        position['exit'], position['pnl'] = position['sl'], position['entry'] - position['sl']
                        position['result'] = 'SL'
                        trades.append(position)
                        position = None
                    elif close <= position['target']:
                        position['exit'], position['pnl'] = position['target'], position['entry'] - position['target']
                        position['result'] = 'TARGET'
                        trades.append(position)
                        position = None
            
            # Check entries - TUNED
            if position is None:
                # Strategy 1: Mean reversion at support (NEW!)
                if close <= l3 and rsi < 40:
                    position = {
                        'type': 'BUY', 'entry': close,
                        'sl': close * (1 - sl_pct/100),
                        'target': close * (1 + target_pct/100),
                        'entry_time': df.index[i], 'strategy': 'MEAN_REVERT'
                    }
                # Strategy 2: Mean reversion at resistance (NEW!)
                elif close >= h3 and rsi > 60:
                    position = {
                        'type': 'SELL', 'entry': close,
                        'sl': close * (1 + sl_pct/100),
                        'target': close * (1 - target_pct/100),
                        'entry_time': df.index[i], 'strategy': 'MEAN_REVERT'
                    }
                # Strategy 3: EMA cross up OR Supertrend flip bullish
                elif not position:
                    ema_cross_up = p_ema12 <= p_ema26 and ema12 > ema26
                    st_flip_up = p_st_dir == -1 and st_dir == 1
                    if (ema_cross_up or st_flip_up) and close > ema50 and 35 < rsi < 75:
                        position = {
                            'type': 'BUY', 'entry': close,
                            'sl': close * (1 - sl_pct/100),
                            'target': close * (1 + target_pct/100),
                            'entry_time': df.index[i], 'strategy': 'TREND'
                        }
                    
                    # Strategy 4: EMA cross down OR Supertrend flip bearish
                    ema_cross_dn = p_ema12 >= p_ema26 and ema12 < ema26
                    st_flip_dn = p_st_dir == 1 and st_dir == -1
                    if (ema_cross_dn or st_flip_dn) and close < ema50 and 25 < rsi < 65:
                        position = {
                            'type': 'SELL', 'entry': close,
                            'sl': close * (1 + sl_pct/100),
                            'target': close * (1 - target_pct/100),
                            'entry_time': df.index[i], 'strategy': 'TREND'
                        }
        
        return self._calculate_result('CRUDE', 'EMA + Supertrend', days, trades)
    
    def backtest_all(self, days: int = 7) -> Dict[str, CommodityBacktestResult]:
        """Backtest all commodity strategies"""
        results = {
            'GOLD': self.backtest_gold(days),
            'SILVER': self.backtest_silver(days),
            'CRUDE': self.backtest_crude(days)
        }
        return results
    
    def _empty_result(self, commodity: str, strategy: str, days: int) -> CommodityBacktestResult:
        """Return empty result when no data"""
        return CommodityBacktestResult(
            commodity=commodity, symbol=self.SYMBOLS.get(commodity, ''),
            strategy=strategy, period=f"{days} days",
            total_trades=0, winning_trades=0, losing_trades=0,
            total_pnl=0, gross_profit=0, gross_loss=0,
            win_rate=0, profit_factor=0, max_drawdown=0,
            avg_win=0, avg_loss=0, trades=[]
        )
    
    def _calculate_result(self, commodity: str, strategy: str, days: int, trades: List[dict]) -> CommodityBacktestResult:
        """Calculate backtest statistics"""
        if not trades:
            return self._empty_result(commodity, strategy, days)
        
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        
        gross_profit = sum(t['pnl'] for t in wins) if wins else 0
        gross_loss = abs(sum(t['pnl'] for t in losses)) if losses else 0
        
        # Calculate max drawdown
        equity = self.initial_capital
        peak = equity
        max_dd = 0
        for t in trades:
            equity += t['pnl']
            peak = max(peak, equity)
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return CommodityBacktestResult(
            commodity=commodity,
            symbol=self.SYMBOLS.get(commodity, ''),
            strategy=strategy,
            period=f"{days} days",
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            total_pnl=round(sum(t['pnl'] for t in trades), 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            win_rate=round(len(wins)/len(trades)*100, 1) if trades else 0,
            profit_factor=round(gross_profit/gross_loss, 2) if gross_loss > 0 else float('inf'),
            max_drawdown=round(max_dd, 2),
            avg_win=round(gross_profit/len(wins), 2) if wins else 0,
            avg_loss=round(gross_loss/len(losses), 2) if losses else 0,
            trades=trades
        )
    
    def print_result(self, result: CommodityBacktestResult):
        """Print backtest result in a nice format"""
        print(f"\n{'='*60}")
        print(f"📊 {result.commodity} BACKTEST RESULTS")
        print(f"{'='*60}")
        print(f"Strategy: {result.strategy}")
        print(f"Period: {result.period}")
        print(f"Symbol: {result.symbol}")
        print(f"{'-'*60}")
        print(f"Total Trades:    {result.total_trades}")
        print(f"Winning Trades:  {result.winning_trades}")
        print(f"Losing Trades:   {result.losing_trades}")
        print(f"Win Rate:        {result.win_rate:.1f}%")
        print(f"{'-'*60}")
        print(f"Total P&L:       ${result.total_pnl:+.2f}")
        print(f"Gross Profit:    ${result.gross_profit:.2f}")
        print(f"Gross Loss:      ${result.gross_loss:.2f}")
        print(f"Profit Factor:   {result.profit_factor:.2f}")
        print(f"{'-'*60}")
        print(f"Avg Win:         ${result.avg_win:.2f}")
        print(f"Avg Loss:        ${result.avg_loss:.2f}")
        print(f"Max Drawdown:    {result.max_drawdown:.2f}%")
        print(f"{'='*60}\n")
    
    def print_summary(self, results: Dict[str, CommodityBacktestResult]):
        """Print summary of all commodities"""
        print("\n" + "="*70)
        print("📊 COMMODITY BACKTEST SUMMARY")
        print("="*70)
        print(f"{'Commodity':<12} {'Trades':<8} {'Win%':<8} {'P&L':>12} {'PF':>8} {'MaxDD':>8}")
        print("-"*70)
        
        total_pnl = 0
        total_trades = 0
        
        for name, result in results.items():
            emoji = '🥇' if name == 'GOLD' else '🥈' if name == 'SILVER' else '🛢️'
            pf_str = f"{result.profit_factor:.2f}" if result.profit_factor != float('inf') else "∞"
            print(f"{emoji} {name:<10} {result.total_trades:<8} {result.win_rate:<7.1f}% ${result.total_pnl:>10.2f} {pf_str:>8} {result.max_drawdown:>7.2f}%")
            total_pnl += result.total_pnl
            total_trades += result.total_trades
        
        print("-"*70)
        print(f"{'TOTAL':<12} {total_trades:<8} {'':<8} ${total_pnl:>10.2f}")
        print("="*70 + "\n")


def run_commodity_backtest(days: int = 7, capital: float = 50000):
    """Run backtest for all commodities"""
    bt = CommodityBacktester(capital=capital)
    results = bt.backtest_all(days=days)
    
    for result in results.values():
        bt.print_result(result)
    
    bt.print_summary(results)
    return results


if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    run_commodity_backtest(days=days)
